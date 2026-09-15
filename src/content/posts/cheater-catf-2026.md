---
title: "Official Cheater CATF 2026 DFIR Writeup"
published: 2026-09-12
description: "A full reconstruction of an anonymous ChatGPT chat from a Windows memory image: this is a writeup for my DFIR challenge in CAT CTF"
tags: [DFIR, Memory Forensics, Browser Forensics, Windows, Volatility, Discord, ChatGPT]
category: CTF Author
image: /covers/post-cheater.png
event: CATF 2026
challengeUrl: https://mega.nz/file/O0hHjAQD#NGzldU4A7xJUrnIYiX948dkUKXp0mm7XEvwGkkKsqZs
draft: false
---

Hello everyone,

This time I am writing more of a methodology than a writeup. I wanted to make a
simple and fun challenge after I was inspired by a research paper, so I present
**Cheater**, my DFIR challenge for CATF 2026.

Description:

> A university receives an unusually good assignment from a student whose
> earlier work was always incomplete. The student denies getting unauthorized
> help, so the laptop is confiscated. 
> 
> Can we tell whether he is lying?



The challenge files are available from the [primary download](https://mega.nz/file/O0hHjAQD#NGzldU4A7xJUrnIYiX948dkUKXp0mm7XEvwGkkKsqZs)
and [Google Drive mirror](https://drive.google.com/file/d/1Zxam9bZhkFPXrx0qQCIJAmiD_rtZxjPe/view?usp=sharing).

| Challenge | Details |
| --- | --- |
| Name | Cheater |
| Category | DFIR / Windows memory forensics |
| Author | `Immortal_ibr` |
| Evidence | `dump.mem` |
| Flag format | `CATF{Flag}` |


## Process triage: the first tempting mistake

I started with the active process list and then asked `windows.cmdline` about the
interesting children.

```bash
python3 vol.py -f dump.mem  windows.pslist.PsList
python3 vol.py -f dump.mem  windows.cmdline.CmdLine --pid 4080
python3 vol.py -f dump.mem  windows.cmdline.CmdLine --pid 6612
python3 vol.py -f dump.mem  windows.cmdline.CmdLine --pid 1472
```
![pslist](/writeups/cheater/screenshots/01-process-list.png)
![pslist](/writeups/cheater/screenshots/02-renderer-command-lines.png)


| PID | Process | Recovered role | Start time (UTC) |
| ---: | --- | --- | --- |
| 3064 | `chrome.exe` | Chrome browser process | 10:50:05 |
| 1196 | `chrome.exe` | network utility process | — |
| 6612 | `chrome.exe` | renderer, client ID 129 | 16:11:04 |
| 1472 | `chrome.exe` | renderer, client ID 133 | 16:11:13 |
| 3740 | `Discord.exe` | Discord/Electron main process | 10:52:26 |
| 4080 | `Discord.exe` | renderer, client ID 6 | 10:52:38 |

Looking at the running processes, I had two obvious hypotheses of how he could have cheated. The student
could have asked a friend for the solution. That would require a communication
channel, and Discord is the clearest candidate in this process list.

The other possibility is that he used an AI assistant or searched the web for
help. I could look for a dedicated ChatGPT or Claude client, or for an AI CLI
running in a terminal, but there is no reason the activity had to happen through
either of them, it could all be inside a browser tab. That makes Chrome the
second candidate.

At this stage, Discord and Chrome are the leads.

The command lines expose the renderer client IDs and Discord `1.0.9256`. These details matter because
the client-side formats parsed below can change.

Chrome 3064 and Discord 3740 are the main
processes, but the web documents live in their renderers.

I dumped all three candidate renderers:

```bash
python3 vol.py -f dump.mem  -o "$OUT/renderer-6612" windows.memmap.Memmap --pid 6612 --dump
python3 vol.py -f dump.mem  -o "$OUT/renderer-1472" windows.memmap.Memmap --pid 1472 --dump
python3 vol.py -f dump.mem  -o "$OUT/discord-renderer-4080" windows.memmap.Memmap --pid 4080 --dump
```

With `--dump`, `windows.memmap` concatenates resident mappings into a derived
file. Without it, the table retains each virtual address, physical address,
size, and derived-file offset.

## Do not choose a renderer by PID or age

Chrome renderer 1472 started nine seconds after 6612, but the newest renderer is
not necessarily the tab that completed the request. It may still hold copied
draft state or cached strings from another page.

This is just a way to try to have an indicator on which one is the right one, so don’t read too much into it (unless you want to)

The comparison script memory-maps both dumps and locates four schema anchors:
the composer key, `terminal-received`, `data-assistant-stream-block`, and the
unauthenticated conversation route. A match is only a lead. Composer candidates
must survive the Mojo pointer and array-header checks explained later, HTML
candidates must parse as one bounded element and routes must parse to the
expected host, path, and query.

For anyone who wants the format details, see the
[Web Storage standard](https://html.spec.whatwg.org/multipage/webstorage.html),
Blink's DOM Storage [`KeyValue` definition](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/public/mojom/dom_storage/storage_area.mojom),
and Chromium's [Mojom wire-format specification](https://chromium.googlesource.com/chromium/src/+/HEAD/mojo/docs/wire_format_spec.md).

The script here accepts a completed turn only when a
committed assistant block, its resume token, `assistant-content-started`, and a
terminal control repeat the same conversation, operation, final-message, and
pending-message IDs.

| Validated evidence | PID 1472 | PID 6612 |
| --- | ---: | ---: |
| raw composer-key occurrences (leads only) | 3 | 10 |
| validated storage `KeyValue` records | 0 | 2 |
| terminal controls | 0 | 1 |
| assistant blocks | 0 | 3 (1 committed) |
| ID-linked completed turns | 0 | 1 |

PID 1472 is a convincing wrong choice because its three key copies even sit near
prompt fragments. None resolves as the Mojo pair used later, however, and no
terminal or stream record survives validation. This is stale residue, not a
completed exchange.

PID 6612 contains two valid composer revisions: a 12-character partial value at
`0x466440` and the complete 233-character value at `0x467440`. It also contains
three assistant blocks, but two are four-character pending fragments. Only the
40-character block at `0x2658000` is committed, and its IDs join it to the
terminal control at `0x265360c`. That single relationship selects PID 6612, not
its age, and not because `10` is greater than `3`.

<details>
<summary><strong>The renderer-comparison script</strong></summary>

The script takes `PID=path` arguments and writes its JSON report to standard
output. It uses field names as anchors, then validates the surrounding formats,
none of the constants contains the recovered prompt or response. The same
tested file is available as
[`compare_renderers.py`](/writeups/cheater/scripts/compare_renderers.py).

```bash
python3 compare_renderers.py "1472=renderer-1472/pid.1472.dmp" "6612=renderer-6612/pid.6612.dmp"
```

```python
#!/usr/bin/env python3
"""Compare raw Chrome renderer dumps without searching for the prompt or answer."""

import argparse
import json
import mmap
import re
import struct
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID


COMPOSER_KEY = b"oai/apps/lightweight-web/composerDraft/v1"
TERMINAL = b'data-conversation-control="terminal-received"'
RESUME = b'data-conversation-control="resume-token"'
STARTED = b'data-conversation-control="assistant-content-started"'
STREAM = b'data-assistant-stream-block=""'
NOAUTH_ROUTE = b"chatgpt.com/unauth-mweb/conversation?lightweight_authenticated=0"
SUBMISSION_OWNER = b"conversationRetryOwner="

UUID_TEXT = rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PENDING_FOR = re.compile(
    rb'for="assistant-pending-(' + UUID_TEXT + rb')-(committed-tail|pending)"'
)
TURN_STATE = re.compile(
    rb'\x22\x12conversationTurnId\x22\x24(' + UUID_TEXT +
    rb')\x22\x04kind\x22\x1cweb-mobile-conversation-turn'
    rb'\x22\x09streaming([FT])'
)


class FirstStartTag(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.name = None
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        if self.name is None:
            self.name = tag
            self.attrs = dict(attrs)


def offsets(data, needle):
    at = 0
    while (at := data.find(needle, at)) != -1:
        yield at
        at += 1


def canonical_uuid(value):
    try:
        parsed = str(UUID(value))
    except (ValueError, AttributeError):
        return None
    return parsed if parsed == value.lower() else None


def parse_start_tag(data, anchor, name, look_back=512, look_ahead=2048):
    start = data.rfind(b"<" + name.encode(), max(0, anchor - look_back), anchor + 1)
    end = data.find(b">", anchor, min(len(data), anchor + look_ahead))
    if start == -1 or end == -1:
        return None

    parser = FirstStartTag()
    try:
        parser.feed(data[start : end + 1].decode("latin-1"))
    except Exception:
        return None
    if parser.name != name:
        return None
    return start, end + 1, parser.attrs


def decode_storage_array(data, start):
    if start < 0 or start + 9 > len(data) or start % 8:
        return None
    num_bytes, num_elements = struct.unpack_from("<II", data, start)
    if num_elements < 1 or num_bytes != 8 + num_elements:
        return None
    end = start + num_bytes
    if end > len(data):
        return None

    payload = data[start + 8 : end]
    marker, raw = payload[0], payload[1:]
    try:
        if marker == 1:
            return raw.decode("latin-1"), start + 9
        if marker == 0 and len(raw) % 2 == 0:
            return raw.decode("utf-16le"), start + 9
    except UnicodeDecodeError:
        pass
    return None


def composer_pairs(data):
    hits = list(offsets(data, COMPOSER_KEY))
    pairs = []

    for hit in hits:
        key_array = hit - 9  # 8-byte array header + 1-byte encoding marker
        decoded_key = decode_storage_array(data, key_array)
        if not decoded_key or decoded_key[0].encode("latin-1") != COMPOSER_KEY:
            continue

        first_slot = max(8, key_array - 0x80)
        first_slot += (-first_slot) % 8
        for key_slot in range(first_slot, key_array, 8):
            key_relative = struct.unpack_from("<Q", data, key_slot)[0]
            if key_slot + key_relative != key_array:
                continue

            record = key_slot - 8
            num_bytes, version = struct.unpack_from("<II", data, record)
            if version != 0 or num_bytes < 0x18 or num_bytes % 8:
                continue
            if record + num_bytes != key_array:
                continue

            value_slot = key_slot + 8
            value_relative = struct.unpack_from("<Q", data, value_slot)[0]
            value_array = value_slot + value_relative
            decoded_value = decode_storage_array(data, value_array)
            if not decoded_value:
                continue

            value, value_offset = decoded_value
            pairs.append(
                {
                    "record_offset": hex(record),
                    "key_offset": hex(hit),
                    "value_offset": hex(value_offset),
                    "value_characters": len(value),
                    "value": value,
                }
            )
            break

    return hits, pairs


def printable_allocation(data, anchor, maximum=0x10000):
    """Bound one printable ASCII run around an anchor in raw memory."""
    start = anchor
    floor = max(0, anchor - maximum)
    while start > floor and 0x20 <= data[start - 1] <= 0x7E:
        start -= 1

    end = anchor
    ceiling = min(len(data), anchor + maximum)
    while end < ceiling and 0x20 <= data[end] <= 0x7E:
        end += 1
    return start, end


def submission_records(data):
    """Decode form fragments containing complete owner and message-ID fields."""
    grouped = {}

    for anchor in offsets(data, SUBMISSION_OWNER):
        start, end = printable_allocation(data, anchor)
        try:
            fields = parse_qs(
                data[start:end].decode("ascii"),
                keep_blank_values=True,
                strict_parsing=False,
            )
            owner_text = fields["conversationRetryOwner"][-1]
            assistant_text = fields["assistantMessageId"][-1]
            user_text = fields["userMessageId"][-1]
            owner = json.loads(owner_text)
        except (UnicodeDecodeError, KeyError, IndexError, json.JSONDecodeError):
            continue

        if not assistant_text.startswith("pending-"):
            continue
        pending_id = canonical_uuid(assistant_text.removeprefix("pending-"))
        user_message_id = canonical_uuid(user_text)
        if pending_id is None or user_message_id is None or not isinstance(owner, dict):
            continue
        if owner.get("mode") != "anonymous" or owner.get("sessionEpoch") is not None:
            continue

        key = (pending_id, user_message_id, json.dumps(owner, sort_keys=True))
        record = grouped.setdefault(
            key,
            {
                "allocation_offset": hex(start),
                "allocation_end": hex(end),
                "owner_field_offset": hex(anchor),
                "owner": owner,
                "pending_assistant_id": pending_id,
                "user_message_id": user_message_id,
                "copy_offsets": [],
            },
        )
        record["copy_offsets"].append(hex(anchor))

    return list(grouped.values())


def history_url_arrays(data, conversation_id):
    """Validate exact /uc/ URLs as length-delimited Mojo arrays."""
    if conversation_id is None:
        return []

    encoded = f"https://chatgpt.com/uc/{conversation_id}".encode("ascii")
    records = []
    for url_offset in offsets(data, encoded):
        header = url_offset - 8
        if header < 0 or header % 8:
            continue
        num_bytes, num_elements = struct.unpack_from("<II", data, header)
        if num_bytes != 8 + len(encoded) or num_elements != len(encoded):
            continue
        records.append(
            {
                "array_header_offset": hex(header),
                "url_offset": hex(url_offset),
                "conversation_id_offset": hex(url_offset + encoded.index(conversation_id.encode("ascii"))),
                "num_bytes": num_bytes,
                "num_elements": num_elements,
                "url": encoded.decode("ascii"),
            }
        )
    return records


def conversation_turn_states(data):
    """Parse serialized navigation-state records keyed by user message UUID."""
    grouped = {}
    for match in TURN_STATE.finditer(data):
        conversation_turn_id = canonical_uuid(match.group(1).decode("ascii"))
        if conversation_turn_id is None:
            continue
        state = "true" if match.group(2) == b"T" else "false"
        record = grouped.setdefault(
            conversation_turn_id,
            {
                "conversation_turn_id": conversation_turn_id,
                "kind": "web-mobile-conversation-turn",
                "streaming_true_offsets": [],
                "streaming_false_offsets": [],
            },
        )
        record[f"streaming_{state}_offsets"].append(hex(match.start()))
    return list(grouped.values())


def storage_page_links(url_arrays, pairs):
    """Keep only pages containing both the pivot URL and a valid composer pair."""
    links = []
    for url_record in url_arrays:
        page = int(url_record["array_header_offset"], 16) & ~0xFFF
        page_pairs = [
            pair
            for pair in pairs
            if page <= int(pair["record_offset"], 16) < page + 0x1000
        ]
        if page_pairs:
            links.append(
                {
                    "page": hex(page),
                    "url_array_header": url_record["array_header_offset"],
                    "composer_records": page_pairs,
                }
            )
    return links


def controls(data, needle, kind, required):
    parsed = []
    for anchor in offsets(data, needle):
        tag = parse_start_tag(data, anchor, "span")
        if not tag:
            continue
        start, end, attrs = tag
        if attrs.get("data-conversation-control") != kind:
            continue

        values = {}
        valid = True
        for attr in required:
            value = canonical_uuid(attrs.get(attr))
            if value is None:
                valid = False
                break
            values[attr.removeprefix("data-").replace("-", "_")] = value
        if valid:
            values.update({"anchor": anchor, "tag_start": start, "tag_end": end})
            parsed.append(values)
    return parsed


def stream_blocks(data):
    blocks = []
    for attr_offset in offsets(data, STREAM):
        tag = parse_start_tag(data, attr_offset, "p", 256, 1024)
        if not tag:
            continue
        start, open_end, attrs = tag
        try:
            index = int(attrs["data-assistant-stream-block-index"])
        except (KeyError, ValueError):
            continue

        close = data.find(b"</p>", open_end, min(len(data), open_end + 4096))
        if close == -1:
            continue
        body = data[open_end:close].split(b"<", 1)[0]
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            continue

        # The allocation boundary can cut off the beginning of <template>, so
        # use the last complete `for=` attribute before the paragraph.
        context_start = max(0, start - 2048)
        matches = list(PENDING_FOR.finditer(data[context_start:start]))
        if not matches:
            continue
        match = matches[-1]

        pending_id = canonical_uuid(match.group(1).decode("ascii"))
        state = match.group(2).decode("ascii")
        blocks.append(
            {
                "anchor": attr_offset,
                "end": close + 4,
                "block_index": index,
                "text": text,
                "pending_id": pending_id,
                "committed": state == "committed-tail",
            }
        )
    return blocks


def pending_target_after(data, control):
    end = min(len(data), control["tag_end"] + 4096)
    match = PENDING_FOR.search(data[control["tag_end"] : end])
    if not match or match.group(2) != b"pending":
        return None
    return canonical_uuid(match.group(1).decode("ascii"))


def linked_turns(data, terminals, blocks, resumes, started):
    turns = []
    for block in (item for item in blocks if item["committed"]):
        nearby_resumes = [r for r in resumes if 0 < r["anchor"] - block["end"] < 0x8000]
        for resume in nearby_resumes:
            nearby_started = [
                s for s in started if 0 < s["anchor"] - resume["anchor"] < 0x8000
            ]
            for began in nearby_started:
                if pending_target_after(data, began) != block["pending_id"]:
                    continue
                for terminal in terminals:
                    if not (0 < block["anchor"] - terminal["anchor"] < 0x10000):
                        continue
                    if not (
                        terminal["conversation_id"] == resume["conversation_id"]
                        and terminal["operation_id"] == resume["operation_id"]
                        and terminal["operation_id"] == began["operation_id"]
                        and terminal["message_id"] == began["message_id"]
                    ):
                        continue
                    turns.append(
                        {
                            "terminal_control": hex(terminal["anchor"]),
                            "committed_stream_block": hex(block["anchor"]),
                            "conversation_id": terminal["conversation_id"],
                            "pending_assistant_id": block["pending_id"],
                            "final_assistant_id": terminal["message_id"],
                            "operation_id": terminal["operation_id"],
                            "response_text": block["text"],
                        }
                    )
    return turns


def attach_submissions(turns, submissions):
    for turn in turns:
        matches = [
            record
            for record in submissions
            if record["pending_assistant_id"] == turn["pending_assistant_id"]
        ]
        if len(matches) == 1:
            turn["submission"] = matches[0]


def attach_turn_states(submissions, states):
    by_id = {state["conversation_turn_id"]: state for state in states}
    for submission in submissions:
        state = by_id.get(submission["user_message_id"])
        if state is not None:
            submission["navigation_state"] = state


def inspect_dump(pid, path, conversation_id=None):
    with path.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        key_hits, pairs = composer_pairs(data)
        terminals = controls(
            data,
            TERMINAL,
            "terminal-received",
            ("data-conversation-id", "data-message-id", "data-operation-id"),
        )
        resumes = controls(
            data, RESUME, "resume-token", ("data-conversation-id", "data-operation-id")
        )
        started = controls(
            data, STARTED, "assistant-content-started", ("data-message-id", "data-operation-id")
        )
        blocks = stream_blocks(data)
        turns = linked_turns(data, terminals, blocks, resumes, started)
        submissions = submission_records(data)
        turn_states = conversation_turn_states(data)
        attach_turn_states(submissions, turn_states)
        attach_submissions(turns, submissions)
        url_arrays = history_url_arrays(data, conversation_id)
        page_links = storage_page_links(url_arrays, pairs)

        route_offsets = []
        for at in offsets(data, NOAUTH_ROUTE):
            route = urlsplit("https://" + NOAUTH_ROUTE.decode("ascii"))
            if (
                route.hostname == "chatgpt.com"
                and route.path == "/unauth-mweb/conversation"
                and parse_qs(route.query) == {"lightweight_authenticated": ["0"]}
            ):
                route_offsets.append(hex(at))

    matching_turns = [
        turn
        for turn in turns
        if conversation_id is None or turn["conversation_id"] == conversation_id
    ]

    return {
        "pid": pid,
        "history_pivot": {
            "conversation_id": conversation_id,
            "validated_url_arrays": url_arrays,
            "storage_page_links": page_links,
            "matching_completed_turn_count": len(matching_turns),
        },
        "composer_key_candidates": {
            "count": len(key_hits),
            "offsets": [hex(item) for item in key_hits],
        },
        "valid_mojo_composer_pairs": pairs,
        "terminal_controls": [
            {
                "anchor_offset": hex(item["anchor"]),
                "conversation_id": item["conversation_id"],
                "message_id": item["message_id"],
                "operation_id": item["operation_id"],
            }
            for item in terminals
        ],
        "assistant_stream_blocks": [
            {
                "anchor_offset": hex(item["anchor"]),
                "text_characters": len(item["text"]),
                "committed": item["committed"],
                "pending_assistant_id": item["pending_id"],
                "text": item["text"],
            }
            for item in blocks
        ],
        "submission_records": submissions,
        "conversation_turn_states": turn_states,
        "valid_noauth_route_literals": route_offsets,
        "linked_completed_turns": turns,
        "complete_turn": bool(matching_turns),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conversation-id",
        help="conversation UUID recovered from Chrome History",
    )
    parser.add_argument("dump", nargs="+", metavar="PID=PATH")
    args = parser.parse_args()

    conversation_id = None
    if args.conversation_id is not None:
        conversation_id = canonical_uuid(args.conversation_id)
        if conversation_id is None:
            parser.error("--conversation-id must be a canonical UUID")

    renderers = []
    for item in args.dump:
        pid_text, separator, path_text = item.partition("=")
        if not separator:
            parser.error(f"expected PID=PATH, got {item!r}")
        renderers.append(
            inspect_dump(int(pid_text), Path(path_text), conversation_id)
        )

    completed = [r["pid"] for r in renderers if r["complete_turn"]]
    report = {
        "report": "Cheater Chrome renderer comparison",
        "source": "Volatility windows.memmap --dump output",
        "method": {
            "history_pivot": "Validate the supplied History conversation UUID in exact /uc/ URL arrays and typed terminal controls.",
            "response_join": "Join terminal, committed stream, resume-token, and assistant-content-started records by their named UUID fields.",
            "submission_join": "Match the committed stream's pending assistant UUID to assistantMessageId in a decoded form allocation.",
            "prompt_join": "Require the validated /uc/ URL array and a valid Mojo composer KeyValue record to occupy the same 4 KiB storage page.",
        },
        "history_conversation_id": conversation_id,
        "renderers": renderers,
        "selected_pid": completed[0] if len(completed) == 1 else None,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

```

</details>


## Reconstructing Discord

PID 4080 is the Discord renderer, but that does not make every Discord-looking
string inside it a message. The interesting question is narrower: **was the word
`solution` actually sent, or did it only exist in the composer?**

I wanted one parser to answer that without being handed the answer first. Its
only input is the renderer dump, no channel ID, username, message text, or magic
offset.

### Run the reconstruction

Download [`parse_discord.py`](/writeups/cheater/scripts/parse_discord.py), put it
beside `pid.4080.dmp`, and run:

```bash
python3 parse_discord.py pid.4080.dmp -o discord-investigation.json
```

It prints:

```text
Recovered 28 Gateway dispatches, 5 messages, and 13 draft revisions for channel 1546915046091923606.
```

The complete, already generated
[JSON report](/writeups/cheater/reports/discord-investigation.json) keeps the
source offsets and the fields used for every join. Its first draft-to-message
comparison is the part that was very interesting:

```json
{
  "message_id": "1546915339453857823",
  "final_draft": "did you finish the ECE 54700 hw 1 solution",
  "sent_content": "did you finish the ECE 54700 hw 1",
  "removed_words": ["solution"],
  "draft_to_send_ms": 8754
}
```

That is still not yet the proof. The rest of this section shows how
the script reached it if you're interested.

<details>

<summary><strong>Show the complete Discord reconstruction script</strong></summary>

```python
#!/usr/bin/env python3
"""Reconstruct Discord evidence from a dumped Chromium renderer.

The parser deliberately starts without a channel ID, username, message text, or
known offset.  It validates complete Discord Gateway ETF dispatches, correlates
the recovered DM channel with Discord's cached selected-channel state, and then
extracts DraftStore revisions for that same channel.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import mmap
import struct
from pathlib import Path
from typing import Any, Iterator


DISCORD_EPOCH_MS = 1_420_070_400_000
MAX_TERM_BYTES = 8 * 1024 * 1024
MAX_COLLECTION_ITEMS = 100_000
MAX_DEPTH = 64


class ETFError(Exception):
    """A candidate is not a complete, supported ETF term."""


class ETFReader:
    def __init__(self, data: mmap.mmap, pos: int, limit: int):
        self.data = data
        self.pos = pos
        self.limit = min(limit, len(data))

    def take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > self.limit:
            raise ETFError("term runs outside the candidate bounds")
        value = self.data[self.pos : self.pos + size]
        self.pos += size
        return value

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack(">H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack(">I", self.take(4))[0]

    def checked_count(self, count: int) -> int:
        if count > MAX_COLLECTION_ITEMS:
            raise ETFError(f"unreasonable collection length: {count}")
        return count

    def atom(self, size: int) -> Any:
        value = self.take(size).decode("utf-8", errors="strict")
        return {"true": True, "false": False, "nil": None}.get(value, value)

    def binary(self, size: int) -> Any:
        value = self.take(size)
        try:
            return value.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return {"$binary_hex": value.hex()}

    @staticmethod
    def map_key(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool, bytes, type(None))):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def term(self, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise ETFError("maximum ETF nesting depth exceeded")

        tag = self.u8()

        if tag == 70:  # NEW_FLOAT_EXT
            return struct.unpack(">d", self.take(8))[0]
        if tag == 97:  # SMALL_INTEGER_EXT
            return self.u8()
        if tag == 98:  # INTEGER_EXT
            return struct.unpack(">i", self.take(4))[0]
        if tag == 99:  # FLOAT_EXT (legacy, 31-byte string)
            raw = self.take(31).split(b"\x00", 1)[0]
            try:
                return float(raw.decode("ascii"))
            except ValueError as exc:
                raise ETFError("invalid FLOAT_EXT") from exc
        if tag in (100, 118):  # ATOM_EXT / ATOM_UTF8_EXT
            return self.atom(self.u16())
        if tag in (115, 119):  # SMALL_ATOM_EXT / SMALL_ATOM_UTF8_EXT
            return self.atom(self.u8())
        if tag == 104:  # SMALL_TUPLE_EXT
            return [self.term(depth + 1) for _ in range(self.checked_count(self.u8()))]
        if tag == 105:  # LARGE_TUPLE_EXT
            return [self.term(depth + 1) for _ in range(self.checked_count(self.u32()))]
        if tag == 106:  # NIL_EXT
            return []
        if tag == 107:  # STRING_EXT
            return self.take(self.u16()).decode("latin-1")
        if tag == 108:  # LIST_EXT
            count = self.checked_count(self.u32())
            values = [self.term(depth + 1) for _ in range(count)]
            tail = self.term(depth + 1)
            if tail != []:
                return {"items": values, "tail": tail}
            return values
        if tag == 109:  # BINARY_EXT
            return self.binary(self.u32())
        if tag == 77:  # BIT_BINARY_EXT
            size = self.u32()
            significant_bits = self.u8()
            value = self.binary(size)
            return {"bits_in_last_byte": significant_bits, "value": value}
        if tag in (110, 111):  # SMALL_BIG_EXT / LARGE_BIG_EXT
            size = self.u8() if tag == 110 else self.checked_count(self.u32())
            sign = self.u8()
            magnitude = int.from_bytes(self.take(size), "little")
            return -magnitude if sign else magnitude
        if tag == 116:  # MAP_EXT
            count = self.checked_count(self.u32())
            result = {}
            for _ in range(count):
                key = self.map_key(self.term(depth + 1))
                result[key] = self.term(depth + 1)
            return result

        raise ETFError(f"unsupported ETF tag {tag}")


def scan_gateway_events(data: mmap.mmap) -> list[dict[str, Any]]:
    """Find and validate uncompressed ETF maps beginning with version 131."""
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = 0

    while True:
        offset = data.find(b"\x83\x74", cursor)
        if offset == -1:
            break
        cursor = offset + 1
        reader = ETFReader(data, offset + 1, offset + MAX_TERM_BYTES)

        try:
            event = reader.term()
        except (ETFError, UnicodeDecodeError, struct.error):
            continue

        if not (
            isinstance(event, dict)
            and event.get("op") == 0
            and isinstance(event.get("t"), str)
            and "d" in event
            and "s" in event
        ):
            continue

        fingerprint = json.dumps(event, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        events.append(
            {
                "offset": offset,
                "end_offset": reader.pos,
                "event": event,
            }
        )

    return events


def bounded_json_object(data: mmap.mmap, start: int, maximum: int = 1024 * 1024) -> tuple[Any, int]:
    """Return one balanced UTF-8 JSON object and its exclusive end offset."""
    if start < 0 or start >= len(data) or data[start] != ord("{"):
        raise ValueError("JSON object does not start with an opening brace")

    depth = 0
    in_string = False
    escaped = False
    end_limit = min(len(data), start + maximum)

    for pos in range(start, end_limit):
        byte = data[pos]
        if in_string:
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                in_string = False
            continue

        if byte == ord('"'):
            in_string = True
        elif byte == ord("{"):
            depth += 1
        elif byte == ord("}"):
            depth -= 1
            if depth == 0:
                raw = data[start : pos + 1]
                return json.loads(raw.decode("utf-8")), pos + 1

    raise ValueError("unterminated JSON object")


def scan_selected_channels(data: mmap.mmap) -> list[dict[str, Any]]:
    marker = b'{"selectedChannelId"'
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = 0

    while True:
        json_offset = data.find(marker, cursor)
        if json_offset == -1:
            break
        cursor = json_offset + 1

        if json_offset < 8:
            continue
        length, flag = struct.unpack("<II", data[json_offset - 8 : json_offset])
        if flag != 1 or length < len(marker) or length > 1024 * 1024:
            continue

        try:
            raw = data[json_offset : json_offset + length]
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or "selectedChannelId" not in value:
            continue

        fingerprint = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        records.append(
            {
                "record_offset": json_offset - 8,
                "json_offset": json_offset,
                "length": length,
                "string_flag": flag,
                "value": value,
            }
        )

    return records


def walk_draft_state(value: Any, path: tuple[str, ...] = ()) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("timestamp"), int) and isinstance(value.get("draft"), str):
            yield {
                "path": list(path),
                "timestamp_ms": value["timestamp"],
                "draft": value["draft"],
            }
        for key, child in value.items():
            yield from walk_draft_state(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_draft_state(child, path + (str(index),))


def scan_draft_store(data: mmap.mmap) -> list[dict[str, Any]]:
    marker = b"DraftStore"
    drafts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, str]] = set()
    cursor = 0

    while True:
        anchor = data.find(marker, cursor)
        if anchor == -1:
            break
        cursor = anchor + 1
        json_offset = data.find(b"{", anchor + len(marker), anchor + len(marker) + 32)
        if json_offset == -1:
            continue

        try:
            value, _ = bounded_json_object(data, json_offset)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or not isinstance(value.get("_state"), dict):
            continue

        for leaf in walk_draft_state(value["_state"]):
            path = leaf.pop("path")
            if len(path) < 2:
                continue
            user_id, channel_id = path[0], path[1]
            key = (user_id, channel_id, leaf["timestamp_ms"], leaf["draft"])
            if key in seen:
                continue
            seen.add(key)
            drafts.append(
                {
                    "record_offset": anchor,
                    "json_offset": json_offset,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    **leaf,
                }
            )

    drafts.sort(key=lambda item: (item["timestamp_ms"], item["record_offset"]))
    return drafts


def iso_from_ms(timestamp_ms: int) -> str:
    value = dt.datetime.fromtimestamp(timestamp_ms / 1000, tz=dt.timezone.utc)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def snowflake_ms(value: str | int) -> int:
    return (int(value) >> 22) + DISCORD_EPOCH_MS


def event_id(entry: dict[str, Any]) -> str | None:
    payload = entry["event"].get("d")
    if isinstance(payload, dict) and payload.get("id") is not None:
        return str(payload["id"])
    return None


def choose_dm_channel(
    events: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
) -> dict[str, Any]:
    messages_per_channel: collections.Counter[str] = collections.Counter()
    for entry in events:
        event = entry["event"]
        payload = event.get("d")
        if event.get("t") == "MESSAGE_CREATE" and isinstance(payload, dict):
            if payload.get("channel_id") is not None:
                messages_per_channel[str(payload["channel_id"])] += 1

    selected_ids = {
        str(record["value"].get("selectedChannelId"))
        for record in selected
        if record["value"].get("selectedChannelId") is not None
    }
    draft_counts: collections.Counter[str] = collections.Counter(
        draft["channel_id"] for draft in drafts
    )

    candidates = []
    for entry in events:
        event = entry["event"]
        payload = event.get("d")
        if event.get("t") != "CHANNEL_CREATE" or not isinstance(payload, dict):
            continue
        if payload.get("type") != 1 or payload.get("id") is None:
            continue
        channel_id = str(payload["id"])
        candidates.append(
            {
                "entry": entry,
                "channel_id": channel_id,
                "message_count": messages_per_channel[channel_id],
                "selected": channel_id in selected_ids,
                "draft_count": draft_counts[channel_id],
            }
        )

    if not candidates:
        raise RuntimeError("no validated type-1 CHANNEL_CREATE dispatch was recovered")

    corroborated = [
        candidate
        for candidate in candidates
        if candidate["message_count"] > 0
        and candidate["selected"]
        and candidate["draft_count"] > 0
    ]
    if len(corroborated) != 1:
        details = ", ".join(
            f"{candidate['channel_id']} "
            f"(messages={candidate['message_count']}, selected={candidate['selected']}, "
            f"drafts={candidate['draft_count']})"
            for candidate in candidates
        )
        raise RuntimeError(f"expected one fully corroborated DM channel; recovered: {details}")
    return corroborated[0]["entry"]


def compact_channel(payload: dict[str, Any]) -> dict[str, Any]:
    recipients = []
    for recipient in payload.get("recipients", []):
        if isinstance(recipient, dict):
            recipients.append(
                {
                    key: recipient.get(key)
                    for key in ("id", "username", "global_name")
                    if recipient.get(key) is not None
                }
            )
    return {"id": str(payload["id"]), "type": payload.get("type"), "recipients": recipients}


def compact_message(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry["event"]["d"]
    author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
    identifier = str(payload["id"])
    derived_ms = snowflake_ms(identifier)
    supplied = str(payload.get("timestamp", ""))
    supplied_ms = int(dt.datetime.fromisoformat(supplied.replace("Z", "+00:00")).timestamp() * 1000)
    return {
        "event_offset": f"0x{entry['offset']:x}",
        "id": identifier,
        "channel_id": str(payload.get("channel_id")),
        "timestamp": supplied,
        "snowflake_timestamp": iso_from_ms(derived_ms),
        "snowflake_delta_ms": derived_ms - supplied_ms,
        "author": {
            key: author.get(key)
            for key in ("id", "username", "global_name")
            if author.get(key) is not None
        },
        "content": payload.get("content"),
    }


def final_draft_before(
    drafts: list[dict[str, Any]], timestamp_ms: int, user_id: str
) -> dict[str, Any] | None:
    candidates = [
        draft
        for draft in drafts
        if draft["user_id"] == user_id and draft["timestamp_ms"] <= timestamp_ms
    ]
    if not candidates:
        return None
    candidate = max(candidates, key=lambda item: item["timestamp_ms"])
    if timestamp_ms - candidate["timestamp_ms"] > 60_000:
        return None
    return candidate


def build_report(path: Path, data: mmap.mmap) -> dict[str, Any]:
    events = scan_gateway_events(data)
    selected = scan_selected_channels(data)
    drafts = scan_draft_store(data)
    channel_entry = choose_dm_channel(events, selected, drafts)
    channel = compact_channel(channel_entry["event"]["d"])
    channel_id = channel["id"]

    channel_messages = [
        compact_message(entry)
        for entry in events
        if entry["event"].get("t") == "MESSAGE_CREATE"
        and isinstance(entry["event"].get("d"), dict)
        and str(entry["event"]["d"].get("channel_id")) == channel_id
    ]
    channel_messages.sort(key=lambda item: item["timestamp"])

    selected_matches = [
        record for record in selected if str(record["value"].get("selectedChannelId")) == channel_id
    ]
    relevant_drafts = [draft for draft in drafts if draft["channel_id"] == channel_id]

    draft_user_counts = collections.Counter(draft["user_id"] for draft in relevant_drafts)
    message_author_ids = {str(item["author"].get("id")) for item in channel_messages}
    local_user_id = next(
        (user_id for user_id, _ in draft_user_counts.most_common() if user_id in message_author_ids),
        None,
    )

    message_comparisons = []
    for message in channel_messages:
        if local_user_id is None or str(message["author"].get("id")) != local_user_id:
            continue
        message_ms = int(
            dt.datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00")).timestamp() * 1000
        )
        draft = final_draft_before(relevant_drafts, message_ms, local_user_id)
        if draft is None:
            continue
        draft_words = draft["draft"].split()
        sent_words = str(message["content"]).split()
        removed = [word for word in draft_words if word not in sent_words]
        message_comparisons.append(
            {
                "message_id": message["id"],
                "final_draft": draft["draft"],
                "sent_content": message["content"],
                "removed_words": removed,
                "draft_to_send_ms": message_ms - draft["timestamp_ms"],
            }
        )

    event_counts = collections.Counter(entry["event"]["t"] for entry in events)
    recipient_ids = [str(item["id"]) for item in channel["recipients"] if item.get("id")]

    return {
        "report": "Cheater Discord renderer reconstruction",
        "source": {"file": path.name, "size_bytes": path.stat().st_size},
        "method": {
            "gateway": "complete ETF terms beginning with VERSION_MAGIC + MAP_EXT",
            "selected_channel": "complete little-endian length-prefixed JSON records",
            "drafts": "complete DraftStore JSON states",
            "deduplication": "identical decoded Gateway events and identical draft revisions",
        },
        "gateway": {
            "validated_dispatch_count": len(events),
            "event_type_counts": dict(sorted(event_counts.items())),
            "dm_channel": {
                "event_offset": f"0x{channel_entry['offset']:x}",
                **channel,
            },
            "messages": channel_messages,
        },
        "client_state": {
            "selected_channel_records": [
                {
                    "record_offset": f"0x{record['record_offset']:x}",
                    "json_offset": f"0x{record['json_offset']:x}",
                    "length": record["length"],
                    "string_flag": record["string_flag"],
                    "value": record["value"],
                }
                for record in selected_matches
            ],
            "draft_revisions": [
                {
                    "record_offset": f"0x{draft['record_offset']:x}",
                    "user_id": draft["user_id"],
                    "channel_id": draft["channel_id"],
                    "timestamp": iso_from_ms(draft["timestamp_ms"]),
                    "timestamp_ms": draft["timestamp_ms"],
                    "draft": draft["draft"],
                }
                for draft in relevant_drafts
            ],
        },
        "correlation": {
            "channel_id": channel_id,
            "local_user_id": local_user_id,
            "recipient_ids": recipient_ids,
            "message_count": len(channel_messages),
            "all_messages_match_channel": all(
                message["channel_id"] == channel_id for message in channel_messages
            ),
            "all_snowflake_checks_zero_delta": all(
                message["snowflake_delta_ms"] == 0 for message in channel_messages
            ),
            "draft_to_sent": message_comparisons,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("renderer", type=Path, help="renderer dump, for example pid.4080.dmp")
    parser.add_argument("-o", "--output", type=Path, help="write the JSON report here")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.renderer.open("rb") as stream:
        data = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            report = build_report(args.renderer, data)
        finally:
            data.close()

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    print(
        f"Recovered {report['gateway']['validated_dispatch_count']} Gateway dispatches, "
        f"{report['correlation']['message_count']} messages, and "
        f"{len(report['client_state']['draft_revisions'])} draft revisions "
        f"for channel {report['correlation']['channel_id']}."
    )


if __name__ == "__main__":
    main()

```

</details>

### What the parser accepts as a Discord event

Discord's [Gateway](https://docs.discord.com/developers/events/gateway) may
encode payloads as JSON or binary Erlang External Term Format (ETF). In this
renderer the complete cached dispatches begin like this:

```text
83 74 00 00 00 04
```

According to the official
[ETF grammar](https://www.erlang.org/docs/26/apps/erts/erl_ext_dist.html),
`0x83` is the version byte, `0x74` is `MAP_EXT`, and the next four
big-endian bytes say that the map has four pairs. Those pairs are the Gateway
envelope:

```text
op  operation code          d  event data
s   sequence number         t  dispatch event name
```

![A complete Discord Gateway ETF event in the renderer dump](/writeups/cheater/screenshots/07-discord-etf.png)

The scanner uses `83 74` only to propose an offset. A recursive decoder then
has to consume the whole term: `BINARY_EXT` supplies an exact byte length,
`LIST_EXT` supplies an element count and tail, `MAP_EXT` supplies a pair
count, and `SMALL_BIG_EXT` supplies the byte width and sign of a large integer.
Every read is bounds-checked, collections are capped, and nesting stops at 64
levels. A false hit, unsupported tag, impossible length, or truncated object is
discarded.

Even a successfully decoded map is ignored unless `op == 0`, `t` is a
string, and both `d` and `s` exist. Identical decoded objects are deduplicated
because the same event can survive in more than one allocation. Only then does
the script inspect `t`.

The result is not just five convenient messages. It is 28 complete dispatches:
11 `SESSIONS_REPLACE`, five `MESSAGE_CREATE`, two `MESSAGE_ACK`, two
`RELATIONSHIP_ADD`, two `TYPING_START`, and six other single events. That
background traffic is a useful sanity check. A parser that returned only the
sentence I hoped to find would make me suspicious.

### The conversation ID is an output, not an input

After decoding every dispatch, the script looks for `CHANNEL_CREATE` events.
There is one type-`1` channel whose ID is also present in three independently
parsed structures: sent messages, the selected-channel record, and DraftStore.
If that join were ambiguous, the script would stop instead of quietly choosing
a channel.

The mapping is:

| What it identifies | Structural field | Recovered value |
| --- | --- | --- |
| DM conversation | `CHANNEL_CREATE.d.id` | `1546915046091923606` |
| Why it is a DM | `CHANNEL_CREATE.d.type` | `1` |
| Other participant | `CHANNEL_CREATE.d.recipients[0].id` | `541465360080044032` |
| Other participant's handle | `CHANNEL_CREATE.d.recipients[0].username` | `tarek_ibr` |
| Local account | outer user key in `DraftStore._state`, also the author of three messages | `1546836880941777006` |
| Conversation on each sent record | `MESSAGE_CREATE.d.channel_id` | `1546915046091923606` |
| Conversation open in the UI | `selectedChannelId` | `1546915046091923606` |
| Conversation owning each draft | second key below the local user in `DraftStore._state` | `1546915046091923606` |

Discord's [Channel resource](https://docs.discord.com/developers/resources/channel)
defines type `1` as a DM and gives it a `recipients` array. That is why the
recipient ID means more than a username found near a message.

The selected-channel evidence is a different structure. At `0xa9aa814` the
renderer contains:

```text
99 00 00 00  01 00 00 00  { ...153 JSON bytes... }
^ length=153  ^ string flag  ^ JSON begins at 0xa9aa81c
```

The script reads both four-byte little-endian fields, takes exactly 153 bytes,
and only accepts the record if `json.loads()` consumes a complete object:

```json
{
  "selectedChannelId": "1546915046091923606",
  "selectedChannelIds": {"null": "1546915046091923606"},
  "mostRecentSelectedTextChannelIds": {},
  "knownThreadIds": []
}
```

This cache schema is version-specific and is not documented as part of
Discord's public API, so I do not use it alone. It agrees with the official DM
object, every message's `channel_id`, and every draft's nested channel key.
That is how conversation `1546915046091923606` was recovered.

### Rebuilding the transcript

Only after the channel is established does the script select
`t == "MESSAGE_CREATE"` and match `d.channel_id`. The five records are:

| UTC | Message ID | Author (user ID) | Sent content |
| --- | --- | --- | --- |
| 16:08:17.987 | `1546915091000328343` | `immortal_xxxx` (`1546836880941777006`) | `hey` |
| 16:08:20.567 | `1546915101821370449` | `tarek_ibr` (`541465360080044032`) | `hey` |
| 16:09:17.223 | `1546915339453857823` | `immortal_xxxx` (`1546836880941777006`) | `did you finish the ECE 54700 hw 1` |
| 16:09:55.418 | `1546915499655303199` | `immortal_xxxx` (`1546836880941777006`) | `the deadline is approaching and I can't do it` |
| 16:10:17.181 | `1546915590935945417` | `tarek_ibr` (`541465360080044032`) | `bro I didn't even start doing it` |

The local user is not guessed from the display name. The outer DraftStore user
key is `1546836880941777006`, and that same immutable ID appears in
`author.id` on three messages. The DM recipient ID appears in `author.id` on
the two replies.

![parsed conversation and drafts](/writeups/cheater/screenshots/08-discord-draft-versus-sent.png)

### The draft changes the meaning

`DraftStore` is client state, not a Gateway event. After each `DraftStore`
anchor, the parser finds the nearby JSON object, balances braces while respecting
quoted strings and escapes, parses the complete object, and walks this shape:

```text
_state
└── 1546836880941777006        local user ID
    └── 1546915046091923606    channel ID
        └── 0
            ├── timestamp
            └── draft
```

Thirteen distinct revisions survive. The first important message develops like
this:

| UTC | Recovered composer state |
| --- | --- |
| 16:08:29.828 | `just wanted t` |
| 16:08:31.209 | `just wanted to ask ` |
| 16:08:40.788 | `did you finish ` |
| 16:08:51.446 | `did you finish the assignment ` |
| 16:08:56.050 | `did you finish the e` |
| 16:09:03.308 | `did you finish the ECE 54700: Intro to Computer Communication Networks hw 1 solution` |
| 16:09:08.469 | `did you finish the ECE 54700 hw 1 solution` |
| 16:09:17.223 | **sent:** `did you finish the ECE 54700 hw 1` |

For each message authored by the local account, the script takes the newest
draft for the same user and channel within the preceding 60 seconds. Here that
draft was saved 8.754 seconds before the matching message event. The second
long draft matches its sent message exactly, the first does not. `solution`
existed in the composer and was removed before Discord created the message.

This distinction is the trap: DraftStore answers “what was typed?” while
`MESSAGE_CREATE` answers “what was sent?” Treating both as chat fragments would
turn two different facts into a false transcript.


### A second clock inside every message ID

Discord message IDs are [Snowflakes](https://docs.discord.com/developers/reference#snowflakes).
Their high bits encode milliseconds since Discord's epoch:

```python
timestamp_ms = (int(message_id) >> 22) + 1420070400000
```

For `1546915339453857823` this yields
`2026-09-08T16:09:17.223Z`.

At 16:10:17 the friend says he has not even started. Forty-seven seconds later,
a new Chrome renderer appears. Now the browser activity is becoming more interesting as his friend didn't give him the assignment.


## Reconstructing Chrome's History database from RAM

To get a better idea of what really happened let's try reconstructing the chrome history. Chrome's browser process had the profile's
SQLite `History` file mapped, so I located its Windows file objects:

```bash
python3 vol.py -f dump.mem  --filters 'Name,History' windows.filescan.FileScan
```

The two relevant rows were:

```text
0x978fd8a95500  \Users\Tarok\AppData\Local\Google\Chrome\User Data\Default\History
0x978fd8a95820  \Users\Tarok\AppData\Local\Google\Chrome\User Data\Default\History-journal
```

now we dump them

```bash
python3 vol.py -f dump.mem -o "$HISTORY_OUT" windows.dumpfiles.DumpFiles --virtaddr 0x978fd8a95500
python3 vol.py -f dump.mem -o "$HISTORY_OUT" windows.dumpfiles.DumpFiles --virtaddr 0x978fd8a95820
```

Volatility's [DumpFiles implementation](https://volatility3.readthedocs.io/en/latest/_modules/volatility3/plugins/windows/dumpfiles.html)
can recover separate `DataSectionObject` and `SharedCacheMap` views. They are
cache layers, not guaranteed clean disk copies. Here, `History` is 188,416
bytes with a valid `SQLite format 3` header. When trying to open it in DB Browser for
SQLite. The header is recognized, but the GUI's integrity check reports
`database disk image is malformed` and the normal schema cannot be browsed.

The journal views cannot repair it: one is mostly zero and the other contains a
stale, unrelated page. Treating every dump with `History-journal` in its name as
a replayable transaction would mix cache residue into the database.

SQLite's documented [`.recover` command](https://www.sqlite.org/recovery.html)
reads usable pages directly instead of stopping at the broken schema.

The input is the 188,416-byte `DataSectionObject` dumped from the main `History`
file at `0x978fd8a95500`:

```text
file.0x978fd8a95500.0x978fd58f1c30.DataSectionObject.History.dat
```

`--ignore-freelist` prevents deleted rows from being silently reintroduced:

```bash
sqlite3 "$HISTORY_OUT/file.0x978fd8a95500.0x978fd58f1c30.DataSectionObject.History.dat" ".recover --ignore-freelist" > "$HISTORY_OUT/History-recovered.sql"
```

`History-recovered.sql` is a text SQL dump, not yet a database. In DB Browser
for SQLite, choose **File → Import → Database from SQL file…**, select that SQL
file, and save the new database. now we can view the recovered table and browse it.


This imported database is the one I use in the screenshots.

![renderer-comparison](/writeups/cheater/screenshots/05-recovered-gui-chrome-history.png)

### Database beautification

now we have the database you can choose to take what you want from here or to clean the database more for better view🤓

Only `lost_and_found` survived because the schema could not be associated with
its b-trees. That does not make the rows anonymous. The recovery output keeps
the root page, rowid, number of fields, and each decoded field. Root page 4 has
seven-field URL records, root page 6 has eighteen-field visit records. Chromium's
own [`urls` implementation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/history/core/browser/url_database.cc)
defines `id, url, title, visit_count, typed_count, last_visit_time, hidden`, and
its [`visits` implementation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/history/core/browser/visit_database.cc)
starts with `id, url, visit_time, from_visit, external_referrer_url, transition`.
The recovered shapes and types match those definitions.

`c0` appears null because both tables declare `id INTEGER PRIMARY KEY`. In an
ordinary SQLite rowid table, that column aliases the b-tree rowid and is stored
as null inside the record, SQLite uses the b-tree key instead. This is specified
in the official [database file format](https://www.sqlite.org/fileformat.html#representation_of_sql_tables).
Therefore the join is `visits.c1 = urls.id`, not `visits.c0 = urls.c0`.

I run that query in the GUI's **Execute SQL** tab.


```sql
SELECT v.id AS visit_id, v.c2 AS chrome_time, v.c3 AS from_visit,
       v.c4 AS external_referrer, v.c5 AS transition, u.c1 AS url
FROM lost_and_found AS v
JOIN lost_and_found AS u
  ON u.rootpgno = 4 AND u.id = CAST(v.c1 AS INTEGER)
WHERE v.rootpgno = 6 AND v.nfield = 18
ORDER BY CAST(v.c2 AS INTEGER), v.id;
```


| UTC | Visit(s) | Recovered navigation |
| --- | ---: | --- |
| 14:51:02.249567 | 38 | Google search for `ECE 54700 ... hw 1 solution` |
| 16:11:06.966950 | 46 | Google search for `chatgpt`, generated from the address bar |
| 16:11:13.701106 | 47 → 48 | Google `goto` URL → `https://chatgpt.com/`, server-redirect chain |
| 16:12:43.363572 | 49 | `https://chatgpt.com/` |
| 16:12:45.456248, 16:12:46.359363 | 50, 51 | `/uc/6aa033fb-3d68-83ea-b1c2-a333a240813c` |
| 16:13:04.274016 | 52 | `/?noauth_recent_chat_failed=1`, from visit 51 |
| 16:13:06.463614 | 53 | back to `https://chatgpt.com/`, also from visit 51 |


![renderer-comparison](/writeups/cheater/screenshots/06-history-timeline.png)

History establishes what was visited and when. It even discloses the anonymous
conversation UUID, but it cannot tell us the prompt or answer. For that we must
parse the renderer state.


## The research that inspired this challenge and why its tool rejects our file

One inspiration for Cheater was Jihun Joun's paper,
[“Forensic analysis from generative AI web application memory: A ChatGPT case study”](https://www.sciencedirect.com/science/article/abs/pii/S2666281726001320),
published in *Forensic Science International: Digital Investigation*. Its core
idea is important: browser memory should be treated as structured application
state, and conversation objects can remain recoverable even when they are no
longer visible in the active interface.

The accompanying [ChatGPT V8 Heap Forensics tool](https://github.com/jihunjoun/ChatGPT-V8-Heap-Forensics)
does this properly for Chrome DevTools `.heapsnapshot` files. A heap snapshot is
not an arbitrary slice of process memory. It is a UTF-8 JSON document with a
schema in `snapshot.meta`, flattened `nodes` and `edges` arrays, and a string
table. The tool rebuilds the directed object graph, finds candidate objects with
properties such as `id`, `parentId`, `children`, and `message`, and then follows
the path `message → content → parts → elements`.

I tried the tool against renderer 6612 because “Chrome V8 memory” sounds like the
right input. It failed immediately:

```text
$ python heap_forensics.py pid.6612.dmp
Error: 'utf-8' codec can't decode byte 0xa0 in position 6: invalid start byte
```

That is an expected and useful failure. Our Volatility file is sparse raw
virtual-memory pages from a process. It has no heap-snapshot JSON envelope, node
table, edge table, or string table. The program is not broken, we just violated its
input contract.

![renderer-comparison](/writeups/cheater/screenshots/04-heapsnapshot-input-mismatch.png)

this would have been possible if for example we managed to acquire a DevTools heap snapshot. An offline full-RAM investigation cannot manufacture graph metadata that
was never captured.

The paper still gives us the right methodological instinct: recover
relationships, not isolated words. With this evidence, however, those
relationships must come from self-describing records that survived inside the
raw renderer pages: Erlang ETF, JSON, URL-encoded form data, HTML attributes, and
application telemetry.


## Reconstructing the anonymous ChatGPT turn

The History database has already handed us the best lead in the renderer:

```text
https://chatgpt.com/uc/6aa033fb-3d68-83ea-b1c2-a333a240813c
                       └──────────────────────────────────┘
                              conversation UUID
```

Visits 50 and 51 contain that URL. I take the final path component, validate it
as a UUID, and use it as a pivot. I do **not** begin by searching for the prompt
or decoding every Base64-looking string.

I go back to the **same** `compare_renderers.py` used during renderer triage and
save a new report. This time I give its optional `--conversation-id` argument
the UUID recovered from History:

```bash
python3 compare_renderers.py --conversation-id 6aa033fb-3d68-83ea-b1c2-a333a240813c "1472=renderer-1472/pid.1472.dmp" "6612=renderer-6612/pid.6612.dmp" > renderer-comparison.json
```

The tested [script](/writeups/cheater/scripts/compare_renderers.py) and its
[JSON report](/writeups/cheater/reports/renderer-comparison.json) are included
with the writeup. The value after `--conversation-id` is copied directly from
the recovered `/uc/` URL. In the report, PID 6612 has one
`history_pivot.matching_completed_turn_count` PID 1472 has zero, which we expected.

There are only two branches to follow from here. One reaches the submitted
request and response. The other reaches the saved prompt:

```text
History /uc/ URL
└── conversation UUID 6aa033fb-...
    ├── terminal and resume controls
    │   ├── final assistant ID + operation ID
    │   └── committed assistant block
    │       ├── response text
    │       └── pending assistant ID
    │           └── submission form → anonymous owner + user-message ID
    └── length-delimited URL array on the storage page
        └── validated composer KeyValue → exact prompt
```

Each arrow is an equality between a named field in two parsed records. Proximity
only tells the parser which bounded container to try next.

### 1. Confirm the History UUID inside a terminal control

The UUID occurs many times in raw V8 memory. Most copies are useless on their
own. The useful one begins at `0x2653682` because it is the value of
`data-conversation-id` inside one complete HTML start tag:

```html
<span data-conversation-control="terminal-received"
      data-conversation-id="6aa033fb-3d68-83ea-b1c2-a333a240813c"
      data-message-id="32b7301b-6a8d-492e-9ff5-519f961d2944"
      data-operation-id="d8d9a168-c0cc-498c-a7c6-7fa0c14c900e">
```

The parser works backward to `<span`, forward to the closing `>`, parses one
tag, and requires all three [`data-*`
attributes](https://html.spec.whatwg.org/multipage/dom.html#embedding-custom-non-visible-data-with-the-data-*-attributes)
to contain canonical UUIDs. The fields now have distinct jobs:

- `data-conversation-id` matches the UUID recovered from History
- `data-message-id` names the **final assistant message**
- `data-operation-id` follows this response through the streamed update

That typed container is why PID 6612 survives. PID 1472 still has cached `/uc/`
URL arrays for this UUID, but no terminal control for it and no linked committed
assistant block.

### 2. Follow the same IDs into the response

At `0x2657f10` a streamed HTML update targets the pending assistant message.
The important parts occur in one bounded update:

```html
<template for="assistant-pending-23bfd3ad-3695-44bc-8b47-99ff1186dcf5-committed-tail">
  <p data-assistant-stream-block=""
     data-assistant-stream-block-index="0">VGVhX2Jsb29tc19zb2Z0bHlfd2FybV9xdWlldA==</p>
</template>

<span data-conversation-control="resume-token"
      data-conversation-id="6aa033fb-3d68-83ea-b1c2-a333a240813c"
      data-operation-id="d8d9a168-c0cc-498c-a7c6-7fa0c14c900e">

<span data-conversation-control="assistant-content-started"
      data-message-id="32b7301b-6a8d-492e-9ff5-519f961d2944"
      data-operation-id="d8d9a168-c0cc-498c-a7c6-7fa0c14c900e">
```

The `resume-token` repeats the **History conversation UUID** and the terminal's
**operation ID**. The following `assistant-content-started` control repeats that
operation ID and the terminal's **final message ID**. The template target adds a
new identifier: pending assistant message
`23bfd3ad-3695-44bc-8b47-99ff1186dcf5`.

The response candidate is the text node at `0x2658045`. The parser accepts it
because it is inside block index `0` of the `committed-tail` for that pending
message not because it happens to resemble Base64.

### 3. Use the pending ID to recover the submission

The pending assistant UUID leads backward to the request state. A matching V8
allocation around `0x2aa3400` contains a complete
[URL-encoded](https://url.spec.whatwg.org/#application/x-www-form-urlencoded)
form. The parser finds the field boundaries, percent-decodes every value, parses
`conversationRetryOwner` as JSON, and validates both message IDs as UUIDs:

```text
conversationRetryOwner={"mode":"anonymous","sessionEpoch":null}
assistantMessageId=pending-23bfd3ad-3695-44bc-8b47-99ff1186dcf5
userMessageId=8408d033-4102-48db-a549-77f18e6b15eb
```

The equality is now explicit: `assistantMessageId` contains the same pending
UUID carried by the committed response template. The form also introduces the
user-message UUID, `8408d033-4102-48db-a549-77f18e6b15eb`.

That user-message UUID later appears in a serialized navigation-state record as
`conversationTurnId`. The parser requires the two UUIDs to match, so the form is
tied to the same browser turn rather than only to a pending UI element.

Two independent records describe a guest request:

- the route is `/unauth-mweb/conversation?lightweight_authenticated=0`
- `conversationRetryOwner.mode` is `anonymous` and `sessionEpoch` is null

There is no ChatGPT account user ID to recover here. `userMessageId` identifies
the guest's message, not a user account.

All of this you can refrence from the [JSON report](/writeups/cheater/reports/renderer-comparison.json)

### 4. Use the History UUID again to reach the prompt

A second useful copy of the conversation UUID begins at `0x4675d7`. This time it
is inside a length-delimited URL array:

| Offset | Parsed field |
| ---: | --- |
| `0x4675b8` | `num_bytes=0x43`, `num_elements=0x3b` |
| `0x4675c0` | start of the 59-byte `https://chatgpt.com/uc/...` URL |
| `0x4675d7` | start of the 36-byte conversation UUID |

`0x43` is 67, exactly the eight-byte array header plus `0x3b`, or 59,
URL bytes. This validates the URL object and narrows the next pass to the
`0x467000–0x467fff` storage page. It does **not** make nearby printable text a
prompt. The report records this correlation under
`history_pivot.storage_page_links`: only that page contains both a validated
copy of the History URL and a valid composer record.

On that page I enumerate Chromium DOM-storage `KeyValue` records. Blink defines
a pair as two
[`array<uint8>` fields](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/public/mojom/dom_storage/storage_area.mojom).
In the [Mojo wire
format](https://chromium.googlesource.com/chromium/src/+/HEAD/mojo/docs/wire_format_spec.md),
each pointer is a relative offset from its own slot and each array begins with
little-endian `num_bytes` and `num_elements` values.

The walker resolves the two pointers:

```python
target = pointer_slot + read_u64le(pointer_slot)
num_bytes, count = unpack_from("<II", dump, target)

require(target % 8 == 0)
require(num_bytes == 8 + count)
payload = dump[target + 8 : target + num_bytes]
```

For local storage, the first payload byte is the string encoding marker.
Chromium's [storage
implementation](https://chromium.googlesource.com/chromium/src/+/dd8d5985e4b1dc04142c94984d0654f4a3339298/components/services/storage/dom_storage/local_storage_impl.cc)
uses `0` for UTF-16LE and `1` for Latin-1. The complete pair is:

| Location | Parsed value |
| ---: | --- |
| `0x467440` | struct header: `num_bytes=0x20`, `version=0` |
| `0x467448` | key pointer: relative `0x18` → `0x467460` |
| `0x467460` | key array: `num_bytes=0x32`, `num_elements=0x2a` |
| `0x467468` | encoding `01` + `oai/apps/lightweight-web/composerDraft/v1` |
| `0x467450` | value pointer: relative `0x48` → `0x467498` |
| `0x467498` | value array: `num_bytes=0xf2`, `num_elements=0xea` |
| `0x4674a1` | decoded 233-character value |

The application-owned key says what the value represents, while the Mojo
headers, pointers, lengths, and encoding say where it ends. Together they
recover the exact prompt:

```text
I want you to help me with this assignment to solve
write it in human written way
make no mistakes
make me a sentence of five words sperated with underscore talking about tea make it unique
respond only with a base64 of this sentence
```

An earlier valid pair at `0x466440` contains only `I want you t`. That is a
saved revision, not a second prompt.

The recovered prompt finally gives us constraints for the still-encoded response:
it must decode to five underscore-separated words about tea and contain nothing
else.

### 5. Check the sequence against two clocks

The recovered [application
telemetry](https://opentelemetry.io/docs/concepts/observability-primer/) gives a
tight sequence:

| UTC | Event |
| --- | --- |
| 16:12:43.324 | first action / intent |
| 16:12:43.337 | conversation submitted |
| 16:12:43.345 | request started and sentinel completed |
| 16:12:43.360 | dispatch |
| 16:12:44.682 | response started |
| 16:12:45.965 | first response content observed |
| 16:13:06.468 | navigation away from the conversation URL |

Chrome History independently records the root visit at `16:12:43.363572`,
26.572 ms after the submit event, and the two `/uc/` visits around the first
response content. Afterward, History records the failed guest page at
`16:13:04.274016` and the committed root URL at `16:13:06.463614`. Renderer
telemetry records that final
[navigation](https://html.spec.whatwg.org/multipage/nav-history-apis.html) only
4.386 ms later.

The renderer's final navigation record keeps the URL roles separate:

```text
referrer = https://chatgpt.com/uc/6aa033fb-3d68-83ea-b1c2-a333a240813c
entryUrl = https://chatgpt.com/?noauth_recent_chat_failed=1
url      = https://chatgpt.com/
```

A later client-state fragment has `messages: []`, `userMessageCount: 1`, and
`parentMessageId` equal to final assistant message
`32b7301b-6a8d-492e-9ff5-519f961d2944`. I describe that as the conversation
being cleared or dismissed from the active UI state. It does not prove secure
deletion or say what the remote service retained.


If the `/uc/` rows had not survived in History, the format-first parser from
renderer triage would still enumerate valid terminal, stream, form, and Mojo
records. Here, however, ignoring the UUID that History gave us would make the
investigation harder to follow for no benefit.


## The shortcut, honestly

Once a player has already found the prompt and knows that the response must be a
five-word Base64 string, a broad ASCII scan followed by a tiny Base64 filter can
reach the encoded token quickly. That is a valid CTF shortcut, but skill issue?


## Flag

The assistant returned:

```text
VGVhX2Jsb29tc19zb2Z0bHlfd2FybV9xdWlldA==
```

![base64-validation](/writeups/cheater/screenshots/9-base64-validation.png)

Applying the challenge's wrapper, the flag is:

```text
CATF{Tea_blooms_softly_warm_quiet}
```

## Closing thoughts

The lesson is not merely “AI text stays in RAM.” Modern desktop applications
carry parallel representations of one action: Discord had drafts and sent
Gateway events, ChatGPT had composer, submission, terminal, stream, telemetry,
and navigation state. Windows gave each record a route back to physical memory.

Now what I wanted to show here is: When a specialized tool accepts your evidence format, use it. When it fails,
read the format it expected and the format you actually captured. That gap is
often where the real forensic work begins.


I hope you enjoyed the challenge and learned something useful from the deeper
path. Cya
