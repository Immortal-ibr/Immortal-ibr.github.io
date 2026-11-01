# Bounded browser envelopes in VMware saved memory

[`browser_json_envelopes.py`](browser_json_envelopes.py) frames complete JSON
objects in resident user mappings and checks their shape. The
[`scan_vmware_envelopes.py`](scan_vmware_envelopes.py) wrapper reads those
mappings through MemProcFS because a VMware `.vmem` is not a flat physical
image. It checks the selected PID's browser name and samples Volatility's
virtual-to-physical translations before scanning. No known conversation text
or ID is an input.

From the repository root, set `SDK`, `SNAP`, `MAP`, `PID`, and `OUT` to your
local MemProcFS directory, `.vmem`, Volatility `windows.memmap -r json` output,
selected renderer PID, and a private output file. Run:

```powershell
python public/research/chatgpt-windows-ram/method_signedin_envelopes_v1/scan_vmware_envelopes.py --sdk-root "$SDK" --vmem "$SNAP" --memmap "$MAP" --pid "$PID" --process-name msedge.exe --output "$OUT"
```

Use `chrome.exe` for Chrome. The output contains full accepted records, which
can include account data. Keep it outside the blog repository. A zero means no
complete record in this grammar was accepted from that process map.
