---
title: "What Survives of a ChatGPT Conversation in Windows RAM? Part 2: Closing Tabs, Reloading, and Signed-In Chats"
published: 2026-11-01
description: "Close, reload, navigation, and Temporary Chat captures show when ChatGPT text remains in RAM without a reconstructable turn."
tags: [DFIR, Memory Forensics, Browser Forensics, Windows, ChatGPT, Volatility]
category: Research
image: /covers/post-chatgpt-windows-ram-memory-layers.png
draft: false
---

A finished answer can still be on screen when I acquire RAM, yet the process maps may no longer contain the record that joins it to the prompt. In [Part 1](/posts/chatgpt-windows-ram-case-study/) I built and tested two browser grammars against complete, bounded records. Here I close and reload tabs, navigate away, and test signed-in Chrome and Edge, including Temporary Chat.

B10–B16 use anonymous Chrome and Edge profiles, with the Research VM restored to the client-stopped snapshot for the controlled starts. B17–B19 use signed-in Edge, B20–B24 use signed-in Chrome, and B25–B28 test Temporary Chat before and after navigation in both browsers. B18 led me to add a separate [SSE event scanner](/research/chatgpt-windows-ram/method_signedin_sse_v1/sse_event_records.py) for complete `data:` response records. I then ran it back over earlier images. I keep that development separate from the frozen [state-object parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py). A physical string hit means the bytes survived somewhere. A joined turn requires the application's own identifiers inside accepted records. The [process mapping and scoring rule](/posts/chatgpt-windows-ram-case-study/#what-would-count-as-a-reconstruction) are in Part 1.

Each linked **ledger** is a JSON audit record for a trial, not a Chrome or Edge database. It holds the capture condition and hash, the processes examined, the parser's result, and any later search using values known from the page. The reload ledger, for example, lets you see the parser's zero-turn result separately from the answer bytes found afterward.

Research series: [1. Reconstructing a browser turn](/posts/chatgpt-windows-ram-case-study/) · **2. Browser state changes** · [3. The native Codex CLI](/posts/codex-cli-windows-ram/)

## Trials B10–B16: leaving the chat and testing the controls

For these anonymous-profile trials, I recorded the page state, verified the tab or draft before capture, and then acquired RAM with WinPmem. The page observations supplied the later exact-text checks.

### Trial B10: close the Edge tab, not the browser

Navigation and tab closure are different events, so I ran one more Edge capture from the restored baseline. I used a new anonymous profile, waited for the test answer to finish, and saved this view before touching the tab:

![The completed anonymous Edge prompt and response before I closed its tab](/research/chatgpt-windows-ram/screenshots/23-edge-before-tab-close.png)

*The page was captured before the tab closed.*

I opened `about:blank` to keep Edge alive, closed the ChatGPT tab, and checked that only the blank tab remained.

I took the recovered URL and text *out* of the parser inputs. Volatility's process list and command lines selected two active Edge renderers. The unchanged [state parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) looks for a bounded `backendConversationId` object containing a `messages` array. Its [joiner](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py) tests the user and assistant IDs inside that object. Both resident renderer maps yielded **zero complete state objects and zero joined turns**.

The B18 investigation later produced a separate [SSE event scanner](/research/chatgpt-windows-ram/method_signedin_sse_v1/sse_event_records.py), which I ran back over this image. It searches resident process pages for `data: {` in UTF-8 and UTF-16LE, follows virtually adjacent pages, and accepts an event only when it reaches the terminating blank line and parses the JSON. Its [joiner](/research/chatgpt-windows-ram/method_signedin_sse_v1/signedin_sse_turns.py) needs linked message IDs, content patches, and completion to assemble an answer. The state parser above expects one conversation object, while the earlier [`stream-item` parser](/research/chatgpt-windows-ram/trial_iab_visible_002/parse_stream_items.py) expects an outer JSON record around event text. B10's active NetworkService yielded zero complete SSE events. A later [full-physical SSE scan](/research/chatgpt-windows-ram/EDGE_CLOSE_PHYSICAL_SSE_20261001.json) found 33 `data: {` prefixes but **no complete framed JSON event**: six failed encoding, 26 failed event structure, and one was truncated or cap-limited. Those prefixes alone are not responses. I also ran the bounded state-object grammar across the hash-verified physical image: **zero signatures**, not merely zero mapped renderer records. That is a check of this serialization, not of erasure.

The known-value check came later. Across the full physical image, I found 47 UTF-8 and 39 UTF-16LE copies of the conversation ID, 11 and 35 of the full prompt, and **one UTF-8 copy of the full answer**. None of the nine active Edge maps held that full answer. I located the one physical hit and strictly parsed its surrounding JSON. The answer was inside `textTail`, a field where my page check had saved text from the rendered chat before closing the tab. The surrounding `url`, `user`, and `assistant` fields matched that check's JSON object too. A parser for `textTail` could read the object, but it would only recover my own observation from RAM. I excluded the hit as Edge conversation evidence. A later exact-offset pass checked all 152 `pslist` entries. None of the 130 with user-space rows mapped that hit. The [bounded context check](/research/chatgpt-windows-ram/EDGE_CLOSE_OBSERVER_COPY_20261001.json) records the offset and structural checks without publishing surrounding RAM. The browser parent still mapped ID and prompt copies, StorageService mapped both, and NetworkService and SearchIndexer mapped the ID. Those values alone do not rebuild the turn. The [close-tab ledger](/research/chatgpt-windows-ram/EDGE_CLOSE_TAB_20261001.json) keeps the counts separate from this later attribution.

The later screenshot-only Edge pair gave me another check. B25's finished Temporary Chat answer had exact hits in physical RAM, but neither `textTail` nor the `"textTail":` field appeared anywhere in the tested UTF-8 or UTF-16LE guest-physical ranges. B26, after navigation, also had zero hits. The [paired ledger](/research/chatgpt-windows-ram/TEMP_CHAT_PAIRED_20261101.json) records the scan. These were signed-in Temporary Chats, so they do not repeat B10's anonymous tab close. They do show that `textTail` was not a usable starting signature in those Edge captures.

### Trial B11: repeat the tab close in Chrome

The closed Edge tab left me with no joined turn and one full-answer copy from my own page probe. I repeated the close in Chrome with a fresh anonymous profile and a wooden-stopwatch question:

