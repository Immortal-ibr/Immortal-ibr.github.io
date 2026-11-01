# VMware saved-memory format check

This is the **pretest client-open** snapshot check, not the browser-turn recovery
method or a claim about account history. The saved `.vmem` is 6,073,352,192
bytes, but the selected guest mappings reach physical address 7,147,094,016.
It cannot be substituted for a flat WinPmem image when reading every mapped
page. Volatility supplies virtual-to-guest-physical rows; MemProcFS reads guest
physical addresses through the VMware snapshot metadata.

Select **all** active renderer PIDs from `windows.pslist` and `windows.cmdline`.
In Kali WSL Bash, set `VOL`, `SNAP`, `OUT`, and `PID` to your own Volatility
script, snapshot, private output directory, and image-selected renderer PID.
For each selected PID, obtain its map:

```bash
python3 "$VOL" -r json -f "$SNAP" windows.pslist > "$OUT/pslist.json"
python3 "$VOL" -r json -f "$SNAP" windows.cmdline > "$OUT/cmdline.json"
python3 "$VOL" -r json -f "$SNAP" windows.memmap --pid "$PID" > "$OUT/renderer-$PID-memmap.json"
```

On Windows, run the VMware-aware scanner against that map, then repeat for
every selected renderer. From this method directory, set `SDK`, `SNAP`, `MAP`,
`PID`, and `RESULT` to local inputs and a private output file:

```powershell
python scan_vmware_snapshot.py --sdk-root "$SDK" --vmem "$SNAP" --memmap "$MAP" --pid "$PID" --process-name ChatGPT.exe --output "$RESULT"
```

The scanner runs both bounded JSON grammars in UTF-8 and UTF-16LE. It stores
only counts and mapping-check results, never recovered record content. Zero
accepted records here means neither **tested format** was found in this
pretest state; it does not prove no conversation data existed. The
[reviewed ledger](../CLIENT_OPEN_SNAPSHOT_CONTROL_20261001.json) gives all ten
PID results in aggregate. The reader and schema checks can be exercised on
invented data with `python -m unittest test_scan_vmware_snapshot.py` from this
directory.

## Later exact-value check

[`count_known_physical.py`](count_known_physical.py) was used after the blind
Temporary Chat scans. It takes strings recorded from the guest-screen image,
scans MemProcFS-reported guest-physical ranges in UTF-8 and UTF-16LE, and
reports occurrence counts and physical offsets. Those are byte matches, not
accepted conversation records. Keep the known-value input and output private.
From this directory, with `KNOWN` and `RESULT` set to private files:

```powershell
python count_known_physical.py --sdk-root "$SDK" --vmem "$SNAP" --known-json "$KNOWN" --output "$RESULT"
```
