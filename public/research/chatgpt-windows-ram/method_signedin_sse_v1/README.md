# Signed-in Edge SSE turn method, development v1

This method was developed on the retained VMware state of one completed
synthetic teapot turn, then frozen before being applied to the later direct
WinPmem image of that **same** turn. The latter checks persistence across a
second acquisition, not a new-prompt validation. No prompt, response,
conversation ID, message ID or memory offset is passed to the scanner/joiner.

1. Use `windows.pslist` and `windows.cmdline` to select the active `msedge.exe`
   utility whose command line includes
   `--utility-sub-type=network.mojom.NetworkService`. The included
   `select_edge_network_service.py` requires exactly one such active PID.
   Generate its `windows.memmap` from the **same image**. Do not reuse a prior
   PID or map.
2. For a flat WinPmem raw image, run from this directory:

   ```bash
   python3 select_edge_network_service.py \
     --pslist "$PRIVATE/pslist.json" --cmdline "$PRIVATE/cmdline.json" \
     --output "$PRIVATE/network-selection.json"
   PID=$(jq -r '.selected_pid' "$PRIVATE/network-selection.json")
   python3 "$VOL" -q --offline -r json -f "$IMAGE" \
     windows.memmap --pid "$PID" > "$PRIVATE/network-memmap.json"
   python3 sse_event_records.py --image "$IMAGE" \
     --memmap "$PRIVATE/network-memmap.json" \
     --output "$PRIVATE/network-sse.json"
   python3 signedin_sse_turns.py --parsed "$PRIVATE/network-sse.json" \
     --output "$PRIVATE/network-turn.json"
   ```

   Keep both outputs outside the public repository: unfiltered SSE records
   from a signed-in browser can include unrelated account data.

3. A compact VMware `.vmem` cannot be substituted for the flat `$IMAGE` above.
   After selecting NetworkService and producing its `windows.memmap` from that
   saved state, run the included VMware-aware wrapper on Windows:

   ```powershell
   python -B .\scan_vmware_sse.py --sdk-root 'D:\path\to\MemProcFS' `
     --vmem 'D:\path\to\Research-Snapshot.vmem' `
     --memmap 'C:\private\network-memmap.json' --pid $NetworkPid `
     --output 'C:\private\network-sse.json'
   python -B .\signedin_sse_turns.py `
     --parsed 'C:\private\network-sse.json' `
     --output 'C:\private\network-turn.json'
   ```

   The wrapper uses Volatility's guest-physical mapping and MemProcFS's
   VMware-aware reads, with 32 virtual/physical sample comparisons. The
   published wrapper reproduced the development output's conversation, both
   message IDs, prompt, answer and stream digest on the saved image.

4. For the later flat image, I checked the same frozen grammar against *every*
   active Edge process, not just NetworkService. With `pslist.json` from that
   image, Bash, and `jq`, this is the repeatable selection and scan:

   ```bash
   mkdir -p "$PRIVATE/all-edge"
   jq -r '.[] | select(.ImageFileName == "msedge.exe" and .ExitTime == null) | .PID' \
     "$PRIVATE/pslist.json" > "$PRIVATE/all-edge/active-pids.txt"
   while IFS= read -r pid; do
     python3 "$VOL" -q --offline -r json -f "$IMAGE" \
       windows.memmap --pid "$pid" > "$PRIVATE/all-edge/$pid-memmap.json"
     python3 sse_event_records.py --image "$IMAGE" \
       --memmap "$PRIVATE/all-edge/$pid-memmap.json" \
       --output "$PRIVATE/all-edge/$pid-sse.json"
     python3 signedin_sse_turns.py --parsed "$PRIVATE/all-edge/$pid-sse.json" \
       --output "$PRIVATE/all-edge/$pid-turn.json"
   done < "$PRIVATE/all-edge/active-pids.txt"
   ```

   In the retained direct image, `pslist` selected 11 active Edge processes.
   Six complete events were in one renderer; every other process had zero
   complete events, and every join returned zero. This tests each resident
   process map independently, not an invented stream spanning processes.

   A separate hash-verified scan over the flat physical bytes framed only five
   of that renderer's six events. The sixth straddled virtually adjacent pages
   whose physical locations were far apart. The synthetic
   `test_virtual_continuity_recovers_event_that_flat_physical_scan_misses`
   reproduces this mapping distinction without publishing memory content.

The scanner frames only complete strict-JSON SSE `data:` events in resident
user mappings. It verifies the actual control-line bytes between adjacent
events before grouping them into one stream, and records exact byte hashes and
source spans. The joiner requires one user input, an ID ancestry chain through
any intermediate system message to one assistant, matching assistant markers,
content patches, a final status/end-turn patch, and a conversation-matched
stream completion. Missing, conflicting, or unknown content operations fail
closed. It never joins merely by the nearest text or timestamp.

Run `python -m unittest discover -p 'test_*.py' -v` in this directory to check
synthetic selection, framing, ancestry, patch assembly, and rejection paths. These tests
do not themselves prove recovery from the private image. The
[frozen-file manifest](../FROZEN_SIGNEDIN_SSE_V1.json) records the exact three
method hashes, and the [trial ledger](../EDGE_SIGNEDIN_VISIBLE_20261001.json)
reports the observed result without exposing signed-in records. The saved
VMware state yielded one full candidate; the later direct image yielded zero
with this unchanged grammar, even though post-hoc exact-text checks still
found the visible answer in an active renderer.