![The completed anonymous Chrome prompt and response before I closed its tab](/research/chatgpt-windows-ram/screenshots/24-chrome-before-tab-close.png)

*I captured the page before closing the tab.*

My first attempt to close the Chrome tab failed. I checked that the finished chat was *still open* and excluded that attempt. After the scored close, the target list showed two `about:blank` tabs and no ChatGPT tab.

Volatility selected all four active `chrome.exe --type=renderer` processes from that image. None yielded a complete state object under the **unchanged** Chrome [parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py), so the [joiner](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py) returned zero turns. The same bounded state-object grammar found **zero signatures** in a separate, hash-verified scan of the full physical image. This still tests only that record format.

I ran the same [SSE scanner](/research/chatgpt-windows-ram/method_signedin_sse_v1/sse_event_records.py) over all ten active Chrome process maps. It found zero complete events. The browser parent had one invalid `data:` prefix.

The later known-value diagnostic found the conversation ID in one renderer, the full prompt in StorageService, and the ID in the browser parent and NetworkService. It found no exact full response in the physical image. An answer-only phrase, `magnetic field detector`, did occur seven times in physical RAM, but in none of the ten active Chrome user maps. That phrase was absent from the prompt. The requested ending words were *not* a useful answer marker because I had put them in the prompt too.

I searched backward from the finished answer. The [post-capture residue checker](/research/chatgpt-windows-ram/reverse_known_value_audit.py) takes already known text, searches the complete verified image in UTF-8 and UTF-16LE, and tests each hit against the image-derived process maps. It cannot discover a conversation blindly. The first complete answer sentence had four physical hits and no active Chrome user-map hit. The second sentence and the full answer had none.

A separate provenance check placed two shorter-phrase hits inside my page-observation JSON, two in VMware Tools user space, and left three without a process user mapping. I also tried the later [bounded envelope scanner](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/browser_json_envelopes.py), which looks for complete `action: next`, `message` event, and typed-message JSON without known text. It found zero signatures across all ten active Chrome processes. The [reverse audit](/research/chatgpt-windows-ram/REVERSE_RESIDUE_AUDIT_20261031.json) records these extra checks alongside the [phrase provenance](/research/chatgpt-windows-ram/CHROME_CLOSE_PHRASE_PROVENANCE_20261001.json) and [process-owner check](/research/chatgpt-windows-ram/CHROME_CLOSE_PHYSICAL_OWNER_20261001.json).

The remaining fragments do not recover the closed turn. The renderer's old mapping may have disappeared, its buffers may have been reused, or the answer may survive in pieces or another representation. The capture cannot tell which happened.


### Trials B12 and B13: reload without closing the tab

B12's page check copied the answer text. B13 recorded only screenshot pixels and message counts. Both captures followed a reload of the same tab.

Closing a tab destroys its visible page. I tried a narrower change: keep the same anonymous Chrome tab open and reload a *finished* conversation. Before the reload, the page had its `/uc/…` conversation URL, two DOM message IDs, and the completed wool-thermometer answer. `Page.reload` returned that same tab to the new-chat page. The message elements were gone before acquisition and still absent afterward.

![Actual completed anonymous Chrome turn before reloading the tab](/research/chatgpt-windows-ram/screenshots/39-chrome-reload-before-crop.png)
![The same tab showing a new chat after reload, before RAM acquisition](/research/chatgpt-windows-ram/screenshots/40-chrome-reload-after-crop.png)


Volatility selected all three active Chrome renderers. The unchanged [state parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) found **zero complete objects and zero joined turns**. I then reversed the search: the old `/uc/…` URL gave me a conversation ID, and the pre-reload page record gave me the prompt and answer. The later exact-value diagnostic put the ID, full prompt, and full answer in renderer PID 3640. It found one complete answer copy in UTF-8 and another in UTF-16LE. MemProcFS confirmed representative mapped reads.

The available mapped context, up to 8 KiB on either side of the first UTF-8 prompt and answer hits, contained no `textTail`, `user`, or `assistant` key and no complete saved page-observation string. That weakens one observer-copy explanation for those particular hits. The values were on separate pages, though, and I found no accepted record linking them through message IDs. My page check had also copied the text, so I cannot assign every copy to Chrome's application state. The [reload ledger](/research/chatgpt-windows-ram/CHROME_RELOAD_20261001.json) records the page transition, hashes, blind zero, and later value search. The [reverse-audit summary](/research/chatgpt-windows-ram/REVERSE_RESIDUE_AUDIT_20261031.json) records the bounded context check separately.

That last caveat bothered me. The first page check had returned the answer as text, potentially leaving its own copy in RAM. I repeated the experiment from the baseline with a new clay-barometer question. This time I did not retrieve the answer as text. I saved a screenshot and checked only the URL and message count. The same tab had two message elements before reload and zero on the new-chat page afterward. I did not collect their IDs in this repeat.

![Finished test answer in Chrome before the screen-only reload](/research/chatgpt-windows-ram/screenshots/43-chrome-screenonly-reload-before-crop.png)
![The same Chrome tab at new chat after the screen-only reload](/research/chatgpt-windows-ram/screenshots/44-chrome-screenonly-reload-after-crop.png)


The second image again gave the frozen [state parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) **zero state objects and zero joined turns** across all three image-selected renderers. I sealed that output before transcribing one answer-only sentence from the screenshot. The reverse search started at that sentence, which was absent from both the submitted prompt and the pre-acquisition page record. It found one exact UTF-8 copy in renderer PID 10028. The old conversation ID and one UTF-16LE prompt copy were also mapped by that renderer, but at different physical locations. MemProcFS confirmed representative bytes and translations. A later [flat-physical scan](/research/chatgpt-windows-ram/PHYSICAL_CHROME_STATE_CONTRAST_20261001.json) found zero state signatures.

Because the page check never returned the answer as text, this trial avoids B12's specific text-bearing observation. Sharing a PID still does not give the sentence a message ID or identify its V8 object. The page check recorded message counts, not IDs, so there is no independent five-field turn to score. The [visible-turn control](/posts/chatgpt-windows-ram-case-study/#trial-b5-a-visible-answer-without-a-text-probe) joined a turn with the same quiet observation protocol. The [screen-only repeat ledger](/research/chatgpt-windows-ram/CHROME_RELOAD_SCREEN_ONLY_20261001.json) records the screenshot hashes, blind result, and post-seal sentence search. The [reverse-audit summary](/research/chatgpt-windows-ram/REVERSE_RESIDUE_AUDIT_20261031.json) records the process-level boundary of that reverse search.

