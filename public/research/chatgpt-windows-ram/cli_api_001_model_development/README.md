# Model-input fallback developed from the first frozen core failure

This uses the **same** September 29 raw image as `cli_api_heldout_001`, not a
new capture. Core-v1 returned zero candidates prospectively. Its result remains
zero. Only after that score was sealed did broader structural inspection expose
a tagged model input and one terminal RPC record. This alternate method is
therefore **development** on this image.

The two complete records share an exact turn ID. The model input's
`internal_chat_message_metadata_passthrough.content_item_kinds` is `["user.text"]`.
A different `role: "user"` record carried generated environment context and was
excluded. The terminal `turn/completed` record supplies thread ID, turn ID,
final assistant ID and response. One input variant, one final assistant variant
and one thread binding produce one candidate without known text/IDs/offsets.

After sealing the recovery, the host log independently matched **thread ID,
turn ID, prompt, response and assistant ID**. These are NOT core-v1's five fields:
the API user-item ID is missing. The model-input message ID has its own namespace,
is different from that observed API user-item ID, and is not independently scored
against a model-input ground-truth trace. Its `create_time` is not a human
submission timestamp. No account identity is claimed.

MemProcFS independently matched the exact bytes and physical translations of
both accepted records. The opaque transport relay had zero accepted records and
zero linked candidates. This establishes mapped reachability in this image, not
exclusive page ownership. The complete raw image and archive remain private;
unfiltered format-inspection and RPC logs are not published.

The alternative was frozen at `2026-09-29T05:08:23.963366Z`, after this capture
and before a separate fresh test. The freeze does not turn this development case
into held-out validation.

## Replaying only the reviewed source bytes

From the public research bundle root:

```bash
python3 method_cli_model_input_v1/replay_cli_model_fixture.py \
  --method method_cli_model_input_v1 \
  --fixture cli_api_001_model_development/source-byte-fixture.json \
  --output /tmp/model-input-development-replay.json
```

The helper checks frozen source and exact record-byte digests, then reruns framing
and joining on a tiny **artificial** image/map. It must produce two records and
one candidate with the fixture fields equal. This is not a replay of original
process selection or whole-RAM extraction. `turn-for-viewer.json` is only a
readable projection; `recovery.json` retains the supporting addresses and hashes.

`input-record-for-viewer.json` and `terminal-record-for-viewer.json` select the
two recovered payloads for a side-by-side GUI view of their matching turn IDs.
Each names and hashes the same `recovery.json` source. They are presentation
copies, not new records, a new capture, or an independently validated success.
