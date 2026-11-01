---
title: "What Survives in Windows RAM? Part 3: Reconstructing a Native Codex CLI Turn"
published: 2026-11-01
description: "A native Codex CLI memory study: disk sessions, bounded RAM records, failed frozen methods, and a fresh four-field join."
tags: [DFIR, Memory Forensics, Windows, Codex, Volatility]
category: Research
image: /covers/post-chatgpt-windows-ram-memory-layers.png
draft: false
---

The browser tests in [Part 1](/posts/chatgpt-windows-ram-case-study/) and [Part 2](/posts/chatgpt-browser-state-changes/) followed Chromium renderer and service processes. Codex CLI has a native backend and local session files. An old prompt can reach a new process from disk, and the terminal or guest relay can hold copies of the same text. I wanted to see whether RAM from the native process could still link one prompt and response without giving the parser their text or IDs.

The first CLI probes counted known strings across four states of one turn. After that I reset a separate VM for new turns, learned the native record formats on development captures, froze each rule, and tested it on a fresh image. The field set here is different from the browser's `C/P/R/U/A` score: a CLI result can bind thread and turn IDs while leaving the assistant-message ID unresolved.

Research series: [1. Reconstructing a browser turn](/posts/chatgpt-windows-ram-case-study/) · [2. Browser state changes](/posts/chatgpt-browser-state-changes/) · **3. The native Codex CLI**

The linked trial **ledgers** are JSON audit records, not CLI session files. Each keeps the capture hash and process selection beside the parser output and the later host-observation score. In the fresh test, the host saw an assistant ID that the RAM records did not bind to the turn. The ledger keeps that ID out of the recovered field count.

## First, check what lands on disk

One `codex exec` request produced a 77,569-byte JSONL session containing the exact synthetic prompt and answer. Resuming the same session grew that file to 83,496 bytes and left both turns inside it. An ephemeral request created no normal session JSONL for its emitted session ID, although my own redirected stdout log still existed.

| Probe                      | Observation                                                                |
| -------------------------- | -------------------------------------------------------------------------- |
| `codex exec`             | Exact prompt and answer in a 77,569-byte session JSONL.                    |
| Resume that session        | File grew to 83,496 bytes and held both turns.                             |
| `codex exec --ephemeral` | No normal session JSONL for that session ID. Investigator stdout remained. |
| Interactive TUI preflight  | 75,629-byte JSONL with user and assistant `response_item` records.       |

OpenAI's troubleshooting documentation identifies [`$CODEX_HOME/sessions`](https://learn.chatgpt.com/docs/reference/troubleshooting) as the session-transcript location. This disk behavior matters when interpreting RAM: a resumed process can load old text from the saved session without any old process page surviving.

## The launcher mistake

For the active-TUI image, I initially selected only the visible `node.exe` launcher, PID 12820. The known-value scan returned zero prompt and zero answer hits.

That result was correct for the wrong process.

`windows.pslist` and `windows.cmdline` showed a native `codex.exe` child, PID 3916. Scanning its 37,884 user-space rows found 101 UTF-8 plus three UTF-16LE prompt hits and 36 UTF-8 plus one UTF-16LE answer hits. The Node launcher still had zero.

The original exploratory checks used two scripts with the known values supplied after capture. The [mapped-process scanner](/research/chatgpt-windows-ram/cli_ram_known_scan.py) counts exact prompt and answer bytes in the selected native and launcher user maps. The [physical-byte counter](/research/chatgpt-windows-ram/cli_ram_physical_counts.py) counts them across the whole image without assigning a process. The commands need a private trial directory containing `ground_truth.json`, `private/memory.raw`, `private/pslist.json`, and `private/cmdline.json`; the public result files alone cannot rerun them. From the directory containing the downloaded scripts, set `TRIAL` to that private directory and `VOL` to your local `vol.py`:

```bash
TRIAL=cli_tui_active_010
VOL=vol.py
python3 cli_ram_known_scan.py --trial "$TRIAL" --vol "$VOL"
python3 cli_ram_physical_counts.py --trial "$TRIAL"
```

These scripts were given the known values after capture. They count presence in mapped pages, but do not reconstruct a CLI turn blindly.

## Four states around one turn

I captured the same synthetic turn in four states:

1. interactive TUI still active
2. immediately after `/exit`
3. later idle, with no new CLI turn
4. resumed into a new process from the unchanged session JSONL.

