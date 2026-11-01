---
title: "What Survives of a ChatGPT Conversation in Windows RAM? Part 1: Browser Reconstruction"
published: 2026-11-01
description: "Part 1 of the Windows RAM research: developing a bounded-record method, then testing it in Chrome and Edge."
tags: [DFIR, Memory Forensics, Browser Forensics, Windows, ChatGPT, Volatility]
category: Research
image: /covers/post-chatgpt-windows-ram-memory-layers.png
draft: false
---

Jihun Joun recovered ChatGPT conversations from V8 heap snapshots by following object references. I wanted to know what I could prove from a full Windows memory image acquired after the activity. A heap snapshot gives me object boundaries and references. A raw image makes me recover the process map and record boundary first.

> Can I reconstruct a ChatGPT turn from Windows RAM without knowing the prompt, answer, conversation ID, message IDs, or offsets in advance?

An answer-looking sentence would not settle it. The same words might be in a browser record, my page-observation log, or the terminal I used to investigate. I needed to connect the prompt and response through the application's own IDs, then check that result against what was actually on screen. The parser would not know the prompt, answer, IDs, or offsets in advance.

Research series: **1. Reconstructing a browser turn** · [2. Browser state changes](/posts/chatgpt-browser-state-changes/) · [3. The native Codex CLI](/posts/codex-cli-windows-ram/)

## What would count as a reconstruction?

### Where the records can live

A conversation changes form while the page uses it. The typed prompt can appear in a client-side object before an answer exists. Response events can pass through a network buffer. The page can then hold a state object containing both messages. RAM may retain several copies of any of these, including copies in different encodings. A prompt found beside an answer in a hex view is not necessarily a turn.

