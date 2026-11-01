# Request/core RAM join (post-hoc v1)

This method was written after inspecting the museum image, then frozen before
rechecking the two earlier retained CLI images. The same frozen code was later
run on one genuinely new turn and image; that separate prospective result is
in the [fresh-trial ledger](../CLI_REQUEST_CORE_PROSPECTIVE_20261001.json).
It receives a raw image and a matching `windows.memmap`
for one image-selected native `codex.exe` PID; no known prompt, answer, ID, or
offset is supplied. Run the relay PID separately.

From the blog repository root in Kali WSL, after selecting the native PID from
`windows.pslist` and `windows.cmdline`:

```bash
VOL='/mnt/d/Cyber Security/tools/DFIR/volatility3-2.8.0/volatility3-2.8.0/vol.py'
IMAGE='/path/to/private/memory.verified.raw'
OUT='/path/to/private/analysis'
PID=9144 # Example from the museum image; select the PID from your own image.

python3 "$VOL" -q --offline -r json -f "$IMAGE" \
  windows.memmap --pid "$PID" > "$OUT/native-memmap.json"
python3 public/research/chatgpt-windows-ram/method_cli_request_core_v1/cli_request_core_turns.py \
  --image "$IMAGE" --memmap "$OUT/native-memmap.json" \
  --output "$OUT/request-core-private.json"
```

The parser reads bounded, strict JSON objects through virtually adjacent
resident user pages. It accepts `response.create` only when `client_metadata`
supplies thread and turn IDs and the `input` array has exactly one `user.text`
message for that turn. It joins a single `task_complete` on the exact turn ID.
Duplicate copies retain their source addresses; conflicting thread, input, or
completion variants are not resolved by proximity or text similarity.

`response.create` may contain unrelated context. Keep its raw output private.
The [retrospective ledger](../CLI_REQUEST_CORE_RETROSPECTIVE_20261001.json)
and fresh-trial ledger publish counts and field-level scores without the object
or account data.
The method's [freeze manifest](../FROZEN_CLI_REQUEST_CORE_V1.json) gives the
source hashes. To replay the join logic on wholly invented values:

```bash
cd public/research/chatgpt-windows-ram/method_cli_request_core_v1
python3 -m unittest test_cli_request_core_turns.py
```

The model-input message ID recovered here is not the API user-item ID. The
completion text is linked by turn ID, but its assistant-message ID is not
independently bound by this pair of records.
