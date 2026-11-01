# Clean-VM follow-up: ChatGPT artifacts in Windows RAM

Working protocol, 2026-09-29. Planned captures below are **not results**.
Keep the earlier frozen v1/v2 files unchanged. Work on `main`; do not commit or push.

## Question and scope

Can a parser given only a full Windows memory image and process mappings recover
a linked user/assistant turn, including its IDs, without a known prompt, answer,
conversation ID, message ID, or offset? Does that change after the client leaves
the conversation?

Test ordinary Chrome, ordinary Edge, the installed Codex desktop app (whose
executable is `ChatGPT.exe`), and the native Codex CLI separately. The guest's
installed package identifies itself as `OpenAI.Codex`, not a verified standalone
ChatGPT-for-Windows installation. A result for one client is not a result for
another.
The September 16–17 in-app-browser captures remain exploratory development data,
not clean-VM repetitions. Codex is a separate CLI client, not a terminal version
of the ChatGPT website.

## Reset and evidence separation

1. Preserve the user's `clean` snapshot of `D:\VMs\Research\Research.vmx`.
2. Inventory Windows, client versions, executable paths, RAM, acquisition tools,
   and installed CLI. Do not assume the desktop app is the same build as the pilot.
3. After installing the tools, close target clients and take a new named baseline
   snapshot before creating any experimental conversations.
   The signed-in, client-stopped reset point made on September 30 is
   `ram-auth-profile-ready-20260930-v1`. Verify it restores before counting a
   repetition. The earlier `ram-ui-ready-20260930-v1` predates sign-in.
4. Restore that baseline before every independent repetition. Use a new synthetic
   prompt for each capture. Keep a host-only log of reset, submission, response
   completion, state change, and acquisition start/end times in UTC.
5. Store ground truth, analysis code, logs, and browser-control runtime on the
   **host**, outside the guest. The guest receives only the intended prompt and
   acquisition/setup tools. Never paste a result report back into the guest.
6. A local snapshot cannot reset server-side account history. Collapse sidebars,
   do not open old chats, and report possible history prefetch. Do not delete
   unrelated conversations. Closed-state ground truth is observed while the turn
   is visible and saved only on the host, before closing/navigating.
7. Do not open DevTools, inspect a heap, or collect a network body before an ordinary
   capture. If remote debugging is required for ground truth, record that as an
   instrumented cohort and include uninstrumented UI-only captures for comparison.
8. Do not count a VMware `runProgramInGuest` browser launch as an ordinary UI
   trial until its process is in the interactive Windows session and its page is
   visibly confirmed. A September 30 Edge launch, even with `-activeWindow`,
   ran in Session 0 and was discarded before acquisition.

## Development, then held-out validation

Use one fresh development capture per client to identify its actual serialization.
Develop structural grammars from those captures, not from the known answer in a
validation capture. Freeze hashes, caps, candidate rules, and process-selection
rules before running the held-out set. Log any change as a new method version and
use new captures; never quietly repair the parser against a failed test and keep
calling the same capture held out.

The earlier stream-item parser must be tested as-is on the new clients. A zero
result may mean its envelope is client-specific. Record format applicability
separately from artifact retention.

### Primary matrix

| Client | State | Independent repetitions |
| --- | --- | ---: |
| Chrome, Edge, Codex desktop app | No experimental submission | 1 per client |
| Chrome, Edge, Codex desktop app | Completed response still visible | 3 per client |
| Chrome, Edge | Same tab navigated to a neutral local page | 3 per client |
| Codex desktop app | New chat opened after completion | 3 |
| Chrome, Edge | Conversation tab closed; browser remains open | 3 per client |
| Codex desktop app | App closed; verify remaining background processes | 3 |
| Chrome, Edge | Anonymous/private-window response still visible | 3 per client |
| Native Codex CLI | Completed response, process still running | 3 |
| Native Codex CLI | Exit after completion | 3 |
| Native Codex CLI | Resume the just-created synthetic session | 3 |

Primary set: 45 captures, plus separate development captures. CLI active/exit/resume
trials start from independent restores, rather than reusing one image as a repeat.

An additional **instrumented native CLI app-server** cohort may be driven over
the installed CLI's version-specific stdio API. It is not a terminal-UI result
or a substitute for an ordinary browser capture. The host keeps RPC observations
and scoring data; a guest relay only forwards opaque bytes over pinned TLS. Its
buffers are an explicit observer effect. Inventory the native backend and relay
separately and do not attribute a relay's copy to the CLI. No first-party account
credential is exported. Freeze a separate API-record grammar before any held-out
claim for this cohort.

### Boundary experiments

Run after the primary set; distinguish these from the primary cohort in reporting.

- Unicode (Arabic, accented text, emoji) and an answer exceeding the old 128 KiB
  record cap: test encodings, framing, and exact byte hashes.
- Two conversations in separate tabs and a multi-turn conversation: test mistaken
  cross-conversation joins and branch selection.
- Reload, whole-browser exit/restart, and delayed captures after navigation:
  distinguish active mappings, terminated processes, and physical residue.
- Draft without submission and interrupted generation: challenge completion rules.
- Temporary chat and deletion of a **synthetic test chat only**: distinguish local
  navigation, cloud deletion, and RAM retention. No unrelated history is deleted.
- Paired ordinary-RAM/DevTools-heap experiments, using independent restores:
  compare representations and observer effects, not just output text.
- Compare Volatility and MemProcFS mapping/reading on the same image; discrepancies
  are reported rather than interpreted as exclusive process ownership.

Use three repetitions for any boundary result stated as reproducible. A single
probe is labeled exploratory. Record unavailable UI states or account limits as
not tested, not as negative findings.

## Acquisition and storage

Use WinPmem raw acquisition in the guest, copied to a private host folder. Record
the acquisition interval, exit code, sparse logical length, tool SHA-256, raw SHA-256,
and copy verification. Verify raw-image compatibility with `windows.info` before
parsing. VMware memory captures require their matching metadata and are a separate
acquisition method, not interchangeable evidence without a compatibility check.

Private host root: `C:\Research\chatgpt-ram-validation-20260929\private` for the
verified initial baseline archive and new live captures. It is outside OneDrive
and visible to WSL. Some older private notes remain under the corresponding
`D:\Research` root.
Never put full RAM, browser profiles, cookies, credentials, or unfiltered parser
outputs in OneDrive, the blog repository, `public/`, or a public download.

Compress verified images after analysis, verify the decompressed digest, and retain
the private archive. Monitor free space before each capture; do not discard evidence
or change VM RAM merely to meet the matrix. Preserve at least one complete image
with its process maps for raw-to-record replay. Record any storage-driven deviation.

## Scoring and screenshots

Run the parser first, seal its output hash, then score on the host against C/P/R/U/A
and observed times. Report exact matches, attribution, ambiguity, and completion
separately. Known-value physical scans are secondary diagnostics only.

Negative findings must say which process set, map coverage, encoding, grammar, and
size cap were searched. A zero count is not proof that the information was erased.

Capture actual screens of acquisition, process triage, a recovered record in an
editor/JSON viewer, the joined turn, and the failure comparison. Screenshot source,
capture time, crop, redaction rectangles, and original/private SHA-256 belong in
the evidence manifest. No generated terminal panels presented as screenshots.
Redact account names, sidebars, tokens, unrelated text, host/guest identifying paths,
and unrelated conversations. Keep synthetic prompts and test IDs intact where safe.

The article should follow the experiments: command → observation → what that
observation changes → next test. Mention Cheater only as an application/practice
case, with its existing CTF Author writeup linked separately.