| State           | Process-scoped observation                                                               | Whole-image observation             | What it means                                                                    |
| --------------- | ---------------------------------------------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------------------- |
| Active          | Native PID 3916 held the exact prompt and answer. Node PID 12820 held neither.           | 343+13 prompt and 84+3 answer hits. | Values were reachable through the active native process, but not blindly joined. |
| After `/exit` | Old PIDs absent from `pslist`, `psscan`, and `cmdline`.                            | 112+2 prompt and 64 answer hits.    | Bytes remained somewhere, but not attributable to the exited CLI.                |
| Later idle      | Old PIDs still absent, with no new turn.                                                 | 97+2 prompt and 54 answer hits.     | Reused-VM residue and disk-backed copies still prevent source attribution.       |
| Resumed         | New native PID 12848 held 15 prompt and 11 answer hits. The new Node launcher held zero. | 162+1 prompt and 115 answer hits.   | Consistent with the new native process loading the saved session file.           |

The four captures are four states of **one** turn, not four repetitions. The terminal had also displayed the known values before capture, so whole-image counts include an explicit alternative source.

## A clean follow-up: can I recover the CLI turn without its text?

The presence counts left an obvious hole: I had told the scanner what to find. I went back to this question in a dedicated Windows 10 Pro 22H2 VM, build 19045, with 5,792 MiB assigned RAM and native `codex-cli 0.158.0-alpha.2.1`.

I closed the target clients, saved a tools-ready snapshot before submitting anything, and restored it for the development capture. The snapshot reset the client state, though the signed-in account could still have older history. The observation and scoring logs stayed on the host. The intended request still entered the guest CLI, which retained its normal session behavior. An opaque guest relay connected the installed CLI's `app-server --listen stdio://` to that host over pinned TLS. The relay still copies bytes, so I examined its process separately. This experiment tested the instrumented native backend, not the terminal UI or a ChatGPT browser tab.

I generated the installed version's schema first:

```powershell
& $codex app-server generate-json-schema --out .\schemas
```