### Trial B14: two tabs, one capture

The single-tab close and reload tests needed a control in which another conversation stayed open. I restored the baseline and opened two completed anonymous chats in one Chrome profile. The first asked why a paper compass cannot measure rainfall. The second asked why a glass metronome cannot predict tides. I closed only the first target. Chrome and the second chat stayed open.

![Pixel crop of the first completed Chrome chat before I closed its tab](/research/chatgpt-windows-ram/screenshots/27-chrome-two-tabs-first-crop.png)

![Pixel crop of the second completed Chrome chat in the same browser](/research/chatgpt-windows-ram/screenshots/28-chrome-two-tabs-second-crop.png)


I also recorded both rendered answers and their DOM message IDs **before** the close. Those are the independent scoring values, not parser input. From the hash-verified image, `pslist` and `cmdline` selected three active Chrome renderers and six other Chrome processes. The unchanged [state-object parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) and [joiner](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py) found two copies of one complete object in one renderer, joined exactly **one** turn, and found no complete object in the other eight processes. Only after sealing that output did I compare it to the page records:

![The frozen Chrome parser and joiner run on PID 1356 in the complete B14 memory image. Two mapped occurrences reduce to one state and one joined turn.](/research/chatgpt-windows-ram/screenshots/84-b14-parser-direct.png)


| Chat at acquisition    | Blind state-object result | Later page comparison                                                           |
| ---------------------- | ------------------------- | ------------------------------------------------------------------------------- |
| First tab, closed      | No joined turn            | Its known text was checked separately as residue                                |
| Second tab, still open | One joined turn           | Conversation ID, prompt, answer, user ID and assistant ID matched **5/5** |

I then checked the **whole physical images**, not only active process maps. I applied the same bounded state signature to physically contiguous bytes. The closed-only image had **zero signatures**. The two-tab image had three signatures and two complete copies of one object. Its prompt exactly matched the second, still-open tab, not the closed first tab. This [physical-scan contrast](/research/chatgpt-windows-ram/PHYSICAL_CHROME_STATE_CONTRAST_20261001.json) is a useful positive control, but a flat scan cannot reassemble nonadjacent physical pages or assign an object to a process. It does not prove erasure.

MemProcFS reread both accepted record copies, matching their bytes and translations. Its wider deterministic check matched 261 of 288 sampled pages. The other 27 reads or translations were unavailable, and none of the completed checks disagreed. The separate signed-in SSE grammar yielded zero complete events across all nine Chrome process maps.

I nearly overstated the closed-tab result when the *known-value* pass found six full-answer hits in physical RAM. I reversed from each answer hit to its surrounding bytes. Two mapped to Chrome's browser parent, inside the JSON-escaped `textTail` returned by my page-observation probe. MemProcFS confirmed those mapped bytes. The other four had no active Chrome user-map owner, but the 64 bytes on either side of each answer matched my saved observation JSON exactly. Two matched page observations and two matched the DOM-input inspection that had copied the state value before closure.

I also tried the later [envelope scanner](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/browser_json_envelopes.py) on the nine active Chrome process maps. It scans resident pages for three JSON shapes: a submission beginning with `{"action":"next","messages":`, an event beginning with `{"message":{`, or a typed message beginning with `{"type":"message",`. It follows virtual pages and accepts a record only when the JSON is complete and the fields expected for that shape are present. It receives no prompt, answer, or conversation ID from the page. It found zero complete envelopes here. A user envelope alone would still leave the reply unlinked. In the same image, the frozen state parser reconstructed the open chat **5/5**. The [two-tab ledger](/research/chatgpt-windows-ram/CHROME_TWO_TABS_CLOSE_ONE_20261001.json) records the original capture and score. The [reverse audit](/research/chatgpt-windows-ram/REVERSE_RESIDUE_AUDIT_20261031.json) records the later answer-to-context check. Other encodings and unrecognized record formats remain outside this exact-value test.

### Trial B15: one tab, two turns

Two tabs tested whether I would accidentally join *different* conversations. I also wanted the reverse test: a follow-up in the *same* conversation. After restoring the VM baseline, I sent a wooden-gyroscope question in a fresh anonymous Chrome tab, waited for the answer, and recorded its two DOM message IDs. I then sent a paper-magnet follow-up in that **same tab**. The URL and tab stayed the same. The page now had four message IDs, and the first pair's IDs and text had not changed. I checked them again after acquisition.

![Actual first completed turn before the follow-up](/research/chatgpt-windows-ram/screenshots/33-chrome-multiturn-first-crop.png)
![Actual second completed turn in the same tab before acquisition](/research/chatgpt-windows-ram/screenshots/34-chrome-multiturn-second-crop.png)


From its hash-verified image, `pslist` and `cmdline` selected all three active Chrome renderers. I ran the **unchanged** September 30 [state parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) over each `memmap` before comparing anything to the page records. Only one renderer, PID 6896, contained complete state objects:

| State object in PID 6896 | `messages` | `userMessageCount` | Encoding | RAM copies |
| ------------------------ | -----------: | -------------------: | -------- | ---------: |
| No message pair          |            0 |                    1 | UTF-8    |          2 |
| First completed pair     |            2 |                    1 | UTF-8    |          2 |
| Second completed pair    |            2 |                    2 | UTF-16LE |          2 |

I had expected a four-message array after the follow-up. Chrome had not left me one in these recovered objects. The newer object held only the latest user/assistant pair, while `userMessageCount` had advanced to 2. The older two-message object was still separately mapped, and each completed object's `parentMessageId` matched its assistant ID. That is why the frozen joiner emitted **two** turns without concatenating unrelated strings. The sealed output matched the first and second page turns **5/5 each**, with no cross-joined pair. MemProcFS reread all six record occurrences and agreed on their bytes and virtual-to-physical translations. The [multi-turn ledger](/research/chatgpt-windows-ram/CHROME_MULTITURN_VISIBLE_20261001.json) has the image hashes, per-renderer counts, and score. These records did not supply independent event timestamps. Submission and observation times came from the separate page records.