Chromium spreads this work across processes. The browser process manages tabs and launches children. A renderer runs a page's JavaScript. [NetworkService](https://chromium.googlesource.com/chromium/src/+/main/services/network/README.md) handles network operations and may run in a utility process. The captures also contain a child whose command line names `storage.mojom.StorageService`. Chromium's [process model](https://chromium.googlesource.com/chromium/src/+/main/docs/process_model_and_site_isolation.md) means that neither the youngest renderer nor its PID alone identifies the chat tab. I first used `windows.pslist` and `windows.cmdline` to establish process roles, then `windows.memmap` to read their resident pages in virtual order.

The exact record form was something I had to discover in each client. The early captures eventually yielded `stream-item` JSON with a message ancestry chain. Later captures held a client-side submission object, a state object containing both messages, or [SSE-framed](https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation) response events. I worked from complete object boundaries and their IDs because a prompt found near an answer does not establish that they belong to one turn. The bytes and joins appear in the trials below.

### The proof I wanted

I scored a browser candidate against five fields recorded separately from the page:

| Symbol | Field                    |
| ------ | ------------------------ |
| `C`  | conversation ID          |
| `P`  | exact user prompt        |
| `R`  | exact assistant response |
| `U`  | user message ID          |
| `A`  | assistant message ID     |

A `5/5` string match was not enough by itself. Each parser had to establish the relationship from its own bounded records. The early `stream-item` chain, Chrome's state objects, and Edge's signed-in response stream each needed a different join rule. I scored all five fields where independent ground truth was available.

The parser did **not** receive any of the five ground-truth values. I recorded them from the URL and read-only DOM inspection. For close and navigation tests, I had to do that before changing the page. I used those observations for scoring only after sealing the RAM parser's output.

The browser screenshots show what was visible in the guest before or after acquisition. They are ground-truth observations, not images extracted from RAM.

I kept three levels of memory evidence separate throughout the tests:

| Evidence                                | What it proves                                               | What it does not prove                                                    |
| --------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------- |
| Exact string in the whole image         | Those bytes existed somewhere in physical RAM.               | Which process supplied them, or whether two strings belonged to one turn. |
| Exact string in a process mapping       | The bytes were reachable through that process's virtual map. | Exclusive ownership of a shared page, or a blind recovery.                |
| Bounded records joined by their own IDs | The surviving records describe one linked application event. | That the method works for every client build or every browser state.      |

Only the bounded-record result counted as a browser reconstruction.

I kept a JSON **ledger** for each capture. It is an audit record, not a browser history database: it records the page condition, acquisition time and image hash, selected processes, parser results, and the later comparison with what I observed on screen. The later exact-value searches have their own fields so they cannot quietly turn into a blind parser result.

## How I settled on the method

The first captures were for method development in a different ChatGPT client. I did not reset the VM between them, so a later image could contain fragments of an earlier chat. The controlled Chrome and Edge tests below use a separate VM and start from a client-stopped snapshot.

### The string counts looked convincing

I first searched a full WinPmem image for a prompt marker, answer, and IDs I already knew from the page. The [initial scan record](/research/chatgpt-windows-ram/pilot_iab_001_redacted_result.json) shows 368 ASCII prompt-marker hits, 302 answer hits, and 555 conversation-ID hits. I read the bytes around the prompt hits before treating those counts as evidence. A context classifier labelled 22 as DOM-capture copies, 97 as ground-truth copies, and 111 as tool or transcript copies. Manual inspection showed that the one hit it called record-like was another tool record. The counts confirmed byte presence, but could not establish that the browser still held a turn.


### PID 7608 was a false lead

I used `windows.pslist` and `windows.cmdline` to identify process roles, then `windows.memmap` to connect virtual pages to the physical image. Renderer PID 7608 seemed to contain the prompt, answer, and IDs. All 217 apparent hits were on kernel virtual pages included in its map. After I restricted the same map to addresses below `2^47`, that renderer had 7,179 resident user-space rows and none of those known-value hits. The PID alone had misled me.

That check set the page-reading rule for the parsers: scan resident user mappings, read in virtual order, and cross a page boundary only when the next virtual page is adjacent and resident. Two neighboring physical offsets do not necessarily belong to the same process object. I keep the source process and virtual address with every accepted record. The later Chrome parser also records the physical spans and a hash of the exact object bytes. The B1 commands show the process-role check in Kali WSL, and B5 follows an accepted object back to its bytes in the complete image.

### Two chats broke the first join rule

In the exploratory bytes, one format began with `{"type":"stream-item"}`. Its `encoded_item` carried `event:` and `data:` lines. The [bounded parser](/research/chatgpt-windows-ram/trial_iab_visible_002/parse_stream_items.py) searches for that structural prefix without receiving a prompt or ID. It reads at most 128 KiB across virtually adjacent resident pages and accepts one valid outer JSON object. From there, the [joiner](/research/chatgpt-windows-ram/method_v2/reconstruct_turns.py) groups records by conversation and turn, follows `parent_stream_item_id`, and requires a user ancestor, assistant start, response patch, matching marker, and completion on the same branch.

My first join rule failed when I put two completed chats in one image. Both renderers held complete records, but the user message appeared under `data.v.message` instead of the `data.input_message` shape I had accepted earlier. I added that observed form without relaxing the ID, ancestry, patch, marker, or completion checks. The revised joiner kept the two chats separate and matched five independently recorded fields for each. I then froze it before making a new visible turn, which it also matched `5/5`. The [two-chat result](/research/chatgpt-windows-ram/trial_iab_two_chats_004_results/result_v2_redacted.json), [freeze record](/research/chatgpt-windows-ram/FROZEN_METHOD_V2.json), and [fresh result](/research/chatgpt-windows-ram/trial_iab_visible_005_results/fixture_reconstruction_v2.json) keep development and the new-image check distinct.

I found a byte-counting mistake in that early parser after the tests. It used decoded character count to slice the source bytes for a record hash. In a [synthetic UTF-8 check](/research/chatgpt-windows-ram/PILOT_UTF8_DIGEST_BOUNDARY_20261001.json), a 55-byte record containing `café` produced a hash of only its first 54 bytes. The scored records used ASCII, but the linked parser needs a byte-length fix before its hashes can be relied on for multilingual records. The later Chrome state parser hashes the actual bounded bytes.

Closing or navigating away in the exploratory captures left known strings in the physical image without a complete joined record in active renderer maps. That is why I treat an exact byte hit, a mapped hit, and a reconstructed turn as different findings. It also gave me the next test: start ordinary Chrome and Edge from a known baseline, then see whether this record grammar survives and what other bounded formats appear.

## Baselines and trial B1

The B-series runs from B1 to B28. B23 and B24 each compare two captures under one number, while the Temporary Chat visible and blank captures have separate numbers, B25–B28. I gave the saved-memory and direct WinPmem captures of the signed-in Edge turn separate numbers because the acquisition method and timing changed. The B-series starts from a separate reset baseline and tests what survives in ordinary Chrome and Edge.

### A client-open pretest

For the follow-up work, I used the Research VM, Windows 10 Pro 22H2 with 5,792 MiB assigned RAM. An earlier VMware snapshot caught it with the clients running: five `ChatGPT.exe` renderers, three Chrome renderers, and two Edge renderers. I selected all ten by the image-derived process list and exact `--type=renderer` command lines, then ran both bounded browser grammars across their resident user mappings. Neither produced a signature. This was before the controlled follow-up prompts, so it is a **format-specific pretest**, not a claim that a signed-in account had no older history. The [snapshot scanner](/research/chatgpt-windows-ram/method_vmware_snapshot_v1/scan_vmware_snapshot.py) uses Volatility's process maps and VMware-aware MemProcFS reads to count those two record forms without exporting their contents. The [pretest ledger](/research/chatgpt-windows-ram/CLIENT_OPEN_SNAPSHOT_CONTROL_20261001.json) records the selected PIDs, page checks and zero counts. Its [run instructions](/research/chatgpt-windows-ram/method_vmware_snapshot_v1/README.md) give the setup.

This is a direct check from that client-open `.vmem` snapshot. `windows.pslist` identifies Chrome PID 2912 as a child of browser PID 8476. `windows.cmdline --pid 2912` supplies the `--type=renderer` flag.

[![Direct Volatility pslist and cmdline commands on the client-open VMware memory snapshot, showing Chrome renderer PID 2912](/research/chatgpt-windows-ram/screenshots/80-baseline-direct-volatility-renderer.png)](/research/chatgpt-windows-ram/screenshots/80-baseline-direct-volatility-renderer.png)

For this `.vmem` check, I read guest physical pages through VMware-aware layers. A guest physical address is not necessarily an offset in the `.vmem` file. The same pretest ledger keeps the mapping cross-check and page-sample counts.

### The client-stopped reset

Before trying ordinary browsers, I saved a repeatable snapshot with the target clients closed. In that saved VMware memory, `windows.pslist` found no active Chrome, Edge, ChatGPT, or Codex process. `windows.psscan` still found 45 exited target-name rows, representing 43 unique PID/start pairs. I also checked the saved file for four subsequent Edge turns' conversation IDs, prompt markers, and message IDs in UTF-8 and UTF-16LE. All 32 exact patterns were absent. This was a client-stopped reset, not a never-used machine. The [snapshot control](/research/chatgpt-windows-ram/RESET_SNAPSHOT_CONTROL_20261001.json) records both findings.

### Trial B1: leave the Edge chat empty

For B1, I opened an ordinary signed-in Edge window from that reset point and left it on a blank ChatGPT new chat. The sidebar was collapsed, and no experimental prompt had been entered. This is the actual page just before acquisition, cropped to the browser with the account greeting and avatar covered:

![Edge on an empty ChatGPT new-chat page before the no-submit memory capture, with account details redacted](/research/chatgpt-windows-ram/screenshots/14-edge-empty-control-redacted.png)

WinPmem acquired `edge-no-submit-control-001` over 24.926 seconds. The 7,147,094,016-byte image was copied through a private, pinned-TLS VM transfer. Its archive and decompressed SHA-256 both matched the guest acquisition record. The full image is not published. In Kali WSL, I verified it with `windows.info`, then used `windows.pslist` and `windows.cmdline` to identify Edge's renderer processes. With a verified B1 copy named `memory.raw`, the role check is short:

```bash
VOL="$HOME/volatility3/vol.py"
python3 "$VOL" -f memory.raw windows.info
python3 "$VOL" -f memory.raw windows.pslist | grep 'msedge.exe'
python3 "$VOL" -f memory.raw windows.cmdline --pid 7200
python3 "$VOL" -f memory.raw windows.cmdline --pid 9500
python3 "$VOL" -f memory.raw windows.cmdline --pid 10256
```

The PIDs above are the three active Edge renderers recorded in the B1 ledger. In the actual analysis I selected every active `msedge.exe` with an exact `--type=renderer` command-line argument, then generated each `windows.memmap`. The [reviewed control result](/research/chatgpt-windows-ram/edge_no_submit_control_001/RESULTS.json) records the process selection and result.

I first applied the [`stream-item` parser](/research/chatgpt-windows-ram/trial_iab_visible_002/parse_stream_items.py) and [v2 joiner](/research/chatgpt-windows-ram/method_v2/reconstruct_turns.py) developed above, with their hashes unchanged. I also tried a development scanner's UTF-8/UTF-16LE framing with a 1 MiB record cap:

| Edge renderer PID | Resident user-map rows | Frozen signature hits | Complete records | Joined turns | MemProcFS page samples matching |
| ----------------: | ---------------------: | --------------------: | ---------------: | -----------: | ------------------------------: |
|              7200 |                 61,458 |                     0 |                0 |            0 |                           32/32 |
|              9500 |                  7,396 |                     0 |                0 |            0 |                           32/32 |
|             10256 |                 35,636 |                     0 |                0 |            0 |                           32/32 |

The broader development scan also found zero `stream-item` signatures. MemProcFS independently agreed with Volatility on all 96 sampled virtual-to-physical translations and bytes. For this **no-submit state**, neither grammar found an accepted envelope in the resident renderer maps. I restored the client-stopped snapshot after this capture so the next test would start from the same baseline.

## Trials B2–B5: Chrome kept a turn in a different format

### Trial B2: find the record before writing a parser

The empty Edge page gave me a no-submit control. Next I needed a completed turn in an ordinary browser. In Chrome 154, I opened a fresh profile, submitted an observatory test prompt, waited for the answer, and acquired RAM with the page still open.

I took every active `chrome.exe` renderer from `windows.pslist` and `windows.cmdline`. I did not know which one held the chat, so all three B2 renderers went through the same scan.

I first tried that same frozen [`stream-item` parser](/research/chatgpt-windows-ram/trial_iab_visible_002/parse_stream_items.py) on all three. It found zero signatures, though the answer was visible. I then used the test prompt I had just entered to inspect its mapped-page neighborhood. This was how I learned the new format, so B2 is a development image. The known text helped me find a complete object, but it would not be an input to the finished parser. Near one copy I found JSON beginning with `{"backendConversationId":...}`. Its `messages` array contained both sides of the turn and their IDs. A plain prompt hit could not establish that relationship.

That gave me a structural search key, `{"backendConversationId":"`, rather than a prompt or an offset. I look for it in UTF-8 and UTF-16LE in each renderer's resident mappings. [Chracer](https://www.sciencedirect.com/science/article/pii/S2666281723001257) validates Chromium objects through symbol-derived layouts. I had no fixed C++ layout for this serialized state, so I recovered its JSON boundary from the bytes. `windows.memmap` supplied virtual-to-physical rows. My reader walks them in **virtual** order and overlaps 1 MiB chunks to catch a key at a chunk edge. It crosses a page only when the next virtual page is resident and adjacent, even if the physical pages are far apart.

At each hit, a quote- and escape-aware walker frames one JSON object within a 1 MiB cap. Strict decoding rejects broken text and duplicate keys. Schema checks require a string `backendConversationId` and a `messages` array whose entries have string `content`, `id`, and `role` fields. The [record parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) saves the exact byte hash and virtual and physical spans, then deduplicates identical copies. The [turn joiner](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py) takes the final adjacent `user` and `assistant` entries **inside that object** and checks whether the outer `parentMessageId` repeats the assistant ID. It does not join separate objects merely because their text is nearby.

The B2 scan produced 13 complete occurrences representing five unique objects, all in PID 3400, and one linked turn. Its [post-capture score](/research/chatgpt-windows-ram/chrome_anonymous_cdp_visible_001/score.json) matched all five independently recorded fields. MemProcFS reread all 13 accepted occurrences and matched their bytes and translations.

I froze the rule before testing a new prompt. The [freeze manifest](/research/chatgpt-windows-ram/FROZEN_CHROME_STATE_V1.json), [parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py), [joiner](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py), and [two-record synthetic fixture](/research/chatgpt-windows-ram/chrome_state_synthetic_fixture.json) are available to replay. The state object has no completion event, so the joiner emits a linked candidate. I call it completed when the separately observed page shows that the answer finished.

### Trial B3: test the frozen rule on a new turn

I froze the Chrome [parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) and [joiner](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py) at `06:14:24 UTC`, then opened a second Chrome profile with its own `--user-data-dir`. The first observatory profile stayed open. I submitted a different lighthouse prompt, waited for the answer, and acquired a new image. Now the method had to separate two conversations without receiving either prompt or ID as input.

For the fresh lighthouse turn, the recovered state made the join explicit:

| Field in the bounded record | Recovered value                                                                        |
| --------------------------- | -------------------------------------------------------------------------------------- |
| `backendConversationId`   | `6abcac2e-69a8-83ea-8f62-105367d59333`                                               |
| `messages[0]`             | `user`, ID `1e6f9b28-0080-4e47-9d71-f3886d611b95`, with the exact submitted prompt |
| `messages[1]`             | `assistant`, ID `0b29b1a8-ab90-49c0-bc04-7065348999a5`, with the lighthouse answer |
| `parentMessageId`         | `0b29b1a8-ab90-49c0-bc04-7065348999a5`, the same assistant ID                        |

The assistant content reads: “At the fictional lighthouse museum, **Marrow Gleam** preserves 437 nautical relics beneath a lantern that still sweeps the midnight sea.” The JSON stores Markdown `**` around the name, which the page renders as bold. This state object links the text and IDs, but does not give me a submission timestamp. The acquisition and live-observation times come from separate records.

To replay the mapped scan, run these commands so the linked parser paths under `scripts/ram-research/` resolve. `IMAGE` names the private, verified B3 image. The six PIDs below came from `windows.pslist` and direct `windows.cmdline` output. They are an input list for the scan, not numbers built into the parser:

```bash
IMAGE=private/chrome_anonymous_cdp_visible_002/memory.raw
OUT=private/chrome_anonymous_cdp_visible_002/replay-01
VOL="$HOME/volatility3/vol.py"
mkdir -p "$OUT"
python3 "$VOL" -f "$IMAGE" windows.pslist | grep 'chrome.exe'
python3 "$VOL" -f "$IMAGE" windows.cmdline | grep -- '--type=renderer'
PIDS=(672 3400 4324 5076 6652 7032)
parsed=()
for PID in "${PIDS[@]}"
do
  python3 "$VOL" -r json -f "$IMAGE" windows.memmap --pid "$PID" > "$OUT/renderer_${PID}_memmap.json"
  python3 scripts/ram-research/chrome_state_records.py --image "$IMAGE" --memmap "$OUT/renderer_${PID}_memmap.json" --output "$OUT/renderer_${PID}_chrome_state_private.json"
  parsed+=(--parsed "$OUT/renderer_${PID}_chrome_state_private.json")
done
python3 scripts/ram-research/chrome_state_turns.py "${parsed[@]}" --output "$OUT/chrome_v1_turns_private.json"
```

The parser files refuse to overwrite an existing output. Use an empty private output directory for a second run. The same sequence, with the PIDs from each image, was applied to B2 and B4.

The fresh image recovered the *old* observatory turn and the *new* lighthouse turn separately. The lighthouse candidate matched the page's conversation URL, both message-element IDs, exact prompt, and rendered response text. No cross-join appeared. The [B3 post-capture score](/research/chatgpt-windows-ram/chrome_anonymous_cdp_visible_002/score.json) was `5/5`. MemProcFS reread all 18 accepted occurrences in B3 and matched Volatility's bytes and translations. The [reviewed measurements](/research/chatgpt-windows-ram/CHROME_FOLLOWUP_20260930.json) include both image hashes and per-renderer counts.

![Anonymous Chrome page with the completed lighthouse test prompt and answer](/research/chatgpt-windows-ram/screenshots/20-chrome-heldout-visible.png)

*The page was captured after RAM acquisition for the independent score.*

### Trial B4: leave the lighthouse tab

Then I navigated the *same* lighthouse tab to Example Domain. Chrome's target list showed `https://example.com/` before the third WinPmem capture, taken about two minutes later. The frozen parser scanned all six active renderers again.

PID 5076, which had held the lighthouse record while its tab was open, was no longer active. New renderer PID 6280 belonged to the same browser profile: its `pslist` parent was PID 3392, whose `cmdline` still named the lighthouse test profile. PID 6280 yielded no complete state object. The older observatory profile was still open and gave one candidate from PID 3400.

A separate, post-run check found none of the lighthouse conversation ID, prompt marker, or invented answer name as exact UTF-8/UTF-16LE bytes in those active renderer mappings. MemProcFS agreed on the two old record occurrences and 32 sampled pages from PID 6280. The [navigation result](/research/chatgpt-windows-ram/chrome_anonymous_cdp_away_003/score.json) is a failure to reconstruct **that turn from the active renderers**, not proof that every physical copy was erased.

| Trial | Capture                                    | Active Chrome renderers | Complete Chrome-state records                                    |                   Joined turns |
| ----- | ------------------------------------------ | ----------------------: | ---------------------------------------------------------------- | -----------------------------: |
| B2    | Observatory, grammar development           |                       3 | 13 occurrences / 5 unique, all in PID 3400                       |                              1 |
| B3    | Lighthouse, new turn after freeze          |                       6 | Old profile: 2 / 1 in PID 3400. New profile: 16 / 5 in PID 5076. |        2, one per conversation |
| B4    | Lighthouse tab navigated to Example Domain |                       6 | Old profile: 2 / 1 in PID 3400. Other five renderers: 0.         | 1 old turn, 0 lighthouse turns |

### Trial B5: a visible answer without a text probe

The earlier page check had copied the answer as text, which could leave another copy in RAM. For this trial I submitted a fresh ceramic-sextant question without retrieving the answer text. I checked only the URL and the number of message elements, then read the finished answer from a PNG screenshot. The same two-message page was still open after acquisition.

![Actual completed Chrome turn captured as pixels before the low-observer RAM acquisition](/research/chatgpt-windows-ram/screenshots/46-chrome-visible-screenonly-crop.png)

#### From the parser result back to RAM

I checked process roles before reading bytes. `windows.pslist` shows Chrome parent PID 9372 and three child candidates:

[![Volatility pslist output from the complete B5 RAM image, showing the Chrome browser parent and three child candidates](/research/chatgpt-windows-ram/screenshots/71-b5-volatility-pslist.png)](/research/chatgpt-windows-ram/screenshots/71-b5-volatility-pslist.png)

The process tree alone does not establish their roles. `windows.cmdline --pid 1872` confirms one child's `--type=renderer` argument. The [B5 ledger](/research/chatgpt-windows-ram/CHROME_VISIBLE_SCREEN_ONLY_20261001.json) lists the other two renderer PIDs and their scan counts.

[![Volatility cmdline output from the complete B5 RAM image, showing the renderer role in PID 1872](/research/chatgpt-windows-ram/screenshots/72-b5-volatility-renderer-cmdline.png)](/research/chatgpt-windows-ram/screenshots/72-b5-volatility-renderer-cmdline.png)

The renderer address came from the [record parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py), not from searching for the ceramic-sextant prompt. I first generated `windows.memmap` for each renderer. The frozen parser read those resident pages in virtual order, found the structural key `{"backendConversationId":"`, framed a complete JSON object, and wrote its `virtual_addresses` and `source_spans`. Each source span contains a virtual address and the physical address calculated from the memmap row used to read it. The prompt, answer, and conversation ID were absent from the parser's inputs.

I reran PID 1872 against the complete B5 image. The parser output was byte-identical to the original result: two mapped occurrences of one complete state, followed by one joined turn. The private record output gives the second source span as virtual `107253969511692` (`0x618c02c0e50c`) and physical `2613699852` (`0x9bc9e50c`). That is the address I later opened in HxD. The terminal still says `development` because that label was written into the B2 parser. Its source hash stayed unchanged for B5.

![The frozen state parser and joiner run on the complete B5 RAM image, reporting two mapped occurrences of one state and one joined turn.](/research/chatgpt-windows-ram/screenshots/85-b5-parser-direct.png)

The physical address in `source_spans` is derived from Volatility's map. Reading that offset in the raw image and checking the record bytes with MemProcFS were separate checks. The later `windows.memmap` screenshot below displays the row used for this copy, after the parser had already selected it.

#### A prompt copy is not yet a conversation

I took the other address trail in reverse. After acquisition, I searched the full image for the known test prompt in UTF-8 and UTF-16LE, inspected the surrounding bytes, and framed the complete object that contained one UTF-16LE hit. I then checked which process map reached its physical page. This was a diagnostic of what survived on the submission side. It did not find the completed renderer object and did not contribute to the turn score.

That prompt check found a UTF-16LE copy inside a 1,140-byte JSON object. Its opening brace is at physical `0x261e6690`, which is `0x690` bytes into page `0x261e6000`. I checked the process maps for that page. `windows.cmdline` identifies PID 9520 as StorageService, and its `windows.memmap` row maps virtual page `0x2dcc0016c000` to physical page `0x261e6000`. The record therefore starts at virtual `0x2dcc0016c690`. The filter in the screenshot isolates the row **after** I found the record. Neither this address nor the known prompt was an input to the completed-turn parser:

[![Direct Volatility cmdline and memmap commands on the complete B5 RAM image, showing StorageService PID 9520 and its mapped page](/research/chatgpt-windows-ram/screenshots/81-b5-direct-service-and-map.png)](/research/chatgpt-windows-ram/screenshots/81-b5-direct-service-and-map.png)

The first bytes at `0x261e6690` are `7b 00 22 00`, the UTF-16LE opening `{"`. The bounded 1,140-byte object contains an `actionPath` of `/unauth-mweb/conversation?lightweight_authenticated=0`, a `conversationState` string with `"messages":[]` and `"parentMessageId":"client-created-root"`, an `operationId`, the exact prompt, a `createdAt` value, and `owner.mode` set to `anonymous`. The timestamp decodes to `2026-10-01 12:18:20.056 UTC`, just after the prompt was submitted. These HxD crops come from the **complete raw image**:

[![HxD excerpts from the complete B5 RAM image showing UTF-16LE action path, empty message state and operation ID](/research/chatgpt-windows-ram/screenshots/76-b5-submission-structure-full-ram.png)](/research/chatgpt-windows-ram/screenshots/76-b5-submission-structure-full-ram.png)

[![HxD excerpts from the complete B5 RAM image showing the test prompt and anonymous owner field in the same UTF-16LE record](/research/chatgpt-windows-ram/screenshots/77-b5-prompt-owner-full-ram.png)](/research/chatgpt-windows-ram/screenshots/77-b5-prompt-owner-full-ram.png)

This is submission-side **client state**, not a captured HTTP request. Its `messages` array is empty. I cannot extract an assistant answer or a final conversation ID from it, and its `operationId` does not join it to an unrelated renderer object. The [exact UTF-16LE record](/research/chatgpt-windows-ram/evidence/chrome-visible-010-submission-side-record-utf16le.bin) and [figure provenance](/research/chatgpt-windows-ram/B1_B5_FIGURE_PROVENANCE_20261030.json) allow the byte and address checks without publishing the full image.

#### The completed renderer state

Renderer PID 1872 mapped a different, 558-byte UTF-8 object. It has a `backendConversationId`, a `user` message, an `assistant` message, and an outer `parentMessageId`. Its first `{` is at physical `0x9bc9e50c`. Eight bytes before it, `2e 02 00 00` is 558 in little-endian, matching the object's length in this copy. The parser does not depend on those preceding bytes.

[![HxD view of the complete B5 RAM image showing the 558-byte renderer state object opening and its preceding length bytes](/research/chatgpt-windows-ram/screenshots/64-chrome-state-record-full-ram-annotated.png)](/research/chatgpt-windows-ram/screenshots/64-chrome-state-record-full-ram-annotated.png)

The frozen Chrome parser scanned all three B5 renderers. PID 1872 held two copies of that complete state object. PIDs 5172 and 7648 had no signature. The user and assistant IDs, together with `parentMessageId`, joined one turn.

I sealed that output **before** transcribing the screenshot. The URL supplied an independent conversation ID, the submitted text supplied the prompt, and the pre-acquisition PNG supplied the finished answer. All three matched the RAM candidate, so this trial scored **3/3**. The page check recorded only that two message elements existed. It did not record their IDs. The state object contains a user ID and an assistant ID, and its `parentMessageId` repeats the assistant ID, but I had no separate page IDs to check their exact values against. The denominator is three because only three fields had independent observations. MemProcFS verified both record copies and translations. A later flat-physical scan found two copies with the **same record SHA-256** as PID 1872's mapped output, a positive check on that [physical-scan method](/research/chatgpt-windows-ram/PHYSICAL_CHROME_STATE_CONTRAST_20261001.json). The [screen-only visible ledger](/research/chatgpt-windows-ram/CHROME_VISIBLE_SCREEN_ONLY_20261001.json) records the hashes and score.

For one of PID 1872's two occurrences, `windows.memmap` placed virtual page `0x618c02c0e000` at physical page `0x9bc9e000`. The parser's record began at virtual `0x618c02c0e50c`. Adding its `0x50c` displacement to the physical page gives `0x9bc9e50c` in the decompressed RAM image. I read that 4 KiB page separately and checked the 558-byte slice against the parser's accepted SHA-256: `6c5d1ebbac3abb825c97f227773edbce020bb37058ccc541c61d2e363d1f5c3c`. The [mapping and extraction record](/research/chatgpt-windows-ram/LOW_LEVEL_CHROME_RECORD_20261016.json) and [exact record bytes](/research/chatgpt-windows-ram/evidence/chrome-visible-010-state-record.txt) make that check reproducible without the rest of RAM.

[![Volatility memmap output from B5, showing the virtual page mapped to a physical page in the complete RAM image](/research/chatgpt-windows-ram/screenshots/68-chrome-virtual-to-physical-evidence.png)](/research/chatgpt-windows-ram/screenshots/68-chrome-virtual-to-physical-evidence.png)

*The screenshot shows the `windows.memmap` row for the parser's virtual page. I selected that row for display after the parser recorded its source address. The `Offset in File` column refers to an optional process dump, which was disabled here. For the complete WinPmem image I used the `Physical` value and added the `0x50c` displacement. See [Volatility 3's `memmap` implementation](https://github.com/volatilityfoundation/volatility3/blob/v2.8.0/volatility3/framework/plugins/windows/memmap.py).*

I also read both B5 offsets directly from the complete raw image in a terminal. The top `xxd` command shows `7b 00 22 00` at the start of the UTF-16LE submission-side record. The lower command shows `2e 02 00 00` at `0x9bc9e504` and the renderer state's UTF-8 `{` at `0x9bc9e50c`. The commands read the raw image, not the extracted records.

[![Terminal xxd commands showing the UTF-16LE submission record and UTF-8 completed-state record at their physical offsets in the complete B5 RAM image](/research/chatgpt-windows-ram/screenshots/79-b5-direct-raw-byte-views.png)](/research/chatgpt-windows-ram/screenshots/79-b5-direct-raw-byte-views.png)

[![Four excerpts from the same complete-image HxD view, showing the B5 prompt, response, and message IDs inside one bounded JSON copy](/research/chatgpt-windows-ram/screenshots/74-chrome-state-fields-full-ram.png)](/research/chatgpt-windows-ram/screenshots/74-chrome-state-fields-full-ram.png)

*These excerpts come from the same complete raw image and the same 558-byte record. The labeled bytes are unchanged HxD pixels.*

At physical `0x9bc9e564`, the prompt begins. The user ID starts at `0x9bc9e5f8`. The assistant text starts at `0x9bc9e639`, followed by its ID at `0x9bc9e6b1`. That ID appears again as `parentMessageId` starting at `0x9bc9e6ff`. The object closes at `0x9bc9e739`. These are positions in this one observed JSON copy, not offsets the parser hard-codes. I first recover the whole object, then compare its decoded fields. The later Edge Unicode turn shows why I also had to handle UTF-16LE.

## Trials B6–B9: Edge used the Chrome format, including UTF-16LE

B1's signed-in blank page had no completed conversation. For B6–B8, I restored the client-stopped snapshot before each turn, started Edge 154 with a fresh anonymous profile, and acquired an image while the answer was still on screen. I checked the page state before each acquisition.

The B1 image was acquired early on September 30. At that point I had the earlier `stream-item` method, so that was its first check. Later on September 30, B2 exposed the bounded state-object format and I froze a second parser. I then ran that parser back over the **same B1 image**: zero signatures in all three renderers and zero joined turns. A scan of the hash-verified full physical image also found zero signatures for that format. This retrospective control is why two parsers appear beside one capture. It did not change the B1 acquisition, and the new Edge turns below were tested with the already frozen state parser. The [control record](/research/chatgpt-windows-ram/edge_no_submit_control_001/RESULTS.json) keeps the checks dated separately.

### Trials B6–B8: completed Edge turns

The earlier `stream-item` parser looks for linked event records. It found zero signatures in these three completed Edge images. The parser I developed on Chrome in B2 looks for a ChatGPT state object with `backendConversationId` and `messages`. I named it after the browser where I first found that format. The code reads a renderer's memmap and checks the JSON, and it already handles UTF-8 and UTF-16LE. Edge presented the same object, so I kept the parser unchanged and ran it on every active `msedge.exe --type=renderer` found by Volatility. This is the same process-role check as B1:

```bash
python3 "$VOL" -f "$IMAGE" windows.pslist | grep 'msedge.exe'
python3 "$VOL" -f "$IMAGE" windows.cmdline | grep -- '--type=renderer'
```

For each selected PID I generated `windows.memmap`, ran the same `chrome_state_records.py`, and passed *all* parsed renderer files to `chrome_state_turns.py`. No prompt, URL ID, message ID, or offset entered those commands. The post-capture comparison used the conversation URL, the two message-element IDs and the rendered page text.

| Trial | Edge state after a fresh snapshot restore               | Active renderer PIDs | Complete occurrences / unique state objects | Joined turns | Post-capture match |           MemProcFS |
| ----- | ------------------------------------------------------- | -------------------- | ------------------------------------------: | -----------: | -----------------: | ------------------: |
| B6    | First completed turn                                    | 9140, 10540          |                              17 / 5 in 9140 |            1 |                5/5 |       17/17 records |
| B7    | Completed turn with `مرصد`, `café`, and `🌙` | 4468, 9428           |                              17 / 5 in 9428 |            1 |                5/5 |       17/17 records |
| B8    | Third completed turn                                    | 1904, 8196           |                               9 / 4 in 1904 |            1 |                5/5 |         9/9 records |
| B9    | New turn, then same tab to Example Domain               | 6724, 10620          |                                       0 / 0 |            0 |       No candidate | 64/64 sampled pages |

The second Edge turn carried the same state-object grammar, but its full-content copies were UTF-16LE. The frozen parser handled them without a new branch. As in B5, `windows.memmap` was an input to the blind parser. Its accepted `source_spans` led to the HxD address afterward. For PID 9428, one accepted object starts at virtual `0xf501295a44`. The memmap row places page `0xf501295000` at physical page `0x57b40000`, so the `0xa44` page displacement puts the record at `0x57b40a44` in the full image. No Arabic word, answer text, or message ID was used to locate it. The first four bytes are `7b 00 22 00`, the UTF-16LE encoding of `{"`. The object occupies 1,276 bytes, ends before the page boundary, and matches the parser's accepted record byte for byte. The [full-image figure record](/research/chatgpt-windows-ram/LOW_LEVEL_FULL_RAM_FIGURES_20261027.json) gives the image and record hashes.

[![Cropped HxD view of the complete Edge RAM image, with the UTF-16LE opening and Arabic, accented, and emoji bytes outlined and labeled](/research/chatgpt-windows-ram/screenshots/65-edge-unicode-bytes-full-ram-annotated.png)](/research/chatgpt-windows-ram/screenshots/65-edge-unicode-bytes-full-ram-annotated.png)

At `0x57b40c18`, `45 06 31 06 35 06 2f 06` decodes to `مرصد`. A few bytes later, `e9 00` supplies the `é` in `café`. The four bytes `3c d8 19 df` are the [UTF-16 surrogate pair](https://www.unicode.org/faq/utf_bom.html) for `🌙`. HxD's right pane was set to ANSI, so those characters look wrong there. The hex values show why a UTF-8-only scan would miss this copy of the record.

Farther down the object, the assistant message ID begins at `0x57b40e2e`. The `parentMessageId` value begins at `0x57b40eca` and repeats the same 36-character ID.

[![Two cropped regions of the same full-memory Edge record in HxD, with the assistant ID and matching parentMessageId prefixes outlined and labeled](/research/chatgpt-windows-ram/screenshots/66-edge-assistant-parent-id-full-ram-annotated.png)](/research/chatgpt-windows-ram/screenshots/66-edge-assistant-parent-id-full-ram-annotated.png)

The joiner compares the full values inside this one bounded object. The [published 1,276-byte record](/research/chatgpt-windows-ram/evidence/edge-unicode-002-state-record-utf16le.bin) makes that equality and the highlighted UTF-16LE bytes checkable without releasing the memory image.

My *first scorer* called the response a mismatch: it stripped `**` bold markers but left Markdown's two spaces before a [hard line break](https://spec.commonmark.org/0.31.2/#hard-line-breaks). The page's visible text has the line break, not those two spaces. I kept that initial 4/5 score, made the post-capture display comparison recognize only these two observed Markdown decorations, and got 5/5. The RAM parser and its frozen hashes did not change.

![Anonymous Edge page after the Unicode trial, showing the test prompt and rendered response](/research/chatgpt-windows-ram/screenshots/21-edge-unicode-visible.png)


### Trial B9: navigate the completed tab away

I recorded the completed turn's URL, text, and both message IDs while it was visible. Then I moved that **same** tab to Example Domain and checked that Edge's target list showed `https://example.com/`. WinPmem began 27.7 seconds later. The frozen state parser found zero signatures and no joined turn in either active Edge renderer. Only after saving that result did I search for the known conversation ID, prompt marker, answer name, and message IDs. None appeared in those two renderer maps.

I checked the process that might have held the old page. [`windows.psscan`](https://github.com/volatilityfoundation/volatility3/blob/v2.8.0/volatility3/framework/plugins/windows/psscan.py) found Edge child PID 11068, created before the turn and exited in the same second as navigation. Its parent was the Edge browser process, but its command line was gone. That timing does not establish its Chromium role.

I tried to recover more from the scanned `_EPROCESS` after [`windows.memmap`](https://github.com/volatilityfoundation/volatility3/blob/v2.8.0/volatility3/framework/plugins/windows/memmap.py) returned no rows. Its saved page-table pointer could translate neither the PEB nor the executable base, while the active browser parent's pointer translated both. A [small Volatility probe](/research/chatgpt-windows-ram/method_psscan_vad/psscanvad.py) called `get_vad_root()` on that scanned object and found a null root. [`windows.handles --offset 0x13aa0c080`](https://github.com/volatilityfoundation/volatility3/blob/v2.8.0/volatility3/framework/plugins/windows/handles.py) returned no entries, and [`windows.thrdscan`](https://github.com/volatilityfoundation/volatility3/blob/v2.8.0/volatility3/framework/plugins/windows/thrdscan.py) found no thread with PID 11068. I had a surviving process object, but no usable old user-space map or command line. The [exited-child check](/research/chatgpt-windows-ram/EDGE_EXITED_CHILD_20261031.json) records each result. I cannot use the loose physical hits below to say which bytes this child once mapped.

The known-value search over the **full physical image** found all five values somewhere. I mapped the hits I could back to the eight active processes in this Edge browser tree:

| Process after navigation            | Exact fragments in its resident user mappings   |
| ----------------------------------- | ----------------------------------------------- |
| Browser parent                      | Conversation ID, prompt marker, user message ID |
| NetworkService                      | Conversation ID, answer name                    |
| StorageService                      | Conversation ID, prompt marker                  |
| SearchIndexer                       | Conversation ID                                 |
| Two active renderers, GPU, crashpad | None of those five values                       |

MemProcFS reread 11 mapped hits in the four non-renderer processes and matched their bytes and translations. The assistant message ID was present in physical RAM but in none of those eight active Edge maps. These fragments did not connect the prompt to an answer. They might include copies from my own observation or the file cache. The [Edge residue ledger](/research/chatgpt-windows-ram/EDGE_POST_NAV_RESIDUE_20261001.json) has the counts for each process.

The earlier Chrome navigation capture had a complication: the first *observatory* chat stayed open in one Chrome profile while I navigated the *lighthouse* chat away in another. To check the lighthouse turn, I counted only the nine processes in its browser tree. Its parent mapped the conversation and user IDs, StorageService mapped the prompt marker, and its three active renderers mapped none of the five tested values. The full image still held the conversation ID, prompt marker, and user ID, but no exact answer name or assistant ID in either encoding. The lighthouse renderer PID 5076 was absent from both `pslist` and `psscan`. MemProcFS matched four representative mapped hits. The [Chrome residue ledger](/research/chatgpt-windows-ram/CHROME_POST_NAV_RESIDUE_20261001.json) records that profile-specific check.

Finally I ran the unchanged state-object parser over both **full physical images**, without giving it any known text or IDs. Edge had zero signatures. Chrome had four complete copies of one 699-byte record. Its hash and all five fields matched the older observatory chat, whose tab was still open. Two copies mapped to its renderer PID 3400. The other two had no user mapping among the enumerated processes. None was the navigated lighthouse turn. The [physical scan ledger](/research/chatgpt-windows-ram/NAVIGATION_PHYSICAL_STATE_20261001.json) keeps this result separate from the known-value byte search. A flat physical scan can also miss a record split across nonadjacent physical pages. These captures show what the tested records and mappings yielded after navigation. They do not measure a Chrome-versus-Edge retention rate.

The [four-capture Edge ledger](/research/chatgpt-windows-ram/EDGE_FOLLOWUP_20261001.json) records image hashes, PIDs, parser counts and the distinct scoring paths. The state-object method found a turn in three reset-based visible-answer images, but not in the no-submit control or the navigation image.

## Conclusion: what the browser records established

I could reconstruct a browser turn from a full Windows image when its bounded records and identifier links survived. Ordinary Chrome yielded state objects that linked the prompt, answer, conversation ID, and both message IDs. That method also recovered fresh turns in three reset-based Edge captures, including a UTF-16LE record. In B5, the mapped virtual and physical addresses led back to the exact state bytes in the complete image.

The no-submit Edge control yielded no accepted turn. After navigation, the frozen state parser found no completed turn from the tab that had moved away. Chrome's later image still held records from a different chat whose tab remained open, so those records did not count for the navigated turn. Closing and reloading tabs gave me the next question, which I test in [Part 2](/posts/chatgpt-browser-state-changes/).

## From the research to Cheater at CATF 2026

The research question came first. I later introduced the idea in **Cheater**, my CATF 2026 DFIR challenge, as a practical case: a student might have asked a friend on Discord or used an anonymous ChatGPT session, and the investigator has to prove which path produced the suspicious answer.

The challenge is intentionally cleaner than this experiment matrix. Reconstructed Chrome History gives the player a conversation UUID, and several independent renderer representations must agree before the prompt and response are accepted. The [Cheater author writeup](/posts/cheater-catf-2026/) follows that image from process triage to the flag.

The ordinary-browser captures in this article, the state-change tests in [Part 2](/posts/chatgpt-browser-state-changes/), and the native CLI tests in [Part 3](/posts/codex-cli-windows-ram/) happened after CATF. They are separate evidence from the challenge image.

## Evidence and audit files for the series

The experiment ledgers include hashes, process selections, parser outputs, and the separate post-capture comparisons. The full index is here for anyone who wants to check an individual trial.

<details>
<summary>Open the full evidence index</summary>

- [Laboratory report](/research/chatgpt-windows-ram/REPORT.md): the dated record, including failed checks and deviations.
- [Trial manifest](/research/chatgpt-windows-ram/TRIAL_MANIFEST.json): conditions, capture windows, hashes, and image disposition.
- [Frozen v2 manifest](/research/chatgpt-windows-ram/FROZEN_METHOD_V2.json): parser, joiner, and runner hashes.
- [September 29 follow-up manifest](/research/chatgpt-windows-ram/FOLLOWUP_MANIFEST_20260929.json): three native captures, method freezes, different field sets and unchanged failures.
- [Post-hoc CLI request/core results](/research/chatgpt-windows-ram/CLI_REQUEST_CORE_RETROSPECTIVE_20261001.json) and [method](/research/chatgpt-windows-ram/method_cli_request_core_v1/README.md): a separately labeled four-field join on three retained images, with no change to the earlier frozen scores.
- [Fresh CLI request/core trial](/research/chatgpt-windows-ram/CLI_REQUEST_CORE_PROSPECTIVE_20261001.json): one new turn after the method freeze, its verified capture hashes, image-selected native/relay PIDs, four exact host fields and MemProcFS check.
- [September 30 Edge control](/research/chatgpt-windows-ram/edge_no_submit_control_001/RESULTS.json): reset state, renderer selection, page-map checks and zero accepted records.
- [Client-open pretest snapshot](/research/chatgpt-windows-ram/CLIENT_OPEN_SNAPSHOT_CONTROL_20261001.json): all ten active Chrome, Edge, and `ChatGPT.exe` renderers mapped with VMware-aware reads. Neither tested browser grammar yielded a signature.
- [October 1 Edge follow-up](/research/chatgpt-windows-ram/EDGE_FOLLOWUP_20261001.json): three reset-based completed turns, Unicode scoring, and one navigated-away state under the frozen Chrome method.
- [Post-navigation residue](/research/chatgpt-windows-ram/EDGE_POST_NAV_RESIDUE_20261001.json): exact-value physical and mapped-process counts after the Edge turn navigated away. This diagnostic is not blind reconstruction.
- [Edge close-tab trial](/research/chatgpt-windows-ram/EDGE_CLOSE_TAB_20261001.json): a separate completed turn, verified tab close, direct WinPmem acquisition, frozen parser result, post-hoc residue and MemProcFS checks.
- [Edge close-tab physical SSE scan](/research/chatgpt-windows-ram/EDGE_CLOSE_PHYSICAL_SSE_20261001.json): hash-verified full-image event framing, with 33 structural prefixes but zero complete events.
- [Edge close-tab observer-copy check](/research/chatgpt-windows-ram/EDGE_CLOSE_OBSERVER_COPY_20261001.json): the sole exact full-answer physical hit lies inside the probe's parsed `textTail` JSON, not an active Edge map.
- [Chrome close-tab trial](/research/chatgpt-windows-ram/CHROME_CLOSE_TAB_20261001.json): a reset-based completed turn, verified tab close, direct WinPmem acquisition, zero-turn frozen parser result and scoped post-hoc byte checks.
- [Chrome close-tab phrase provenance](/research/chatgpt-windows-ram/CHROME_CLOSE_PHRASE_PROVENANCE_20261001.json): two of seven physical answer-phrase hits are probe `textTail` copies.
- [Chrome close-tab physical-owner check](/research/chatgpt-windows-ram/CHROME_CLOSE_PHYSICAL_OWNER_20261001.json): two further hits map to `vmtoolsd.exe`. Three have no user mapping in the process enumeration.
- [Reverse residue audit](/research/chatgpt-windows-ram/REVERSE_RESIDUE_AUDIT_20261031.json) and its [known-value checker](/research/chatgpt-windows-ram/reverse_known_value_audit.py): a later, explicitly post-capture search from answer bytes to process mappings and observation-file context in the close and reload trials. It does not create a blind turn.
- [Chrome same-tab reload](/research/chatgpt-windows-ram/CHROME_RELOAD_20261001.json): a completed anonymous turn returning to new chat on reload, zero joined states in active renderers, and separately verified full-text residue.
- [Chrome screen-only reload repeat](/research/chatgpt-windows-ram/CHROME_RELOAD_SCREEN_ONLY_20261001.json): the answer observed as screenshot pixels rather than controller text, zero joined states, and a post-seal exact answer-sentence hit in one active renderer.
- [Chrome screen-only visible turn](/research/chatgpt-windows-ram/CHROME_VISIBLE_SCREEN_ONLY_20261001.json): a fresh completed turn observed as screenshot pixels, one internally linked frozen-method candidate, post-seal C/P/R score of 3/3, and two MemProcFS-verified record copies.
- [Chrome two-tab contrast](/research/chatgpt-windows-ram/CHROME_TWO_TABS_CLOSE_ONE_20261001.json): two completed turns in one browser and one image, one tab closed, one still open. The frozen reconstruction is separate from the checked observer residue.
- [Flat-physical Chrome-state contrast](/research/chatgpt-windows-ram/PHYSICAL_CHROME_STATE_CONTRAST_20261001.json): four hash-verified whole-image scans, with two visible-turn positive controls and no process-attribution claim.
- [Chrome two-turn chat](/research/chatgpt-windows-ram/CHROME_MULTITURN_VISIBLE_20261001.json): two completed turns in one still-open tab, six bounded state occurrences, two separate joined pairs, independent 5/5 scores, and MemProcFS checks.
- [Chrome unsent-draft control](/research/chatgpt-windows-ram/CHROME_DRAFT_NOSUBMIT_20261001.json): a typed but never-submitted prompt, zero frozen completed-state candidates, separately checked exact-byte residue, and an actual page screenshot.
- [Signed-in Chrome visible turn](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_VISIBLE_20261015.json): a new completed turn in the same profile as the no-submit control. It yielded one bounded user-message envelope and exact answer copies in mapped RAM, but zero accepted blind prompt–answer joins.
- [Signed-in Chrome paired control and navigation trial](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_PAIRED_20261015.json): two no-navigation images, then a fresh visible-to-blank pair, with capture windows, real screenshots, hashes, bounded-record changes, and post-hoc exact-byte checks kept separate.
- [Earlier signed-in Chrome after-navigation image](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_AWAY_20261015.json): the nine-hour-later blank-tab capture, process exit during acquisition, zero accepted records, and exact-text residue in the browser parent and exited renderer.
- [Chrome post-navigation residue](/research/chatgpt-windows-ram/CHROME_POST_NAV_RESIDUE_20261001.json): the same diagnostic on the separate lighthouse profile, without mixing in the older still-open conversation.
- [September 30 Chrome follow-up](/research/chatgpt-windows-ram/CHROME_FOLLOWUP_20260930.json): three ordinary-Chrome captures, one method freeze, per-renderer counts, independent page scoring, and MemProcFS checks.
- [Chrome method freeze](/research/chatgpt-windows-ram/FROZEN_CHROME_STATE_V1.json), [bounded state parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py), [turn joiner](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py), and [synthetic replay fixture](/research/chatgpt-windows-ram/chrome_state_synthetic_fixture.json).
- [Technical figure provenance](/research/chatgpt-windows-ram/LOW_LEVEL_FULL_RAM_FIGURES_20261027.json): source hashes and transformations for the process table, address map, Edge event diagram, and full-RAM HxD figures, including the split B15 record.
- [Baseline and B5 figure provenance](/research/chatgpt-windows-ram/B1_B5_FIGURE_PROVENANCE_20261030.json): the client-open pretest and B5 direct Volatility figures, plus the full-RAM HxD crops.
- [Screenshot provenance](/research/chatgpt-windows-ram/ACTUAL_SCREENSHOTS.json): source files, hashes and crops for the page, result-viewer and terminal captures.
- [Reproduction guide](/research/chatgpt-windows-ram/REPRODUCE.md): what can and cannot be replayed from the public bundle.
- [Parser](/research/chatgpt-windows-ram/trial_iab_visible_002/parse_stream_items.py) and [v2 joiner](/research/chatgpt-windows-ram/method_v2/reconstruct_turns.py).
- [Final replay check](/research/chatgpt-windows-ram/final_verification/fixture_replay_check.json).

</details>

## References

1. Jihun Joun, [*Forensic analysis from generative AI web application memory: A ChatGPT case study*](https://doi.org/10.1016/j.fsidi.2026.302175), *Forensic Science International: Digital Investigation*, 2026, with the accompanying [V8 heap-forensics tool](https://github.com/jihunjoun/ChatGPT-V8-Heap-Forensics).
2. Geunyeong Choi, Jewan Bang, Sangjin Lee, and Jungheum Park, [*Chracer: Memory analysis of Chromium-based browsers*](https://dfrws.org/presentation/chracer-memory-analysis-of-chromium-based-browsers/), DFRWS APAC, 2023.
3. Chris Kosmas, [*Scrutinizing a Web-Based LLM in Private Browsing Mode: An Analysis of Memory Artifacts and Privacy Implications*](https://www.sans.edu/cyber-research/scrutinizing-web-based-llm-private-browsing-mode-analysis-memory-artifacts-privacy-implications), SANS Technology Institute, 2025.
4. Malithi Wanniarachchi Kankanamge et al., [*Digital Forensic Investigation of the ChatGPT Windows Application*](https://arxiv.org/abs/2505.23938), 2025.
5. The Chromium Project, [*Multi-process Architecture*](https://www.chromium.org/developers/design-documents/multi-process-architecture/), [*Network Service*](https://chromium.googlesource.com/chromium/src/+/main/services/network/README.md), and the [*StorageService* interface](https://chromium.googlesource.com/chromium/src/+/main/components/services/storage/public/mojom/storage_service.mojom).
6. WHATWG, [*Server-sent events: interpreting an event stream*](https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation).

Continue with [Part 2: Browser state changes](/posts/chatgpt-browser-state-changes/).

Research series: **Part 1: Browser reconstruction** · [Part 2: Browser state changes](/posts/chatgpt-browser-state-changes/) · [Part 3: The native Codex CLI](/posts/codex-cli-windows-ram/)
