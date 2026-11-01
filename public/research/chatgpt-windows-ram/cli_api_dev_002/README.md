# Native CLI development capture, September 29

This is one live WinPmem acquisition of the installed native Codex CLI's
**instrumented app-server stdio backend**, not the ChatGPT website, a browser
renderer, or a terminal-UI capture. The dedicated Research VM was restored before
the turn. The opaque guest relay and host-only observations are investigator
instrumentation; their copies are not native-backend attribution evidence.

The native backend was still running at acquisition. It completed the response
71.95618 seconds before acquisition started. WinPmem took 29.3383097 seconds.
The verified 7,147,094,016-byte raw image and its gzip archive remain private,
outside OneDrive. No whole image, account token, full RPC log, or general format
inspection output is included here.

## Result

- The public-wire RPC grammar found no complete relevant packet in either the
  native backend or the relay.
- A different, observed core-event grammar found three unique native records:
  `item_completed`, `task_complete`, and standalone `agentMessage`.
- Exact turn IDs join the user item to the completion. Thread ID, turn ID,
  user-message ID, prompt, and response all match the host observation.
- The standalone assistant object has no thread/turn fields. Its ID remains
  text-associated only, even though it matches the observed assistant ID.
- MemProcFS independently matches all four occurrences' exact bytes and physical
  translations. This does not prove exclusive ownership of the physical pages.
- The relay has a standalone assistant object but no linked candidate.

`recovery.json` is the final development replay. The earlier discovery output
and score are retained privately; this capture was never relabeled held out.
The separate method freeze happened after this development capture and before
the next synthetic turn.

## Replay the exact record bytes

From the research bundle root:

```bash
python3 method_cli_core_v1/replay_cli_core_fixture.py \
  --method method_cli_core_v1 \
  --fixture cli_api_dev_002/source-byte-fixture.json \
  --output /tmp/cli-core-record-replay.json
```

This constructs a tiny artificial image and map from the exact three reviewed
records, verifies source-byte and frozen-code hashes, then executes framing and
joining afresh. It produces three records and one candidate. It does not replay
the original full image or independently establish native process attribution.

For a privately acquired raw image, first inventory live native backends using
`windows.pslist` and `windows.cmdline`, checking exit times as well as names.
Generate each backend's own `windows.memmap`, then run it separately:

```bash
python3 method_cli_core_v1/cli_core_events.py \
  --image "$IMAGE" --memmap "$OUT/native-${PID}-memmap.json" \
  --output "$OUT/native-${PID}-core.json"
```

No prompt, answer, ID, or offset is supplied. The frozen v1 accepts compact JSON
beginning with `{"type"`, UTF-8/UTF-16LE, up to 1 MiB, in virtually adjacent
resident user-space pages. It rejects duplicate JSON keys, incomplete frames,
mapping overlaps, unknown types and ambiguous joins. A zero result says nothing
about other encodings, representations, swapped-out pages, or changed clients.

## Files

`acquisition.json` and `copy-verification.json` record the complete acquisition
and host verification. `score.json` records the sealed recovery hash and the
five-field/timestamp comparison. `memprocfs-records.json` records independent
rereads, not a second acquisition. `observer-comparison.json` reports only the
relay counts. `source-byte-fixture.json` contains the exact reviewed record
bytes, not surrounding memory. All identifiers and text belong to this synthetic
test. No account identity is inferred.