The accepted parser output gave me the addresses for the next two figures. I followed its `source_spans`, generated from `windows.memmap`, back into the full image and checked the record bytes. The known prompt did not select these pages. One copy of the newer state begins at physical offset `0x9665750c`. Its `7b 00 22 00` opening is `{"` in UTF-16LE. Farther in, `46 00 6f 00 6c 00 6c 00` begins “Following,” the follow-up prompt. The parser's source span and 1,218-byte record hash identify this as the second state in the table.

[![Two HxD crops from the complete B15 RAM image showing the UTF-16LE follow-up state and the start of its prompt](/research/chatgpt-windows-ram/screenshots/73-chrome-multiturn-second-state-full-ram.png)](/research/chatgpt-windows-ram/screenshots/73-chrome-multiturn-second-state-full-ram.png)

*The source was the complete, hash-verified decompressed RAM image. Only cropping, enlargement, byte outlines, and boxed callouts were added.*

One copy of the first completed state crosses a physical page boundary. It starts at `0x7d42e2c` and runs for 468 bytes to the end of that page. The next 136 bytes are adjacent in PID 6896's *virtual* map, but their physical page starts at `0x173243000`. The four bytes before the opening brace are `5c 02 00 00`, or 604 in little-endian. I concatenated the two parser-reported source spans and got the parser's 604-byte record SHA-256, `cf81b8f3186c6374c30e9feffc4d98e1254345c87563cbe94f42a8bcd889c36f`. Reading 604 bytes straight from `0x7d42e2c` in the raw image instead runs into zero padding at `0x7d43000` and gives a different hash. The other copy of this state is physically contiguous.

[![Three cropped HxD views of the complete B15 RAM image showing a UTF-8 state record split across two distant physical pages](/research/chatgpt-windows-ram/screenshots/69-chrome-multiturn-page-boundary-full-ram.png)](/research/chatgpt-windows-ram/screenshots/69-chrome-multiturn-page-boundary-full-ram.png)

*The first two crops show the record's start and the end of its first physical page. The last crop begins at the next mapped physical page. The same record is continuous in the renderer's virtual address space.*

### Trial B16: text in the composer is not a conversation

I wanted a control for the easiest mistake in this investigation: finding the prompt in memory and assuming the user sent it. In a fresh anonymous Chrome profile, I entered a glass-umbrella question into the composer and stopped. The Send button was enabled, but I did not submit the draft. The page stayed at the new-chat URL, with no submitted-message elements. The same draft and empty message list were still there after WinPmem finished.

![Chrome page with an unsent test draft still in the composer](/research/chatgpt-windows-ram/screenshots/36-chrome-unsent-draft-crop.png)


I hash-verified the transferred gzip image, selected all three active Chrome renderers from Volatility's `pslist` and `cmdline`, and ran the same frozen [state parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) before supplying it with the draft text. It found zero state signatures and zero joined turns. A later full-physical scan also found zero state signatures. In a separate, post-hoc byte check, the exact draft appeared 17 times in UTF-8 and 37 times in UTF-16LE in physical RAM. One renderer mapped 3 and 9 respectively. MemProcFS independently reread the first mapped hit of each encoding. Some copies may have come from my saved page observations, so the hit counts are not a persistence rate or proof of submission. The prompt's bytes were present, but I found no accepted user/assistant state. The [unsent-draft ledger](/research/chatgpt-windows-ram/CHROME_DRAFT_NOSUBMIT_20261001.json) records the control and its hashes.

## Trials B17–B19: signed-in Edge and the NetworkService answer

I kept three acquisitions separate: B17 for the response that failed to render, B18 for the finished teapot turn in saved VMware memory, and B19 for the direct WinPmem image of that same visible turn a few minutes later.

### Trial B17: a response that did not render

I also tried the ordinary signed-in Edge page. The first attempt was awkward: my prompt appeared, an assistant toolbar appeared below it, but there was no answer text and Copy failed. I saved that memory state so I would not later count it as a completed turn. Its three active Edge renderers had no signatures for either earlier browser grammar, although the exact prompt was present in one map. A later check with the [SSE scanner](/research/chatgpt-windows-ram/method_signedin_sse_v1/sse_event_records.py) found no complete event in that image's NetworkService either. That [failed-response capture](/research/chatgpt-windows-ram/EDGE_SIGNEDIN_UI_EMPTY_20261001.json) is a separate result, not a negative result for a finished answer.

### Trials B18 and B19: one visible answer, two images

After restarting Edge, I sent a new, deliberately harmless teapot question. This time the answer finished. I saved memory, captured the actual page, and then acquired a direct WinPmem image while the same answer remained visible:

![Signed-in Edge page showing the teapot test prompt and finished response](/research/chatgpt-windows-ram/screenshots/22-signedin-edge-teapot-visible.png)


The direct acquisition ran elevated **inside the guest** with WinPmem's gzip output:

```powershell
.\go-winpmem_amd64_1.0-rc2_signed.exe acquire --compression=gzip ..\outbox\signedin_edge_teapot_visible_001\memory.raw.gz
```

I verified the transferred archive against its guest-side hash and read the gzip stream to EOF, then temporarily materialized a sparse raw copy for Volatility. The older `stream-item` and Chrome-state grammars returned zero signatures across all five active renderers in the saved memory. A bounded request scan gave me a lead: one renderer held five copies of `{"action":"next","messages":...}` with the exact prompt and the conversation ID from the page URL, but no complete answer. The answer was also present as a UTF-16LE V8 string. The bytes survived, but I still needed a record that connected them.

The missing structure was in Edge's **NetworkService**, not its renderer. I selected the live `msedge.exe` utility by its exact `--utility-sub-type=network.mojom.NetworkService` command-line argument, not by its PID or age. Volatility supplied that process's resident page map. A [VMware-aware MemProcFS wrapper](/research/chatgpt-windows-ram/method_signedin_sse_v1/scan_vmware_sse.py) handled the saved `.vmem`, with the complete command in its [README](/research/chatgpt-windows-ram/method_signedin_sse_v1/README.md). For the later flat WinPmem image, I ran the linked [SSE scanner](/research/chatgpt-windows-ram/method_signedin_sse_v1/sse_event_records.py) and [turn joiner](/research/chatgpt-windows-ram/method_signedin_sse_v1/signedin_sse_turns.py) from a directory containing the downloaded method folder. PID 2936 is the NetworkService identified by `windows.cmdline` in that image:

```bash
VOL="$HOME/volatility3/vol.py"
IMAGE=private/memory.raw
OUT=private/analysis
mkdir -p "$OUT"

python3 "$VOL" -f "$IMAGE" windows.pslist | grep 'msedge.exe'
python3 "$VOL" -f "$IMAGE" windows.cmdline | grep -- 'network.mojom.NetworkService'
PID=2936
python3 "$VOL" -r json -f "$IMAGE" windows.memmap --pid "$PID" > "$OUT/network-memmap.json"
python3 method_signedin_sse_v1/sse_event_records.py --image "$IMAGE" --memmap "$OUT/network-memmap.json" --output "$OUT/network-sse.json"
python3 method_signedin_sse_v1/signedin_sse_turns.py --parsed "$OUT/network-sse.json" --output "$OUT/network-turn.json"
```

The SSE scanner accepts a `data:` event only when its JSON and terminating blank line are complete. To put events in one sequence, it reads the *actual bytes* between them and accepts only SSE control lines, not a guessed time order from nearby addresses. In the saved memory, NetworkService yielded 15 events in one verified 6,161-byte stream. The `input_message` carried conversation ID `C`, user ID `U`, and the full prompt. A system message named `U` as its parent, and the assistant start named that system message as *its* parent. Message markers then named the same assistant ID `A` and conversation `C`. Four content patches appended 15, 57, 47, and 36 characters to `/message/content/parts/0`. The last batch marked the assistant finished, and a `message_stream_complete` event closed `C`. The assembled 155-character answer matched the page exactly.

