# Prospective failure of frozen CLI core-v1

This live WinPmem image followed an independent restore of the tools-ready
Research VM. The synthetic turn was submitted after core-v1 was frozen at
2026-09-29T04:33:06.111954Z. Core-v1's exact three source hashes and 1 MiB cap
were verified by the scorer. No known prompt, answer, ID or offset entered the
RAM parser.

The host observed completion at 04:38:00.300528Z. Acquisition ran from
04:38:02.4642788Z to 04:38:31.5517605Z: a 2.16375-second delay, a 29.087482-second
interval, and exit code 0. Full archive and decompressed-image verification
passed. Both full files remain private outside OneDrive.

Native backend PID 4528, parent relay PID 7384, was live in the guest inventory
and image. Volatility supplied 21,441 resident user-space rows; 113,949 kernel rows
were excluded. MemProcFS matched all 32 deterministic mapping/byte samples.

## Frozen result: zero linked candidates

Core-v1 recovered two unique records:

- `task_complete`: the exact answer and turn ID, in three occurrences;
- standalone `agentMessage`: final answer and assistant ID, in four occurrences.

It did not recover the required `item_completed`/`UserMessage` record. Without
that record, core-v1 had no accepted thread/user/prompt side of the join. The
native backend and relay both yielded zero candidates. MemProcFS independently
matched all seven native occurrences' exact bytes and physical translations.
This is not a missing-process or corrupted-copy result.

`observation-not-recovery.json` contains the HOST-observed synthetic turn for
comparison. Those fields must not be presented as the frozen parser's recovery.
`recovery.json` and `score.json` preserve the actual zero-candidate result.
The exact two recovered record bytes are in `source-byte-fixture.json`.

For a GUI screenshot, `result-for-viewer.json` selects the accepted record types,
payloads and zero candidate count from `recovery.json`. It includes that source's
digest and does not load `observation-not-recovery.json`.

Replay from the bundle root:

```bash
python3 method_cli_core_v1/replay_cli_core_fixture.py \
  --method method_cli_core_v1 \
  --fixture cli_api_heldout_001/source-byte-fixture.json \
  --output /tmp/cli-core-failure-replay.json
```

The artificial tiny-image replay yields two records and zero candidates. It
verifies framing/joining only, not extraction from the original complete image.

## Post-score investigation, not a repaired validation score

A broader structural inspection found a complete `turn/completed` RPC frame
with thread ID, turn ID and a final assistant item, but no user item. The public
RPC-only joiner therefore also returned zero complete candidates.

Two other complete model-input objects had `role: "user"`. Their internal
metadata distinguished `environments.environment_context` from `user.text`.
The latter has the exact prompt, a model-input message ID and the same turn ID.
The model-input ID is different from the API user-item ID observed on the host.

That discovery led to a SECOND development method joining the tagged input to
the terminal RPC by exact turn ID. It may bind C/T/P/R/A without recovering the
API user-item ID U. Learning that grammar from this image makes this image
development data for the second method. It remains a failed prospective test of
core-v1. The two scores and identifier namespaces must never be combined.

The 2-second versus 72-second acquisition delay differs from the development
capture, but these are not a controlled delay experiment. No causal timing or
general recovery-rate claim follows from one success and one failure.
