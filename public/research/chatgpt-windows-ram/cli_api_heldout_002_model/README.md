# First fresh test of frozen model-input-v1: zero candidates

This shares the capture reported in `cli_api_heldout_002_core`. It is the first
fresh capture submitted after model-input-v1 was frozen at 05:08:23.963366 UTC.
Its code hashes and cap were checked against that pre-submission manifest during
post-recovery scoring. The native backend remained active and its response
completed; full image/transfer/decompression integrity checks passed.

The unchanged model-input method accepted **one tagged human input record**, but
no complete accepted terminal RPC record. Consequently it produced **zero linked
candidates**. Generated user-role environment context was excluded. MemProcFS
independently matched the one input record's exact bytes and physical translation.
The opaque relay had zero accepted model records and zero candidates.

The development result on the previous image depended on both representations
surviving together. Here the prompt-side representation survived without its
accepted answer-side partner. This is a format/retention boundary of the tested
parser, not proof that all answer bytes disappeared from RAM. No repair against
this image is counted as a held-out success. No API user-item ID or account
identity is recovered.

A post-score manual comparison with `cli_api_heldout_002_core/recovery.json`
finds the same turn ID in this tagged input and its `task_complete` record. Those
two records associate T/P/R, but do not supply a RAM-derived thread binding or
thread/turn-bound assistant ID. This partial cross-representation link does not
change either frozen method's zero five-field candidate count.

`partial-link-for-viewer.json` provides a compact GUI view of this post-score
comparison, with both zero counts, the equal turn IDs, the recovered prompt and
completion text, and the two source-file digests. It does not read host ground
truth or supply the missing thread/assistant binding.

`observation-not-recovery.json` contains the separate synthetic host observation,
not a RAM reconstruction. From the public bundle root:

```bash
python3 method_cli_model_input_v1/replay_cli_model_fixture.py \
  --method method_cli_model_input_v1 \
  --fixture cli_api_heldout_002_model/source-byte-fixture.json \
  --output /tmp/model-first-fresh-replay.json
```

The exact source bytes must frame one record and join zero candidates. This is a
tiny artificial image/map replay, not original process selection or full-RAM
extraction. The complete acquisition and archive remain private.