[![The ID and content relationships accepted from B18's Edge NetworkService response stream](/research/chatgpt-windows-ram/screenshots/70-edge-sse-join-evidence.png)](/research/chatgpt-windows-ram/screenshots/70-edge-sse-join-evidence.png)

*Drawn from B18's 15 parsed events. `U` is the user ID, `S` the system ID, `A` the assistant ID, and `C` the conversation ID. The last patch batch marks the answer finished before `message_stream_complete` closes `C`.*

I wrote the SSE joiner while studying this saved image, so the result belongs to development rather than a fresh-prompt validation. I hashed the RAM-derived output before running the separate screen comparison: conversation ID, exact prompt, and exact rendered answer matched 3/3. The RAM records link the user and assistant IDs internally, but I had not captured those two IDs independently from the live DOM. The [frozen method and synthetic rejection tests](/research/chatgpt-windows-ram/method_signedin_sse_v1/README.md) show what the joiner requires before it will emit a turn.

I also tried this grammar retrospectively on both Chrome NetworkService processes from the earlier two-profile image. Neither held a complete SSE event, although the renderer state objects had joined two turns. The Edge stream was another surviving format, not a replacement for the Chrome state-object evidence.

Then I applied that unchanged method to the direct WinPmem image of the *same* visible turn, acquired several minutes later. This time the image-selected NetworkService had **zero complete SSE events**. I extended the same scan to all 11 active Edge processes in `pslist`. Only renderer 5844 held complete events, six from an older exchange and not enough to join this turn. The browser parent had one incomplete `data:` signature. The other nine processes had no complete events. No individual process map yielded a candidate. A separate *post-hoc* check, deliberately supplied with the screen's text, still found the full prompt (eight UTF-8 and one UTF-16LE mapped copies) and the full answer (three UTF-16LE copies) in renderer 5844. MemProcFS agreed with Volatility on 32 sampled pages there and 32 in NetworkService. So the later zero is about the **joined stream**, not an assertion that the answer had vanished from RAM.

A flat physical-byte pass found five complete SSE events, one fewer than the renderer scan. The missing event crossed two pages that were adjacent in the renderer's virtual address space but distant in physical RAM. That is a concrete reason to use `windows.memmap` instead of treating the raw image as one continuous process dump.

I also compared the **15 saved NetworkService events at their exact virtual addresses** against the later direct image. It was still PID 2936 with the same process-creation metadata. All 15 address ranges were resident later, but none still hashed to its earlier event bytes. Nine even had unchanged physical spans. MemProcFS independently matched all 15 later reads and translations. So this later zero is not just a missing-map artifact: the bytes at those locations changed. It does not tell me whether a buffer was reused, overwritten, or whether another copy survived elsewhere. The [trial ledger](/research/chatgpt-windows-ram/EDGE_SIGNEDIN_VISIBLE_20261001.json) records this post-hoc comparison separately from the blind SSE scan.

The [signed-in trial ledger](/research/chatgpt-windows-ram/EDGE_SIGNEDIN_VISIBLE_20261001.json) contains both acquisition times, hashes, and the two different parser outcomes. The full signed-in records and memory images stay private.

## Trials B20–B24: signed-in Chrome without an accepted join

B20 is the pre-submit control, B21 the finished paper-lighthouse turn, and B22 its much later blank-tab follow-up. B23 is the short paper-anchor pair with the tab left open. B24 is the cardboard-rudder pair captured before and after navigation. Each pair tests one condition at two acquisition times.

### Trial B20: signed-in, before a new prompt

I opened the VM's existing Chrome profile on a signed-in ChatGPT new-chat page and acquired RAM **before submitting a new test prompt**. Edge was also open, so I selected Chrome processes from the image's `pslist` and `cmdline` rather than treating the whole image as Chrome evidence. The unchanged state-object and `stream-item` grammars found zero signatures across five active Chrome renderers. The SSE grammar found no complete event in Chrome's NetworkService. A separate full-physical state-object scan also found zero signatures. MemProcFS matched Volatility's bytes and physical translations on all 192 sampled pages across those six processes. This [control](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_NOSUBMIT_20261014.json) says what the tested grammars did *before a new turn*. It does not make this previously used account a clean no-history machine.

After the visible-turn capture below, I also ran the [signed-in envelope scanner](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/browser_json_envelopes.py) on the stored control image. It looks for bounded JSON beginning with a submission request, a `message` event, or a typed message. It tests UTF-8 and UTF-16LE in mapped user pages and validates the complete JSON before accepting it. Unlike the state parser, it does not require a `backendConversationId` object containing both messages. The control had zero complete envelopes across its five active renderers. This is a retrospective format comparison, not another capture.

### Trial B21: a finished answer in signed-in Chrome

The next capture used that same running Chrome profile, now with a new *paper lighthouse* question and its answer finished on screen.

![Signed-in Chrome showing the paper-lighthouse prompt and finished answer](/research/chatgpt-windows-ram/screenshots/47-signedin-chrome-visible-crop.png)

I ran the existing [state parser](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py) and [envelope scanner](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/browser_json_envelopes.py) without giving them the visible answer or URL. Volatility 3 read the verified raw image. I used `pslist` and `cmdline` to select the **four active Chrome renderers** by `--type=renderer`. The scan below uses those four PIDs from this image.

<details>
<summary>Process selection and mapped-record scan</summary>

```bash
python3 "$VOL" -f "$IMAGE" windows.pslist | grep 'chrome.exe'
python3 "$VOL" -f "$IMAGE" windows.cmdline | grep -- '--type=renderer'
PIDS=(5580 5904 6520 8204)
for pid in "${PIDS[@]}"
do
  python3 "$VOL" -r json -f "$IMAGE" windows.memmap --pid "$pid" > "$OUT/memmap-$pid.json"
  python3 scripts/ram-research/chrome_state_records.py --image "$IMAGE" --memmap "$OUT/memmap-$pid.json" --output "$OUT/state-$pid.json"
  python3 scripts/ram-research/browser_json_envelopes.py --image "$IMAGE" --memmap "$OUT/memmap-$pid.json" --output "$OUT/envelopes-$pid.json"
done
```

</details>

The frozen Chrome state-object parser again found **zero complete states and zero joined turns**. The separate signed-in envelope scan found something narrower in renderer 8204: one complete 740-byte `message-event` whose `author.role` is `user`. Its conversation ID matches the URL, and its content is the exact prompt. It also supplies a user-message ID, but no assistant reply. I reran that renderer's `memmap` and envelope scan. The record digest and source virtual address matched the first run. Neither the older `stream-item` grammar nor the SSE scanner accepted a complete response event in the four renderers or Chrome's NetworkService. A hash-verified full-physical SSE scan had 129 `data:` prefixes, but **zero complete framed events**.

Only after those parsers had run and the state/envelope outputs were hashed did I use the answer transcribed from the screenshot as an exact-byte diagnostic. The full response occurred 62 times in UTF-8 in the flat image. Of the mapped occurrences, 50 were in renderer 5580 and 11 in renderer 8204. At one first hit in each renderer, the 142-byte answer was immediately preceded by `8e 01` (a 142-byte varint) and `8e 00 00 00` (little-endian 142), respectively. Those are plausible length fields around text, **not** assistant-message records or a link to the user envelope. The mapped counts can also include aliases. MemProcFS independently matched seven first-hit bytes and translations. Of 160 deterministic page samples across the four renderers and NetworkService, 157 matched Volatility. Three raised read/translation errors, and none of the completed samples disagreed. The [visible-turn ledger](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_VISIBLE_20261015.json) keeps the blind result separate from this post-hoc check. The answer survived in mapped RAM, but I cannot promote it to a linked `C/P/R/U/A` turn on the strength of these records.

### Trial B22: a late blank-tab follow-up

My first `about:blank` follow-up came **nine hours and 25 minutes** after that visible image. The old answer still had seven exact UTF-8 hits in physical RAM, but the active renderers yielded no accepted turn. The prompt-bearing renderer PID 8204 exited during the 52.8-second acquisition. I checked its remaining process map too, rather than treating the active list as the end of the search. The old prompt and full answer were reachable there, and both were also present in the browser-parent map. The state, `stream-item`, envelope, and SSE grammars still found no complete linked record in the exited map or the other Chrome maps. The [late-follow-up ledger](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_AWAY_20261015.json) records the image times, process exit, expanded blind scan, and later known-value counts separately. That nine-hour delay cannot isolate navigation from everything else the machine did in between.

### Trial B23: the tab stays open

To narrow the time gap, I left a completed *paper anchor* answer on screen and took two RAM images with a 29-second gap between acquisitions. The browser parent and all four active renderer PIDs stayed the same. The [bounded envelope scanner](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/browser_json_envelopes.py) found the same finished user envelope twice in each image. The first image also held an `in_progress` assistant envelope with only the beginning of its answer. That envelope was gone in the second image, without any navigation. A separate, post-parser check still found the full answer in UTF-16LE in the same two renderer maps, with 72 row-contained occurrences in each image. That answer contains the curly apostrophe in `water’s`, while the later all-ASCII rudder answer appeared as full UTF-8 copies instead. Losing a parseable fragment is not the same thing as losing the answer's bytes, and checking just one encoding would have missed one of these answers. The [paired-capture ledger](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_PAIRED_20261015.json) records both no-navigation image hashes, the envelope changes, and the later exact-byte counts.

### Trial B24: one tab before and after navigation

For the navigation test I used a fresh *cardboard rudder* conversation in that same Chrome tab.

![The finished cardboard-rudder turn and its conversation URL, cropped from the VM screen before acquisition](/research/chatgpt-windows-ram/screenshots/49-signedin-chrome-paired-visible-crop.png)

![The same Chrome tab on about:blank before the paired acquisition](/research/chatgpt-windows-ram/screenshots/50-signedin-chrome-paired-blank-crop.png)

The Chrome browser parent remained PID 7832. Before navigation, all six accepted `message-event` envelopes were in renderer 5548 and carried the new conversation ID, but none contained a complete prompt–answer turn: four were system events, one assistant event carried `model_editable_context` rather than answer text, and another contained only an `in_progress` `A`. After navigation, PID 5548 was absent from both the active process list and the pool scan. New renderer PIDs 2656 and 7792 had started between acquisitions. The unchanged [state-object](/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_records.py), [`stream-item`](/research/chatgpt-windows-ram/trial_iab_visible_002/parse_stream_items.py), and [envelope](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/browser_json_envelopes.py) scans accepted **zero** records in the four active renderers after navigation. Chrome's NetworkService supplied no complete SSE event in either image.

Only after sealing those parser outputs did I reverse from the answer copied from the screenshot. Its complete UTF-8 text had 86 exact hits in physical RAM before navigation and **two** afterward. I checked the active renderer maps and browser-parent map against those hits. Neither still mapped the full answer. The old record-bearing renderer was absent from both `pslist` and `psscan`, so there was no trustworthy old user map to follow back from the two physical copies. They remain unassigned, not erased. The mapped count before navigation was 89 row-contained hits, which can exceed the 86 physical hits because virtual mappings can alias the same bytes. The [paired-trial ledger](/research/chatgpt-windows-ram/SIGNEDIN_CHROME_PAIRED_20261015.json) records both page states and image hashes, process turnover, blind envelopes, and the later exact-byte check. In this run, navigating away coincided with losing the accepted active-renderer envelopes. It did **not** demonstrate erasure of the answer from RAM.

## Trials B25–B28: Temporary Chat before and after navigation

[Temporary Chat stays out of ChatGPT history unless it is saved](https://help.openai.com/en/articles/8914046-temporary-chat-in-chatgpt). That made it a useful test here. I wanted to know what a memory image could say about a finished turn while the temporary tab was open, then after I replaced that same tab with `about:blank`. I did not save either chat.

I restored the same signed-in VM snapshot for each browser pair. A separate regular ChatGPT tab stayed open. In the temporary tab I submitted a new, distinctive prompt, waited for the answer, and saved the first memory state. I then navigated **that tab** to `about:blank`, and saved a second state. These are four VMware saved-memory images, one for each page state.

I first used Volatility's `windows.pslist` and `windows.cmdline` to select every active browser renderer by `--type=renderer`, then `windows.memmap` to get its resident virtual pages. The [VMware reader](/research/chatgpt-windows-ram/method_vmware_snapshot_v1/scan_vmware_snapshot.py) used MemProcFS for guest-physical reads and tested the existing state-object and `stream-item` grammars. The [bounded envelope scanner](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/scan_vmware_envelopes.py) used those same maps but accepted a different shape: a complete JSON object with a `message`, an author role, and a `conversation_id`. I also checked each browser's NetworkService with the [SSE scanner](/research/chatgpt-windows-ram/method_signedin_sse_v1/scan_vmware_sse.py). None of these scans received a prompt, URL ID, answer, or target offset.

<details>
<summary>Commands used to reach and scan one renderer</summary>

set `VOL`, `SNAP`, `PID`, `MAP`, and `OUT` to your local Volatility script, VMware memory image, image-selected renderer PID, private map file, and private dump directory. Repeat the map command for every renderer selected from that image.

```bash
python3 "$VOL" -f "$SNAP" windows.pslist
python3 "$VOL" -f "$SNAP" windows.cmdline
python3 "$VOL" -r json -f "$SNAP" windows.memmap --pid "$PID" > "$MAP"
python3 "$VOL" -f "$SNAP" -o "$OUT" windows.memmap --pid "$PID" --dump
```

On Windows, set `ENVELOPE_SCANNER` to the linked [VMware envelope scanner](/research/chatgpt-windows-ram/method_signedin_envelopes_v1/scan_vmware_envelopes.py). Set `SDK`, `SNAP`, `MAP`, `PID`, and `ENVELOPES` to the MemProcFS directory and the corresponding private files. The scanner writes full records, so its output stays outside the blog. Change the process name to `chrome.exe` for Chrome.

```powershell
python "$ENVELOPE_SCANNER" --sdk-root "$SDK" --vmem "$SNAP" --memmap "$MAP" --pid "$PID" --process-name msedge.exe --output "$ENVELOPES"
```

Only after saving the structural results, I put the known strings in a private JSON file such as `{"prompt":"…","answer_sentence":"…"}`. The linked [exact-byte counter](/research/chatgpt-windows-ram/method_vmware_snapshot_v1/count_known_physical.py) then counted those values in the VMware guest-physical ranges. Set `PHYSICAL_COUNTER` to that script, `KNOWN` to the private JSON file, and `COUNTS` to a new private output file.

```powershell
python "$PHYSICAL_COUNTER" --sdk-root "$SDK" --vmem "$SNAP" --known-json "$KNOWN" --output "$COUNTS"
```

</details>

### Trial B25: a finished Temporary Chat in Edge

The Edge page showed the *cardboard sextant* prompt and a finished answer titled “The Paper Navigator’s Problem.” Its address ended in `?temporary-chat=true` and contained conversation ID `6ae667fe-bc94-83e9-a872-a2a0c919db0d`. The “Save chat” control was visible. Here is the guest screen with the account sidebar redacted:

![Edge Temporary Chat with the cardboard sextant prompt and answer](/research/chatgpt-windows-ram/screenshots/temp-chat-edge-visible.png)

Three complete `message-event` objects survived in Edge renderer PID 6288. Two had a system author. The third had `author.role` set to `user`, the full prompt in `content.parts`, a user-message ID, and the same conversation ID as the URL. The scanner framed and validated the complete 735-byte JSON object before reading any of those fields. It found no assistant message object that could connect the displayed answer to this user record. The other two active Edge renderers yielded no complete envelope, and NetworkService yielded no complete SSE event.

I followed the accepted user record back to the dump of PID 6288. It began at virtual address `0x19c0010052c`, mapped to guest physical `0x6712252c`. Volatility placed those bytes at offset `0x7a8152c` in the reassembled **process dump**. The figure is a crop of that dump in 010 Editor. The `data:` prefix is just outside the accepted JSON object. The highlighted `role`, `parts`, and `conversation_id` fields are inside it.

![Actual Edge renderer dump showing the bounded user message, prompt, and conversation ID](/research/chatgpt-windows-ram/screenshots/temp-chat-edge-user-envelope-bytes.png)

### Trial B26: the Edge tab on `about:blank`

After I navigated that same tab, PID 6288 and the other earlier data-bearing renderer were absent from the active process list. The two active Edge renderers yielded **zero complete envelopes**. The state-object and `stream-item` scans also found none, and NetworkService still had no complete SSE event. [The blank-tab screen](/research/chatgpt-windows-ram/screenshots/temp-chat-edge-about-blank.png) records the page state before this capture.

I then supplied the strings from the screen to a separate [guest-physical exact-byte scan](/research/chatgpt-windows-ram/method_vmware_snapshot_v1/count_known_physical.py). The conversation ID and full prompt still had exact hits in both UTF-8 and UTF-16LE. The answer title had one UTF-16LE hit. The exact first answer sentence had **zero** hits in either encoding. Three answer-only fragments, including `precision, rigidity, and durability`, also had zero hits. This follow-up did not recover a linked turn or those tested answer spans. It cannot establish that every shorter fragment or other representation was erased.

### Trial B27: a finished Temporary Chat in Chrome

From the restored starting snapshot I ran the Chrome pair with a different prompt, this time about a *waxen tide gauge*. I chose **Unpersonalized** before sending it. Chrome showed “The Melting Measure” and a one-sentence answer in a Temporary Chat URL ending in `?temporary-chat=true`:

![Chrome Temporary Chat with the waxen tide gauge prompt and finished answer](/research/chatgpt-windows-ram/screenshots/temp-chat-chrome-visible.png)

Renderer PID 10448 held six complete `message-event` objects. One was a user object containing the full prompt and the URL's conversation ID `6ae66eef-ec3c-83ea-8a35-99908c2fbd6b`; five were system objects. There was no accepted assistant object, state object, or `stream-item` in the active renderers, and Chrome's NetworkService had no complete SSE event. The blind method therefore recovered the submission side of this turn, not its displayed answer.

### Trial B28: the Chrome tab on `about:blank`

PID 10448 was absent from Chrome's active process list after navigation. All six active renderer maps now gave **zero complete envelopes**. [The blank-tab screen](/research/chatgpt-windows-ram/screenshots/temp-chat-chrome-about-blank.png) records the page state. The later exact-byte check found the prompt and conversation ID in guest physical RAM, along with **44 UTF-8 occurrences of the full answer sentence**. One renderer, PID 6348, had remained active across the pair. Its user-space map held 43 answer-sentence occurrences but no exact prompt or conversation ID in the tested encodings. Mapped counts can repeat a physical page through aliases, so I do not add them to the 44 physical occurrences.

I dumped PID 6348 and opened the **complete process dump**, not a text-only extraction. At dump offset `0x3a7130`, the answer begins in UTF-8. Volatility's map places that byte at virtual address `0x21301044130` and guest physical address `0x21889130`. The title and sentence sit on the same mapped page. Their proximity explains why a short string search would look convincing, but neither supplies an assistant ID or reconnects the answer to the user envelope that had been in PID 10448.

![Actual Chrome renderer dump after navigation showing nearby title and answer bytes](/research/chatgpt-windows-ram/screenshots/temp-chat-chrome-away-process-bytes.png)

The [paired Temporary Chat ledger](/research/chatgpt-windows-ram/TEMP_CHAT_PAIRED_20261101.json) records the four memory and screen hashes, process selections, accepted-record counts, and later exact-byte counts. The two text columns count **guest-physical occurrences**, not independent objects. Each answer cell uses the exact sentence quoted from the visible response, searched in UTF-8 and UTF-16LE.

| Trial and page state | Complete user envelopes | Full prompt, UTF-8 / UTF-16LE | Answer sentence, UTF-8 / UTF-16LE |
| --- | ---: | ---: | ---: |
| B25 Edge, visible | 1 | 49 / 88 | 75 / 4 |
| B26 Edge, blank | 0 | 12 / 71 | 0 / 0 |
| B27 Chrome, visible | 1 | 42 / 33 | 82 / 0 |
| B28 Chrome, blank | 0 | 15 / 19 | 44 / 0 |

## Conclusion: what changed when the page changed

The two-tab capture gave the clearest comparison. In one Chrome image, the frozen parser reconstructed the chat I left open with all five fields matching the page. It did not reconstruct the chat I had closed. The six exact full-answer hits from that closed chat carried my observation-record context. In the separate Chrome close trial, I found no exact full answer in either tested encoding, though shorter fragments remained outside the active Chrome maps. Both reloads left answer text in a renderer without the state object that would connect it to the prompt. In the Edge close image, the only complete answer hit in physical RAM came from my own page-observation JSON.

The signed-in captures showed another problem with treating text retention as turn retention. One saved Edge image held a complete NetworkService response stream with an internally linked prompt and answer. A direct capture of the same visible turn minutes later did not. Signed-in Chrome kept a user envelope and many exact answer copies without an accepted record joining them. Even with the tab left open, an assistant fragment present in one capture disappeared from the next. The [trial ledgers](/posts/chatgpt-windows-ram-case-study/#evidence-and-audit-files-for-the-series) keep each parser result and later byte check apart.

The Temporary Chat pairs made the difference visible again. Both open tabs yielded a bounded user record with a prompt and conversation ID, yet no accepted assistant record. After each tab went blank, that user record disappeared from the active renderer maps. Chrome still had its answer sentence in an active renderer. Edge kept prompt and ID bytes, but not the exact answer spans I tested. The [paired ledger](/research/chatgpt-windows-ram/TEMP_CHAT_PAIRED_20261101.json) keeps the four image hashes and the later text searches with their narrower scope.

[Joun's heap-snapshot study](https://www.sciencedirect.com/science/article/pii/S2666281726001320) recovered conversation objects deleted through the UI while the browser process remained active. [Ma et al.](https://www.sciencedirect.com/science/article/pii/S2666281726001356) found conversation content in physical memory after a tab closed. The question I tested here was whether surviving records still linked one prompt and answer. In the navigated Edge image, individual values remained in physical RAM, but the tested method could not join them into a turn.

## Evidence and references

The [series evidence index](/posts/chatgpt-windows-ram-case-study/#evidence-and-audit-files-for-the-series) links the image hashes, process selections, parser outputs, and independent checks. The [trial manifest](/research/chatgpt-windows-ram/TRIAL_MANIFEST.json) covers the early pilot and CLI images. Each B-series section above links its own result ledger.

1. Jihun Joun, [*Forensic analysis from generative AI web application memory: A ChatGPT case study*](https://doi.org/10.1016/j.fsidi.2026.302175), *Forensic Science International: Digital Investigation*, 2026.
2. Ma et al., [*A forensic artifact survey of conversational AI services and AI agent browsers across multiple platforms*](https://doi.org/10.1016/j.fsidi.2026.302178), *Forensic Science International: Digital Investigation*, 2026.
3. The Chromium Project, [*Network Service*](https://chromium.googlesource.com/chromium/src/+/main/services/network/README.md).
4. WHATWG, [*Server-sent events: interpreting an event stream*](https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation).
5. OpenAI, [*Temporary chat in ChatGPT*](https://help.openai.com/en/articles/8914046-temporary-chat-in-chatgpt).

Continue with [Part 3: The native Codex CLI](/posts/codex-cli-windows-ram/).

Research series: [Part 1: Browser reconstruction](/posts/chatgpt-windows-ram-case-study/) · **Part 2: Browser state changes** · [Part 3: The native Codex CLI](/posts/codex-cli-windows-ram/)