The [documented protocol](https://learn.chatgpt.com/docs/app-server#protocol) uses newline-delimited RPC messages. I expected `item/completed` and `turn/completed` records with thread and turn IDs to survive together. My [first parser](/research/chatgpt-windows-ram/method_cli_core_v1/cli_rpc_records.py) frames complete JSON objects in the mapped pages, then accepts only the public RPC shapes it recognizes. It found **zero complete relevant records** in both the native backend and relay.

The next step was to inspect other *complete, framed JSON objects*, not search for the known answer. That exposed a different native serialization:

| Surviving record                               | Fields it actually supplies                                         |
| ---------------------------------------------- | ------------------------------------------------------------------- |
| `item_completed`, containing `UserMessage` | `thread_id`, `turn_id`, user-message ID, exact prompt           |
| `task_complete`                              | `turn_id`, `last_agent_message`, start/end times and duration   |
| standalone `agentMessage`                    | assistant-message ID and final text, **no thread or turn ID** |

Notice `UserMessage`, not the public API's `userMessage`. These are formats observed in this client build, not a documented public contract. A `role: "user"` object alone was also unsafe: the native model input contained generated environment context as well as the actual prompt, with a different set of message IDs.

That gives the parser a route to the prompt without an offset or a known conversation ID. It scans the mapped user pages for compact JSON beginning with `{"type"`, frames each object with quote/escape-aware delimiter handling, validates the JSON, and accepts only those three record types. UTF-8 and UTF-16LE are supported, with a 1 MiB byte cap. Virtually adjacent pages may be physically far apart, so the memmap supplies each physical read. A missing virtual page stops the record rather than being silently skipped.

The join then follows the **exact turn ID** from the user item into `task_complete`. It accepts a candidate only when that turn has one thread binding, one user variant and one completion variant. Duplicate copies keep their source addresses. Conflicting copies stay ambiguous. There is no “nearest response” or “newest PID” rule.

For the development image, `pslist`, exit times, command lines and the guest inventory identified one live native backend: PID 9456, parent relay PID 8180. Its map contained 21,344 user-space rows. I excluded 115,322 kernel rows. In Bash, I ran the [core-v1 method](/research/chatgpt-windows-ram/method_cli_core_v1/cli_core_events.py) from a directory containing its downloaded method folder, with `VOL` pointing to Volatility, `IMAGE` to the verified raw image, and `OUT` to a private output directory:

```bash
python3 "$VOL" -r json -f "$IMAGE" windows.memmap --pid 9456 > "$OUT/native-9456-memmap.json"

python3 method_cli_core_v1/cli_core_events.py --image "$IMAGE" --memmap "$OUT/native-9456-memmap.json" --output "$OUT/native-core.json"
```

The [core parser](/research/chatgpt-windows-ram/method_cli_core_v1/cli_core_events.py) receives only the raw image and map. Its [frozen rules](/research/chatgpt-windows-ram/method_cli_core_v1/FROZEN_METHOD.json) are downloadable. The [case bundle](/research/chatgpt-windows-ram/cli_api_dev_002/README.md) includes the exact three synthetic record bytes and a replay command.

The native result was three unique records and one candidate. After sealing the output hash, I compared it with the host observation: **thread ID, turn ID, user-message ID, prompt and response all matched**. These are a different five-field set from the browser score above: the CLI result includes a turn ID, but does not independently bind the assistant-message ID.

The prompt asked for a fictional lighthouse, `174 + 289`, and a three-word name not supplied in the request. The recovered response introduced **Silver Lantern Cove** and the result `463`. Both complete texts are in the [recovered turn](/research/chatgpt-windows-ram/cli_api_dev_002/turn-for-viewer.json), rather than just their test marker.

Why not count the assistant ID as a sixth field? Its standalone object contained the same answer, but no thread or turn. Two different turns can have identical answers. An exact text match is useful corroboration, not an identifier link. The script explicitly leaves that ID unbound.

The relay had one standalone assistant object and **zero linked candidates**. MemProcFS independently reread all four occurrences of the three native records: every byte digest and physical translation matched.

![The core-v1 parser run on the complete development memory image, returning three complete records, one linked turn, and one unbound agent object.](/research/chatgpt-windows-ram/screenshots/87-cli-dev-parser-direct.png)

*Direct rerun on the complete lighthouse image and its native-process map. The records and join matched the saved private result. The later comparison with the host trace supplied the five-field score.*

This capture is **development**, because I learned its grammar from it. I froze the method only afterward, before submitting the next test turn.

## The first fresh test breaks that rule

I restored the same tools-ready snapshot, and submitted a new prompt about a fictional observatory. The native backend, PID 4528, was still running.

The unchanged parser returned **zero candidates**.

The host observed a completed answer, and the transferred image passed its full decompression hash check. The parser recovered `task_complete` and a standalone `agentMessage`, but no complete `item_completed` user record. Seven occurrences of those two surviving records passed the independent MemProcFS byte and translation checks. The answer and turn ID survived without an accepted path back to the prompt or thread.

The [failed core-v1 case](/research/chatgpt-windows-ram/cli_api_heldout_001/README.md) retains that result. Its `observation-not-recovery.json` is explicitly host ground truth, not a recovered conversation. The roughly two-second delay versus the development run's 72 seconds is not a controlled timing experiment, so I cannot conclude that either delay caused the difference.

![The unchanged core-v1 parser running on the fresh observatory memory image and returning zero joined turns.](/research/chatgpt-windows-ram/screenshots/88-cli-core-fresh-direct.png)

*Direct rerun on the complete observatory image. Two core records survived, but they did not include the user item needed for the join. The records and zero-candidate result matched the original private output.*

## A second route: model input is not an API user item

Only **after sealing the failure** did I inspect other framed JSON from this image. A complete `turn/completed` RPC record survived, but its `items` contained only the final assistant item. That bound the answer and assistant ID to a thread and turn. It still supplied no prompt. Merely switching back to the public-RPC parser produced no complete turn.

The useful input was in a different representation. Two objects had `type: "message"` and `role: "user"`. One was generated environment context. The other contained the actual prompt. Their metadata made the distinction possible without knowing either text:

```json
{
  "internal_chat_message_metadata_passthrough": {
    "turn_id": "01a0eb74-759b-7711-9962-91a21e213040",
    "create_time": 1790656675.4543948,
    "content_item_kinds": ["user.text"]
  }
}
```

This is a selected field from the recovered input, not a complete record. The excluded context used `environments.environment_context` instead of `user.text`. The [new parser](/research/chatgpt-windows-ram/method_cli_model_input_v1/cli_model_turns.py) requires the tag list to align with every text content part. It does not accept arbitrary `role: "user"` objects as human prompts. This [metadata](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs) is an **observed internal format**, not a documented OpenAI API guarantee.

Now the join is straightforward. The tagged input supplies the prompt and turn ID. The terminal RPC supplies the **same turn ID**, thread ID, final assistant ID and answer. One input variant, one final answer variant and one thread binding produce a candidate. Conflicts remain ambiguous. I ran the [model-input method](/research/chatgpt-windows-ram/method_cli_model_input_v1/cli_model_turns.py) from the directory containing its downloaded folder:

```bash
python3 "$VOL" -r json -f "$IMAGE" windows.memmap --pid 4528 > "$OUT/native-4528-memmap.json"

python3 method_cli_model_input_v1/cli_model_turns.py --image "$IMAGE" --memmap "$OUT/native-4528-memmap.json" --output "$OUT/native-model-input.json"
```

This recovered two complete records and one candidate. Its exact thread ID, turn ID, prompt, response and assistant ID matched the host observation. MemProcFS matched both source records, and the separately parsed relay supplied none. The answer introduced **Silver Lantern Drift** and `389 + 527 = 916`. The complete texts and identifiers are in the [model-input case bundle](/research/chatgpt-windows-ram/cli_api_001_model_development/README.md).

![The model-input parser running on that same complete observatory image, excluding a context record and returning one joined turn.](/research/chatgpt-windows-ram/screenshots/89-cli-model-development-direct.png)

*This method was developed after the core-v1 failure on the same image. The terminal shows its own result, not a second fresh test. Its records and join matched the saved private output.*

There is an identifier trap here. The input's `id` was `msg_01a0eb74-7e7e-7192-9898-83a486676e21`. The API user-item ID was `01a0eb74-7e7e-7192-9898-83b50f5014b7`. They are **different IDs**, not alternate formatting of one value. The parser preserves the first as `model_input_message_id` and does not report the missing API user-item ID as recovered. That model-input ID is supported by RAM bytes, but was not independently observed in the host's public-RPC trace. Likewise, `create_time` describes model-input metadata, not when the human pressed Enter.

| Method         | Independently scored linked fields               | Field it does not recover      |
| -------------- | ------------------------------------------------ | ------------------------------ |
| Core-v1        | thread, turn, API user-item ID, prompt, response | thread/turn-bound assistant ID |
| Model-input-v1 | thread, turn, prompt, response, assistant ID     | API user-item ID               |

The alternate result is **development on the failed image**, not a second held-out success. Core-v1's result stays zero.

The input's `user.text` tag marks the human prompt. Its `turn_id` matches `turn.id` in the terminal RPC, which supplies the final assistant item. The [reviewed input and completion records](/research/chatgpt-windows-ram/cli_api_001_model_development/README.md) retain those fields.

## The next image: each method finds only half

After another restore, I submitted a new prompt about a fictional museum. Both the [core](/research/chatgpt-windows-ram/method_cli_core_v1/cli_core_events.py) and [model-input](/research/chatgpt-windows-ram/method_cli_model_input_v1/cli_model_turns.py) parsers were already frozen. The response completed normally.

Core-v1 again recovered `task_complete` and a standalone assistant object, but no complete user item: **zero candidates**. Model-input-v1 recovered the tagged human prompt, but no accepted terminal RPC partner: **zero candidates**. MemProcFS also matched every accepted record occurrence. The result is reported separately for [core-v1](/research/chatgpt-windows-ram/cli_api_heldout_002_core/README.md) and [model-input-v1](/research/chatgpt-windows-ram/cli_api_heldout_002_model/README.md), using the same raw image.

The two representations joined a turn on the development image, but did not both survive in accepted form on the next image. Taking a thread ID from the host log or attaching the nearest answer in memory would invent a RAM link, so I kept this result partial.

The museum image still had a partial link. In the two recovery files, the tagged input's metadata and `task_complete` both carry turn ID `01a0eb9a-5b8d-7161-9054-97832028d225`. The first supplies the prompt, the second `last_agent_message`. That associates turn, prompt and response through a RAM-derived ID, without the host's text. Neither supplies the missing thread binding here, and the standalone assistant object does not bind its ID to that turn. This is partial `T/P/R` evidence, not the five-field candidate either frozen method was scored on.

| Capture     | Core-v1                        | Model-input-v1                 | Experimental role                                   |
| ----------- | ------------------------------ | ------------------------------ | --------------------------------------------------- |
| Lighthouse  | 1 candidate, five exact fields | Not tested                     | Core grammar development                            |
| Observatory | 0 candidates                   | 1 candidate, five exact fields | Fresh core test. Model grammar developed afterward. |
| Museum      | 0 candidates                   | 0 candidates                   | Fresh test of both frozen methods                   |

## The request object I had ignored

The two frozen grammars still had zero candidates, but I had not exhausted the museum image. I went back through complete JSON objects they had rejected. One 16,184-byte object in the native backend began with `"type":"response.create"`. Its `client_metadata` held both `thread_id` and `turn_id`. Its `input` array held generated environment context and one message tagged `user.text` for that turn. The existing `task_complete` object carried the same turn ID and the final response. The thread binding had survived in a record I had ignored.

The [new joiner](/research/chatgpt-windows-ram/method_cli_request_core_v1/cli_request_core_turns.py) reads only bounded, strict JSON from the native process's resident user mappings. It requires exactly one tagged human input whose metadata turn ID equals the request's turn ID, then one unambiguous `task_complete` with that ID. A loose prompt string, a nearby answer, or a plain `role: "user"` object cannot satisfy it. The [method and replay tests](/research/chatgpt-windows-ram/method_cli_request_core_v1/README.md) show the record rule and the command. The [freeze manifest](/research/chatgpt-windows-ram/FROZEN_CLI_REQUEST_CORE_V1.json) records the code hashes.

```text
response.create.client_metadata.turn_id
    = input[tagged user.text].internal_chat_message_metadata_passthrough.turn_id
    = task_complete.turn_id
```

The thread ID comes from that same request's `client_metadata`. The tagged input supplies the prompt, and `task_complete.last_agent_message` supplies the response.

With the image-selected native PID's `windows.memmap` already saved, I ran the [request/core parser](/research/chatgpt-windows-ram/method_cli_request_core_v1/cli_request_core_turns.py) from the directory containing its downloaded folder:

```bash
python3 method_cli_request_core_v1/cli_request_core_turns.py --image "$IMAGE" --memmap "$OUT/native-9144-memmap.json" --output "$OUT/request-core-private.json"
```

I developed this on the museum image **after** the frozen-method failure, then froze the code before rechecking the two earlier retained images. It found one request/completion pair in each native backend and none in the separately mapped relays. Every accepted record occurrence matched MemProcFS bytes and translations. The parser received no ground-truth values. I hashed each output before the scorer read the retained host trace:

![The request/core parser run directly on the complete museum memory image, returning two bounded records and one joined turn.](/research/chatgpt-windows-ram/screenshots/90-cli-museum-parser-direct.png)

*The museum image was where I developed this rule. This rerun's records and join matched the original private result. The later fresh test below is the prospective check.*

| Existing image | Native request + completion | Exact host fields              | MemProcFS record checks | Relay candidates |
| -------------- | --------------------------: | ------------------------------ | ----------------------: | ---------------: |
| Lighthouse     |                      1 pair | thread, turn, prompt, response |                     2/2 |                0 |
| Observatory    |                      1 pair | thread, turn, prompt, response |                     4/4 |                0 |
| Museum         |                      1 pair | thread, turn, prompt, response |                     2/2 |                0 |

The [retrospective ledger](/research/chatgpt-windows-ram/CLI_REQUEST_CORE_RETROSPECTIVE_20261001.json) has each older image hash, parser output hash, native-process result and relay control. All three captures predate the request/core method, so these checks are retrospective. The museum scores for core-v1 and model-input-v1 remain zero. The new route recovers four independently checked fields. Its `model_input_message_id` is not the API user-item ID, though, and `task_complete` does not bind the assistant-message ID. I leave that ID unassigned even when a standalone object's text matches.

## A new turn after the freeze

All three images in that table predated the request/core grammar. For a fresh test, I left its source hashes alone, reset the VM, and sent the installed native CLI a new request: “why a brass hourglass cannot detect earthquakes,” ending with the deliberately odd words `cobalt fern 94`. The completed answer explained that an hourglass measures elapsed time rather than ground motion, and it ended with those same words.

I inspected its process list and command lines. They identified native `codex.exe` PID **5968** running `app-server --listen stdio://`, with a separate PowerShell relay at PID **5708**. With `VOL`, `IMAGE`, and `OUT` set to this trial's verified image and private output directory, I ran these from the directory containing the downloaded [request/core parser](/research/chatgpt-windows-ram/method_cli_request_core_v1/cli_request_core_turns.py):

```bash
python3 "$VOL" -r json -f "$IMAGE" windows.pslist > "$OUT/pslist.json"
python3 "$VOL" -r json -f "$IMAGE" windows.cmdline > "$OUT/cmdline.json"
python3 "$VOL" -r json -f "$IMAGE" windows.memmap --pid 5968 > "$OUT/native-memmap.json"
python3 method_cli_request_core_v1/cli_request_core_turns.py --image "$IMAGE" --memmap "$OUT/native-memmap.json" --output "$OUT/native-recovery-private.json"
```

The unchanged parser found two complete native records, a 16,084-byte `response.create` and a 303-byte `task_complete`, and **one** joined turn. The request's five input messages included three `developer` items and two with `role: "user"`. One of those two was tagged `environments.environment_context`, while only the actual prompt was tagged `user.text`. This is a real example of why filtering on role alone would choose the wrong input. I mapped PID 5708 and ran the same parser separately: zero complete records, zero candidates. I sealed the native output hash *before* comparing it with the host trace. Thread ID, turn ID, prompt and response matched **4/4**. The [fresh-trial ledger](/research/chatgpt-windows-ram/CLI_REQUEST_CORE_PROSPECTIVE_20261001.json) records the new image hash, native and relay outputs, and the separate 4/4 host comparison without publishing the signed-in process's unfiltered request.

![The request/core parser run directly on the verified fresh CLI memory image, returning two complete records and one joined turn.](/research/chatgpt-windows-ram/screenshots/86-cli-fresh-parser-direct.png)

*Direct rerun on the complete image and its Volatility map. The recovered records and join matched the original private parser output. I compared the four fields with the host observation afterward.*

The request/core join worked on a turn that was not available when I designed it. That is the prospective check the three older images could not provide. Core-v1 and model-input-v1 still failed their earlier tests, and this grammar still leaves the assistant-message ID unbound.

The host's event log did receive an `item/completed` notification carrying an `agentMessage.id` alongside the thread, turn, and answer. I checked the verified image separately for that *record shape*. The native CLI and guest relay user maps yielded no complete RPC notification, while a full-physical scan found only a thread-result object with an empty `turns` array. The host can name the assistant item, but the RAM join cannot borrow that ID. The [assistant-ID boundary check](/research/chatgpt-windows-ram/CLI_ASSISTANT_ID_BOUNDARY_20261001.json) keeps the observation and memory evidence separate.

## Conclusion: what the native captures established

The native CLI did not leave one reliable record shape across the captures. Core-v1 linked the lighthouse turn, then missed the user item in the next fresh image. The model-input rule recovered that next prompt and answer, then found only half of the museum turn. The museum image led me to a `response.create` request that carried the missing thread binding. I froze the request/core rule and used it on a new turn. It joined the thread ID, turn ID, prompt, and response, and all four matched the separately recorded host observation.

That method did not bind the assistant-message ID. A standalone answer object and a matching host notification could not supply the missing RAM relationship. The disk probes exposed a separate source of confusion: resuming a saved CLI session can put old text in a new process. The result I can stand behind is a four-field native turn from mapped RAM, with its assistant ID left open.

Across the series, the strongest browser captures gave a five-field prompt–answer–message join, and the fresh native CLI capture gave a four-field thread–turn–prompt–answer join. Closing, reloading, and navigating changed which records could still be joined, even when exact text remained in memory. The useful question at acquisition time was which process still held a complete record and which of its own IDs still connected the pieces.

## Evidence and references

The [series evidence index](/posts/chatgpt-windows-ram-case-study/#evidence-and-audit-files-for-the-series) includes the method freezes, retained synthetic records, image hashes, and separate host scores. The [follow-up manifest](/research/chatgpt-windows-ram/FOLLOWUP_MANIFEST_20260929.json) records the native development and fresh captures. The [prospective request/core ledger](/research/chatgpt-windows-ram/CLI_REQUEST_CORE_PROSPECTIVE_20261001.json) records the last fresh turn and its four independently checked fields.

1. OpenAI, [*Codex app-server protocol*](https://learn.chatgpt.com/docs/app-server) and [*internal message metadata types*](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs). The latter is current upstream source, not a verified source match for the inventoried binary. The method freeze and record fixtures document what was tested.
2. OpenAI, [*Codex troubleshooting*](https://learn.chatgpt.com/docs/reference/troubleshooting), including the session-transcript location.

This ends the three-part series. Return to [Part 1: Browser reconstruction](/posts/chatgpt-windows-ram-case-study/) or [Part 2: Browser state changes](/posts/chatgpt-browser-state-changes/).

Research series: [Part 1: Browser reconstruction](/posts/chatgpt-windows-ram-case-study/) · [Part 2: Browser state changes](/posts/chatgpt-browser-state-changes/) · **Part 3: The native Codex CLI**
