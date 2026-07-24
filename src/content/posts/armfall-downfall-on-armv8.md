---
title: "armFall: Reproducing Downfall on armv8"
published: 2025-12-15
description: "Will Downfall work on popular ARM CPUs? We reproduced Intel's Gather Data Sampling attack on a Raspberry Pi 5 and an Apple M4 via NEON, and looked for a usable side channel."
tags: [Hardware Security, Microarchitecture, ARM, NEON, Side-Channels, Speculative Execution]
category: Research
image: /covers/post-armfall.png
event: Purdue ECE 69500 · Fall 2025
contributors:
  - name: Setsuna Yuki
    url: https://github.com/SetsuY
  - name: Matthew Gyure
    url: https://github.com/goo3r
draft: false
---

> We aim to reproduce the [Downfall](https://downfall.page/) attack on current armv8 platforms, exploiting
> speculative execution on SIMD functional units inside the processor. We target
> Raspberry Pi 5 and Apple Silicon M4 as popular armv8 implementations. Through
> analysis of available instructions, we target the NEON SIMD instructions on the
> two platforms and crafted an attack utilizing the strided load instruction. The
> lack of clear side-channel signal from the attack suggests that there is no
> meaningful Downfall-style exploit available on these two platforms.

Research I took on at Purdue with two colleagues over a semester — three of us
chasing one question: **will Downfall work on popular ARM CPUs?** Or, put more
sharply: *even without gather, do ARM's SIMD load patterns plus speculation
reveal any stale SIMD state?*

## Introduction

Modern processors rely heavily on speculative execution and wide SIMD (Single
Instruction Multiple Data) units to achieve high performance. While these
techniques significantly improve throughput, they have also enabled a class of
microarchitectural side-channel attacks that can leak sensitive data across
security boundaries. Over the past several years, attacks such as Spectre,
Meltdown, and more recently Downfall have demonstrated that transient execution
can expose information that should not be architecturally accessible.

Downfall, also known as **Gather Data Sampling (GDS)**, is a microarchitectural
attack that exploits speculative execution of SIMD gather instructions on Intel
processors. By leveraging stale data left in internal CPU buffers, an attacker
can transiently sample victim data and recover it through cache-based side
channels. While Intel has released mitigations for affected processors, the
attack raises a broader question: whether similar vulnerabilities exist in
non-Intel architectures that employ speculative execution and SIMD acceleration.

In this work, we investigate whether a Downfall-style attack can be reproduced on
armv8 platforms. ARM processors differ from x86 in both their instruction set and
microarchitectural implementation, particularly in how SIMD operations are
handled. Notably, common armv8 implementations do not support classic gather
instructions in NEON, which are central to the original Downfall attack. However,
ARM processors still include speculative execution, load buffers, and wide SIMD
units, suggesting that related attack vectors may be possible.

We focus on two widely used armv8 systems: the Raspberry Pi 5 and Apple Silicon
M4. Due to the lack of SVE support on these platforms, and the co-processor based
implementation of the Apple AMX instructions, we target NEON SIMD instructions
and explore whether complex load patterns, such as stride-based vector loads, can
be used to create a similar leakage mechanism. Our goal is to determine whether
speculative execution of NEON loads can expose stale data in a manner analogous
to Downfall.

Our experimental results show no meaningful evidence of Downfall-style data
leakage on either platform. Despite carefully constructing transient execution
windows and cache-based measurement oracles, the observed signal-to-noise ratio
remains low and does not correlate with victim data. These findings suggest that
current armv8 implementations, at least on the tested platforms, are not
vulnerable to a straightforward reproduction of the Downfall attack.

## Background

### The Downfall attack

The Downfall Gather Data Sampling attack targets the SIMD unit in several
generations of Intel processors. The Intel AVX extension provides SIMD
capabilities. Essentially, they provide long registers able to be divided into
several slots, or lanes, essentially forming a vector. Instructions operate on
those vectors to provide acceleration for various applications.

Notably, the AVX extension supports the gathering load operation, providing the
function of the following algorithm in a single instruction:

```python
for i in num_lanes:
    if mask[i] == 1:
        result[i] = *(base_ptr + offset[i])
```

![Gather: each lane holds its own byte offset; the instruction reads memory at base + offset[i] for every unmasked lane and packs the results into the destination vector — one instruction, many non-contiguous addresses.](/research/gather.svg)

*One instruction, many addresses: each lane reads from `base + offset[i]`
(masked lanes are skipped) and the results pack into the destination register.*

This complex load operation is tricky to accelerate due to data dependency in the
memory access pattern. To optimize the implementation, Intel introduces a **load
buffer** to its SIMD units, caching recently accessed values and optimistically
forwarding it speculatively. Furthermore, this buffer is not cleared in case of a
context switch, making stealing the buffer content with a Meltdown-style probe
possible.

It helps to see why that buffer is dangerous. Gather is expensive, so the SIMD
unit keeps a small internal buffer of values it recently moved and forwards them
quickly instead of re-reading memory every time. To stay fast it forwards
optimistically: it hands a later instruction whatever is sitting in the buffer
before it has fully checked that the instruction was allowed to run, or that the
data even belongs to this program. Most of the time the guess is right and nobody
notices. The interesting case is when the guess is wrong.

That is where speculation comes in. A modern core runs ahead of itself: when a
load is slow or a fault is pending, it keeps executing the instructions after it
on a guess, and if the guess turns out wrong it discards the results and pretends
it never happened. It can undo registers and flags, but it cannot undo the cache.
Anything pulled into the cache during that short window is still there afterward.
Downfall lives in that gap. For a few hundred picoseconds the gather forwards
another context's leftover bytes into a register, a dependent instruction uses
them, and even though all of it is squashed a moment later, the cache still
carries a fingerprint of what those bytes were.

On Intel, the actual attack is only a handful of instructions. It widens the
transient window, gathers from uncacheable memory (the leaky step), encodes the
transiently-gathered bytes into the cache, then scans them back out:

```asm
; x86 / AVX-512 — the four steps of the Downfall (GDS) gather attack
; (i) increase the transient window
lea   addresses_normal, %rdi
clflush (%rdi)
mov   (%rdi), %rax
; (ii) gather uncacheable memory
lea   addresses_uncacheable, %rsi
mov   $0b1, %rdi
kmovq %rdi, %k1
vpxord %zmm1, %zmm1, %zmm1
vpgatherdd 0(%rsi, %zmm1, 1), %zmm5{%k1}
; (iii) encode (transient) data to cache
movq  %xmm5, %rax
encode_eax
; (iv) scan the cache
scan_flush_reload
```

The single dangerous instruction is `vpgatherdd`: the gather that speculatively
pulls forwarded bytes out of that load buffer. Everything around it is just
Flush+Reload plumbing.

Read the four steps as one motion. Step (i) stalls the pipeline on a slow load so
there is a speculation window to work inside. Step (ii) fires the gather, the
moment the buffer forwards its stale contents. Step (iii) takes each leaked byte
and uses it as an index into a large array, touching the page whose number is that
byte, so exactly one cache line out of 256 goes warm. The value is now written
into which line is cached, not into any register the program is allowed to read.
Step (iv) times all 256 lines: 255 are slow, and the single fast one names the
byte. Walk the offsets and the secret comes back a byte at a time. Because the
buffer is never cleared between contexts, the bytes you recover can belong to
another process, the kernel, or an SGX enclave sharing the core.

There are several requirements for the Downfall attack to work:

- Complex SIMD memory operations.
- Optimistic, speculative memory instruction acceleration.
- Cache timing side channels that survive miss speculation.
- Stale state in microarchitecture surviving context switch.

We know all modern processors support complex SIMD operations, Out-of-Order and
speculative execution. For its purpose, cache side channels always exist.
Therefore, this study will examine if there are architectural side effects for us
to exploit in two popular armv8 implementations.

| Requirement | On armv8 |
| --- | --- |
| Complex SIMD memory instructions with multi-lane operations | ✅ |
| Optimistic, speculative memory-instruction acceleration | ✅ |
| Cache-timing channels that survive mis-speculation | ✅ |
| Stale state in the microarchitecture | ❓ |

### Target ISA extensions

**Apple AMX.** AMX, or Apple Matrix Coprocessor, is a proprietary and
undocumented coprocessor included in several Apple processors including the
M-series. It is essentially an **Outer Product Machine**, accelerating matrix
multiplication operations. Figure 1 details its internal groups of `x`, `y`, `z`
registers, where `x` and `y` registers are mainly used to store inputs and `z`
registers for outputs.

![AMX register layout — X registers across the top, Y registers down the left, and the Z accumulator computing z[i][j] += x[i]·y[j].](/research/armfall-amx-registers.webp)

*Figure 1: AMX Register Layout (after the Apple AMX documentation / Outer Product
Engine patent).*

AMX supports the gather operation, called **Indexed Load**, to its registers,
similar to the gather instruction targeted by Downfall. However, since it is
designed as a coprocessor, direct data movement from AMX registers to general
purpose registers is not possible. Data movement is instead facilitated with
system memory, eliminating the possibility of optimistic forwarding. Thus it is
not suitable for our attack. (There's precedent for microarchitectural bugs on
Apple Silicon — the AGX GPU exploit, CVE-2022-32947 — which is what made it worth
checking in the first place.)

**ARM NEON.** NEON is the ARM version of SIMD extensions. All registers are fixed
128-bit wide, and dividing them into multiple lanes is supported. Just like Intel
AVX, complex SIMD operations are possible. Unlike AVX though, is that NEON does
not support gathering load. It only supports strided loads where elements are
spaced out evenly in memory.

We believe that this load pattern is still a valuable target for its greater
complexity over contiguous load, justifying caching in its implementation. In
addition, NEON is supported on both the Raspberry Pi 5 and Apple M4, making NEON a
good target for this study.

**ARM SVE.** SVE is the next generation ARM SIMD extension introduced with armv8.
Improving upon NEON, it supports variable register up to 1024-bit wide. It also
provides the gathering load instruction, a key target in the original Downfall
attack.

However, both Raspberry Pi 5 and Apple M4 do not support SVE. We were not able to
identify and obtain a processor with SVE support in time for this study. There
aren't many candidates for these chips — mostly cloud and HPC — and it was too
late to acquire the hardware. **So NEON it is.**

## Method

### Process pinning

For Downfall to work, the victim and attacker must be operating on the same
processor core. On the Raspberry Pi 5 running Linux, we achieve this with the
`taskset` command.

On the Apple M4 target with macOS however, no such command is available. A utility
for pinning a process to a core exists, but it does not support the M4 platform.
We thus resort to running the attack multiple times, summing the results. We
believe that a sufficient number of runs will result in some runs coinciding on
the same core, while other runs would present a near uniform distribution on the
access time pattern, which does not interfere with our analysis.

### Attacking NEON implementations

Closely following the original Downfall attack, we implement a proof of concept
attack, of an attacker process trying to leak data from a separate victim process.

#### The victim

The victim performs NEON loads (simulating crypto keys), leaving a side effect on
the load buffer. It runs its load sequence in an infinite loop, loading known
patterns (`0xAA`, `0xBB`, `0xCC`, `0xDD` into `v0`–`v3`), so every time it runs it
will potentially leave stale state for the attacker to steal:

```asm
_victim_load_neon:
    adrp x0, victim_data@PAGE
    add  x0, x0, victim_data@PAGEOFF
    ld1  {v0.16b, v1.16b, v2.16b, v3.16b}, [x0]
    ret
```

#### The attacker

To create a speculative execution window for the attacker, we implemented both the
standard Downfall-style approach and an additional fault-based approach. In the
first method, we followed the original Downfall attack by inducing a long-latency
memory access to delay retirement and allow subsequent NEON instructions to
execute speculatively. During this transient window, the attacker performs NEON
stride load operations and encodes the transiently observed value into a
cache-based side channel.

```c
void attack_slow_mode(void) {
    flush_oracle();
    // Flush the slow target to create cache miss delay
    flush_cache_line(slow_target);
    // Execute attack - slow load creates speculation window
    attacker_speculative_probe_slow(oracle, slow_target);
}
```

The probe opens the window with a cache-missing load, runs the NEON strided load
speculatively, and encodes the forwarded byte into the oracle:

```asm
_attacker_speculative_probe_slow:                ; x19 = oracle, x20 = slow_target
    adrp x2, probe_buf@PAGE
    add  x2, x2, probe_buf@PAGEOFF
    ldr  x3, [x20]                                ; cache miss -> speculation window
    ld4  {v4.8b, v5.8b, v6.8b, v7.8b}, [x2]       ; runs speculatively
    umov w3, v4.b[0]                              ; encode forwarded byte...
    lsl  x3, x3, #12                              ; ...into oracle[byte << 12]
    add  x4, x19, x3
    ldr  w5, [x4]
    ; ...repeat for v5, v6, v7
```

In addition to this method, we explored a fault-based speculative window by
intentionally accessing a memory address that the attacker process does not have
permission to read. Although the fault eventually raises a `SIGSEGV` and squashes
speculative execution, instructions following the fault may still execute
transiently before the exception is handled. We installed a signal handler to
recover from the fault and continue execution, allowing repeated measurements.
This approach was motivated by prior transient execution attacks that leverage
fault suppression, and was tested to determine whether it could expose additional
microarchitectural leakage on armv8 NEON implementations.

```c
void attack_fault_mode(void) {
    flush_oracle();
    if (sigsetjmp(jump_buffer, 1) == 0) {
        // Execute attack - will fault on kernel address
        attacker_speculative_probe_fault(oracle, (void*)FAULT_ADDR);
    }
    // Recovered from fault - cache state preserved
}
```

We target the strided load instruction, and the key instruction sequence is as
follows:

```asm
adrp x0, data@PAGE
add  x0, x0, data@PAGEOFF
ld4  {v0.8b, v1.8b, v2.8b, v3.8b}, [x0]
```

The first two instructions prepare the address in `x0`, and the last instruction
performs the load.

#### The probe and readout

To leak data through a cache side channel, we use the **Flush+Reload** technique.
The attacker will then prepare the probe array, flush the cache using the
following instruction sequence:

```asm
dc civac, x0
dsb sy
isb
```

These instructions first flush the cache line at the specified address, then
perform a data barrier and instruction barrier to ensure memory transactions are
fully committed. To increase the transient window like the original attack, we
perform the same cache line flushing for a dummy data, then attempt to load it.
Then we perform the NEON strided load, followed by encoding the forwarded values
into the probe array.

Finally we **measure which byte was encoded to the cache** — the reload time of
each oracle page, taking the fastest as the leaked byte:

```c
int detect_leaked_byte(void) {
    uint64_t min_time = UINT64_MAX;
    int min_idx = -1;
    for (int i = 0; i < 256; i++) {
        uint64_t t = measure_access(&oracle[i * PAGE_SIZE]);
        if (t < min_time) {
            min_time = t;
            min_idx = i;
        }
    }
    return min_idx;
}
```

## Analysis

### Running the attack

Running the attacks consisted of first acquiring the target hardware. In our case
this consisted of a Raspberry Pi 5 and M4-based Mac. To avoid cross-compiling and
potentially missing key issues these were compiled and ran on the target
hardware. On the Raspberry Pi 5 the most recent version of GCC that was available
at the time of this Research on Raspberry Pi OS was used to compile the attack. On
the M4 Mac, Clang shipped with XCode Command Line Tools was used to compile the
same attack. The code remained almost identical aside from a small change in
assembly syntax, addressing Apple's use of 16 KiB page size.

After compilation, a victim and attacker process was started. The victim kept
doing NEON SIMD loads of known values. The attacker process would then be tried in
two different ways. First, it would create a cache miss to create a speculation
window. This was closer to how the original Downfall attack worked. The second
method involved attempting to read kernel memory which would result in a fault.
This would be slower, but allow for another opportunity to exploit.

Both variations of attacks were run on each of our chosen target hardware. The
software reports how many attack rounds were attempted, how many victim detections
were found, and if any significant leakage was detected. From the results, we do
not see the expected byte being retrieved by the attacker consistently, signaling
these two platforms not being vulnerable to our attack.

![Apple M4, cache-miss attack: 10,000 rounds, zero victim detections, "No significant leakage detected."](/research/armfall-m4-attack.webp)

*Figure 2: M4 Cache Miss Attack. Top detected bytes `0x00` (9,935) and `0x01`
(65) — both from the probe buffer, not a victim pattern.*

![Apple M4 victim terminal: loading patterns 0xAA, 0xBB, 0xCC, 0xDD into NEON v0–v3.](/research/armfall-m4-victim.webp)

*Figure 3: M4 Victim, loading the known patterns into `v0`–`v3` in a loop while
the attacker probes.*

![Apple M4, fault-mode attack: faults handled and recovered, no significant leakage detected.](/research/armfall-m4-fault.webp)

*The second (fault-based) attack on the M4: the fault path runs and recovers
cleanly, but still surfaces no victim byte.*

![Raspberry Pi 5 cache-miss attack: built with GCC, victim loading patterns, 10,000 rounds with zero victim detections.](/research/armfall-pi5-cachemiss.webp)

*Figure 4: Raspberry Pi 5 Cache Miss Attack — built and run natively with GCC.*

![Raspberry Pi 5, victim and attacker terminals: 10,000 faults handled, no leakage detected.](/research/armfall-pi5-attack.webp)

*Figure 5: Raspberry Pi 5 Victim (with the fault-mode attacker beside it) —
10,000 faults handled and recovered, same outcome.*

### Side-channel signal-to-noise analysis

In Figure 6 and Figure 7, we plot the reload time of each value in the probe
array. For most runs, cache access time returns as 0 from the system's
performance counter, so we sum up the results from multiple runs.

If there is leaked data recorded in the cache side channel, one probe byte would
show significantly less access time compared to all others. However, none of the
platforms show this pattern. For the Raspberry Pi 5, access time pattern resembles
a uniform distribution. While the M4 platform shows several spikes, none at the
expected byte value. We believe this is due to the lack of process pinning,
introducing noise when the attacker and victim processes does not reside on the
same core. The lack of the expected pattern suggests the lack of a usable side
channel. Thus we conclude that no meaningful evidence of Downfall-style data leak
is present on the Apple M4 and Raspberry Pi 5 platforms.

![Apple M4 signal plot — summed access time per byte value, a few spikes but none at a victim byte.](/research/armfall-m4-snr.webp)

*Figure 6: Probe Value vs Load Time for Cache Probing, Apple M4.*

![Raspberry Pi 5 signal plot — summed access time per byte value, essentially a uniform distribution.](/research/armfall-pi5-snr.webp)

*Figure 7: Probe Value vs Load Time for Cache Probing, Raspberry Pi 5.*

This attack is a modified version of the Downfall attack used against x86 AVX
instructions. That attack uses an intermediate buffer while loading non-contiguous
memory. While we did not expect this buffer to exist in NEON loads, this analysis
confirms our expectations as NEON loads, even interleaved, require contiguous
memory to load in a single instruction.

## Conclusion and discussions

After performing the exploit using the NEON SIMD instructions we saw no
significant leakage of data shown in the original Downfall attacks. This outcome
was expected, as the characteristics that lead to the cache side channel attack in
Downfall relied on an intermediary buffer that was utilized when the gather
instructions were used for pulling memory from non-contiguous memory. Due to the
nature of NEON and how data is loaded this support hardware does not exist in the
same way. Due to this we saw no data leakage once tested against both Apple's M4
and a Raspberry Pi 5.

Some other things worth stating plainly from the results:

- **No data leakage** similar to what we have seen in the Downfall attack.
- This is **expected behavior**, but confirms the hypothesis.
- Downfall has been mitigated in Intel x86 processors **12th generation forward**.
- Initial mitigations for Downfall saw hits to performance.
- Because Downfall was released in 2023, many of those ARM chips **may be
  vulnerable**.

While this was an expected outcome, our study does confirm the data safety when
using NEON with this style of attack. What remains untested and left for further
analysis and experimentation is ARM processors that contain more similar
instructions to the original Downfall attack. The ARMv8 instruction set has
support for what ARM called Scalable Vector Extensions, or SVE instructions. These
contain instructions that much more readily mirror those of the x86 gather
instructions. They allow for places in non-contiguous memory to be fetched with
one instruction. This fundamental step is cause to think some ARM chips may still
be vulnerable.

### Acquiring access to hardware with SVE

ARM chips with SVE/SVE2 instruction support are mostly relegated to the enterprise
and datacenter, often with proprietary designs being manufactured on behalf of
customers for use in their equipment and not available to retail. Due to the
availability or lack-there-of with regards to such devices, this leaves us
without a platform to test this against. The micro-architectural design of these
chips remains unknown, so it is unsure if similar mechanisms found in x86 AVX
gather instructions exist; however, it is hypothesized they do.

- Not a lot of consumer-facing hardware supports the SVE instructions, the
  opposite of x86.
- Most chips are aimed at datacenter or HPC use, so how do we acquire access
  without breaking terms of service?
- Many chips are proprietary, so there's no legal market for access.

If consumer hardware with SVE instruction support becomes available as demand for
more SIMD hardware acceleration increases, this would be the easiest means of
testing for this vulnerability. Additionally, if other means of access to these
chips became available, such as agreements with companies who employ these chips,
this is also a viable path forward. Companies such as Amazon employ their Graviton
series for use in AWS. Because this vulnerability was shown in 2023, and Graviton 3
was shown in 2022 and released 2023, it is conceivable that these processors could
still power workloads in AWS. Due to the dates listed it is also possible that
these chips would not have hardware mitigation in place. The ability to access
these in a manner that does not violate terms of service would have to be obtained
by agreements. If this could be achieved, this Research and exploration could be
expanded and adapted to report on those findings.

Additionally, our implementation makes a key assumption: that a load buffer that
does not contain any tagging or indexing mechanism based on memory addresses
exists. This study does not rule out the existence of a small buffer indexed and
tagged with memory addresses, and only forwards when addresses match. Implementing
such an attack would be more challenging, as it involves sharing memory spaces and
mappings. Nonetheless, this could still be explored in future work.

## Resources

The references behind the work:

1. [Arm NEON Intrinsics Reference](https://arm-software.github.io/acle/neon_intrinsics/advsimd.html)
2. [Intel Intrinsics Guide](https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html)
3. [SVE (Scalable Vector Extensions)](https://developer.arm.com/Architectures/Scalable%20Vector%20Extensions)
4. [taskset(1) - Linux manual page](https://www.man7.org/linux/man-pages/man1/taskset.1.html)
5. Amazon. [Announcing new Amazon EC2 C7g instances powered by AWS Graviton3 processors](https://aws.amazon.com/about-aws/whats-new/2022/05/amazon-ec2-c7g-instances-powered-aws-graviton3-processors/)
6. Peter Cawley. [corsix/amx](https://github.com/corsix/amx)
7. ARM Holdings. [Armv8-A Instruction Set Architecture](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/Armv8-A%20Instruction%20Set%20Architecture.pdf)
8. junjie1475. [MacOS_CoreBinder](https://github.com/junjie1475/MacOS_CoreBinder)
9. Paul Kocher et al. Spectre Attacks: Exploiting Speculative Execution. 40th IEEE Symposium on Security and Privacy (S&P '19).
10. Moritz Lipp et al. Meltdown: Reading Kernel Memory from User Space. 27th USENIX Security Symposium.
11. meekochii. [The Elusive Apple Matrix Coprocessor (AMX)](https://research.meekolab.com/the-elusive-apple-matrix-coprocessor-amx)
12. Daniel Moghimi. [Downfall: Exploiting Speculative Data Gathering](https://downfall.page/). 32nd USENIX Security Symposium (USENIX Security 2023).
13. Ali Sazegari, Eric Bainville, Jeffry E. Gonion, Gerard R. Williams III, and Andrew J. Beaumont-Smith. [Outer Product Engine](https://patents.google.com/patent/US20180074824A1/en)
