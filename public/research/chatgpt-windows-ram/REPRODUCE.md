# Reproducing the shareable full-RAM study results

## Client-stopped reset point

The [reset snapshot ledger](RESET_SNAPSHOT_CONTROL_20261001.json) is a separate
read of a powered-on VMware saved-memory file. Volatility's VMware layer
recognized Windows and found no active target client in `windows.pslist`;
`windows.psscan` still found exited target-process entries. This is evidence
for a repeatable client-stopped starting state, not a no-visit or physically
zeroed control. Its private `.vmem` is not published and is not interchangeable
with the later WinPmem images.

## October 1 Edge extension

The [Edge follow-up ledger](EDGE_FOLLOWUP_20261001.json) covers three
snapshot-reset anonymous visible-response captures and one navigated-away
capture. The unchanged [Chrome state-object method](FROZEN_CHROME_STATE_V1.json)
was applied to every image-selected active `msedge.exe --type=renderer` PID.
The three visible turns yielded one 5/5 candidate each; the navigation image
yielded none. Their full WinPmem images are retained as verified private gzip
archives, not distributed. The [actual Unicode-turn screenshot](screenshots/21-edge-unicode-visible.png)
is a post-capture live-page view. Only the parser/joiner logic and synthetic
fixtures are publicly replayable; the original raw-to-record extraction cannot
be independently repeated from this public bundle alone.

A later [signed-in UI control](EDGE_SIGNEDIN_UI_EMPTY_20261001.json) was
captured as a VMware running-state snapshot after a synthetic prompt appeared
but no answer rendered. Its prompt-presence check is post-hoc and separate
from the structural parser result; it is not a fourth completed-response case.

The [post-navigation residue ledger](EDGE_POST_NAV_RESIDUE_20261001.json) asks
a different, ground-truth-assisted question of that same image. The repository
scripts `count_known_raw_gzip.py`, `attribute_known_browser_hits.py`, and
`crosscheck_known_hits_memprocfs.py` take the private archive, acquisition
record, page observation, DOM-ID observation, and Volatility process maps as
inputs. They report exact bytes across the physical image and selected mapped
processes; none of them is a blind conversation parser. The private source
observations and full image are intentionally not in this bundle.
The [Chrome navigation ledger](CHROME_POST_NAV_RESIDUE_20261001.json) uses the
same diagnostic against the separate lighthouse profile's nine active Chrome
processes and the verified September 30 image. Neither ledger is a second
blind parser result.

The separate [Edge](EDGE_CLOSE_TAB_20261001.json) and
[Chrome](CHROME_CLOSE_TAB_20261001.json) close-tab ledgers each start from a
restored baseline and a completed synthetic anonymous turn. The Chrome trial's
first close attempt did not close its target; a second observation and
corrected target enumeration preceded the scored close. Its private raw image
was rehashed before removal and is reproducible from the retained archive.
The separate frozen SSE scanner then checked all ten Chrome process maps; its
NetworkService zero-event result was identical through the raw and
hash-verified indexed-gzip adapters. Neither that grammar nor the frozen
Chrome state-object grammar recovered a post-close turn.
Neither archive is public, so the original extraction cannot be independently
replayed from this bundle alone.

The later [flat-physical Edge SSE check](EDGE_CLOSE_PHYSICAL_SSE_20261001.json)
reverified the close-tab archive and ran the unchanged bounded event grammar
over one physical identity row. It found 33 `data: {` prefixes but zero
complete JSON events. Its unfiltered output remains private. It is a separate
exploratory scan, not a revised frozen process-map score.

To attribute the one exact full-answer physical hit, the repository's
`locate_known_physical.py` takes the private verified archive and the synthetic
answer read from the actual pre-close screenshot as a **post-hoc** value. It
locates both UTF-8 and UTF-16LE byte forms, rechecks the complete decompressed
hash, then parses only bounded context around each hit. The
[observer-copy ledger](EDGE_CLOSE_OBSERVER_COPY_20261001.json) reports that the
sole hit is inside a strict JSON `textTail` string in the probe's
`url`/`user`/`assistant`/`textTail` object. No adjacent RAM text is published.
This is a source check for a known byte hit, not a blind message recovery. The
same indexed-gzip `physmatches` method described below, given physical offset
`4752298820` from this Edge image, found no user-space mapping among 152
`pslist` entries; the physical probe JSON copy is still present.
The same locator applied to the [Chrome close-tab phrase](CHROME_CLOSE_PHRASE_PROVENANCE_20261001.json)
found seven physical copies: two are parsed probe `textTail` copies, and five
could not be attributed by that bounded check. The subsequent [exact-offset
mapping check](CHROME_CLOSE_PHYSICAL_OWNER_20261001.json) put two of those five
in a user page mapped by `vmtoolsd.exe`; the other three had no user mapping
among the 151 image-derived `pslist` entries. That diagnostic uses the physical
offsets as inputs, so it is not blind reconstruction. It did not expand the
private gzip on disk: `vol_indexed_gzip.py` supplied indexed random reads to
Volatility 3, and the local `physmatches` plugin emitted only rows whose
user-space map covered an input offset. A separate standard `windows.memmap
--pid 3372` pass confirmed both translations; `windows.vadinfo --pid 3372
--address 140719567402473` identified the `vix.dll` VAD. A missing probe-shaped
context or missing active mapping is not evidence of Chrome ownership or erasure.

For a private copy of this verified archive, the exact-offset step is:

```powershell
$vol = 'D:\Cyber Security\tools\DFIR\volatility3-2.8.0\volatility3-2.8.0\vol.py'
$archive = 'D:\Research-Private\chrome-anonymous-cdp-close-004.raw.gz'
$index = 'D:\Research-Private\chrome-close-004.gzidx'
$pluginDir = (Resolve-Path .\scripts\ram-research\vol_plugins).Path
py .\scripts\ram-research\vol_indexed_gzip.py --image $archive --index $index --vol $vol `
  --sha256 86CA335B3D18199888EE5354A451939B9CADD60FC83095BB58C465E4739B9CD5 --build-only
py .\scripts\ram-research\vol_indexed_gzip.py --image $archive --index $index --vol $vol -- `
  -q --offline -r json -p $pluginDir physmatches `
  --offsets 658782096,1183937475,2964820931,3139511785,3139512628,6443020452,6443021295 `
  --audit > 'D:\Research-Private\chrome-close-phrase-mapping-replay.json'
```

The published ledger gives the expected two mapping rows and the scan-coverage
counts; the memory image, full process maps and unfiltered page text stay private.

The [two-tab Chrome ledger](CHROME_TWO_TABS_CLOSE_ONE_20261001.json) is a
same-browser contrast: two completed anonymous turns in one profile, only the
first target closed, one WinPmem image. The two page targets were identified
separately before the first was closed.
The unchanged state-object parser found one joined turn for the surviving tab,
which scored 5/5 against the page, and none for the closed tab. A separate
known-value scan found closed-tab prompt and response bytes in the browser
parent, but at least one copy bears the `textTail` layout of the observation
script itself. Those bytes are not independent proof of a retained ChatGPT
state object. The private raw was rehashed against its full-decompression
digest and remains alongside the verified gzip archive. The unfiltered image
and page identifiers are not public.

I also replayed the retained Chrome visible-002 and Edge Unicode-002 gzip
archives without expanding another multi-GB raw file. The repository's
`scripts/ram-research/scan_verified_gzip.py` checks the compressed SHA-256,
streams the complete decompressed image to verify the acquisition size and
SHA-256, then gives the **unchanged** state parser a seekable physical-address
view via `indexed-gzip`. After excluding the adapter-only `archive_replay`
metadata, both outputs matched their earlier raw-image parser JSON exactly,
including record hashes and source spans. This checks storage/replay
equivalence; it is not two additional conversation trials.

## September 29 addition

The later instrumented native CLI development case is separate from the pilot
below. Its complete raw acquisition and verified archive are retained privately,
not published. `cli_api_dev_002/README.md` explains the capture, public-wire
grammar failure, observed native grammar and five linked fields. The assistant
ID is not independently thread/turn bound. `method_cli_core_v1/FROZEN_METHOD.json`
records the distinct follow-up method; it does not replace frozen browser v2.
`source-byte-fixture.json` replays three exact reviewed synthetic records through
framing and joining on an artificial tiny image/map, not the original extraction.

The first fresh core-v1 test, `cli_api_heldout_001`, returned zero. Only after
sealing that score was an alternate tagged-model-input/terminal-RPC method
developed on the same image (`cli_api_001_model_development`). It recovers
C/T/P/R/A, **not** core-v1's C/T/U/P/R; model-input IDs are not API user-item IDs.
The next image was a fresh test of both frozen methods and returned zero for
both (`cli_api_heldout_002_core`, `cli_api_heldout_002_model`). Those two result
folders share one image. Every folder has its own exact-byte replay command.
These are three acquisitions, not five independent trials. See the separately
dated `FOLLOWUP_MANIFEST_20260929.json`. Frozen files remain byte-for-byte intact.

## September 16–17 pilot bundle

This bundle contains the frozen parser/joiner, acquisition and run manifests,
redacted field scores, and **synthetic-only** parsed-record fixtures. The signed-in
browser full-RAM images and their process maps were kept private and removed after analysis.
The pilot active, post-exit, idle, and resumed CLI images were also removed after analysis.
The original Cheater challenge image was not audited or added to this bundle.
Consequently, a reader can replay the published join logic on the synthetic
fixtures and check the recorded hashes, but **cannot independently re-extract
the reported records from the original RAM images using this bundle alone**.

## Frozen method and inputs

`FROZEN_METHOD_V2.json` records the exact SHA-256 values of
`trial_iab_visible_002/parse_stream_items.py`,
`method_v2/reconstruct_turns.py`, and `run_frozen_v2.py`. Check them before
replaying. The parser consumes a full physical-memory image plus a Volatility
`windows.memmap` JSON for one image-derived active renderer. It scans mapped
user-space bytes for bounded `{"type":"stream-item"...}` JSON records. The joiner
consumes that parsed JSON and links user, assistant, patch, marker, and completion
records through conversation/turn IDs and parent stream-item ancestry. Neither
stage receives the known prompt, response, message IDs, or offsets. `run_frozen_v2.py`
selects every active `ChatGPT.exe --type=renderer` PID from image-derived
`windows.pslist` and `windows.cmdline` metadata, verifies the frozen parser and
joiner hashes, and
runs the parser and joiner for each selected process. `score_single_v2.py` reads
ground truth **only after** reconstruction.

Example Windows PowerShell commands from the research root for a retained
private image are below. Replace the Volatility path with your own installation;
the archived `run_frozen_v2.py` still contains the original VM's absolute
Volatility path, so changing that runner requires recording its new hash.

```powershell
$trial = 'C:\path\to\trial_dir'
$image = Join-Path $trial 'private\memory.raw'
$vol = 'C:\Users\Win10\Desktop\volatility3-2.8.0\vol.py'
python $vol -q --offline -r json -f $image windows.pslist > (Join-Path $trial 'private\pslist.json')
python $vol -q --offline -r json -f $image windows.cmdline > (Join-Path $trial 'private\cmdline.json')
python .\run_frozen_v2.py --trial $trial
python .\score_single_v2.py --trial $trial
```

The acquisition command was the official WinPmem 1.0-rc2 executable's
`acquire private/memory.raw` operation, run elevated. `acquisition.json` gives its actual start/end UTC, exit code,
tool SHA-256, and image SHA-256. The raw output was default sparse, uncompressed
physical memory. `windows.info` checked that Volatility 3 version 2.8.0 recognized it.
The image acquisition is a time window, not an instantaneous snapshot.
The bundled acquisition driver is signed; the outer executable itself does not
have an Authenticode signature.

## Fixture replay without a private RAM image

The following inputs preserve only records needed for the **synthetic** turns
observed on the two-chat development image and the later visible-response image.
They omit unrelated records and raw SSE bytes. Run from the research root:

```powershell
python .\method_v2\reconstruct_turns.py --parsed .\trial_iab_two_chats_004_results\synthetic_record_fixture.json --output .\trial_iab_two_chats_004_results\replay_v2_local.json
python .\method_v2\reconstruct_turns.py --parsed .\trial_iab_visible_005_results\synthetic_record_fixture.json --output .\trial_iab_visible_005_results\replay_v2_local.json
```

Expected `candidate_turns` counts are **2** and **1**, respectively. The saved
`fixture_reconstruction_v2.json` files show the observed output and supporting
record digests, stream IDs, ancestry, fields, and RAM message-start times.
For the original audit, the same frozen joiner was rerun into
`final_verification/two_chats_replay.json` and
`final_verification/visible_replay.json`. The verifier was corrected on September
29: it now hash-checks all frozen files and **executes fresh joins in a temporary
directory**, rather than trusting those two saved replay files. Run
`python .\final_verification\verify_fixture_replays.py` to print the new check, or
add `--output <new-report.json>` to retain it without overwriting an older report.
It compares parsed JSON and candidate counts with the saved reconstructions.
Byte-level equality is reported separately: the unchanged frozen writer uses
the operating system's newline convention, so Windows and Linux outputs can
differ in bytes while containing identical JSON. The historical check remains
in `final_verification/fixture_replay_check.json`.
Applying the v1 joiner to those same fixture inputs produced zero candidates
because v1 did not accept the observed user-role `v.message` event. These fixture
replays test the joiner on selected records; they do not revalidate acquisition,
process attribution, or the full-image record search.

## Reading the scores and negative trials

The `result*_redacted.json` files compare candidate conversation ID, exact
prompt, actual response, user message ID, and assistant message ID with
post-capture browser ground truth. The user creation time is checked against the
submission window; the assistant creation time is a **start time**, not answer
completion. A valid join also requires a single user ancestor and bounded
supporting records. The visit-only, close-tab, and navigated-away negative
images had zero candidate turns under the frozen method. Post-hoc
`known_marker_*` files count ground-truth-supplied strings separately; those
counts are not blind reconstruction or evidence of erasure/non-erasure of every
copy. All web images came from the same non-reset signed-in VM, and ground truth
was not kept outside it.

The v1 parser's per-record SHA-256 uses a decoded-character count for the byte
slice. For records with unescaped multibyte UTF-8 before their end, the slice
could omit trailing bytes. The synthetic prompts and answers used here are ASCII,
but this limitation has not been retested against the removed private images.
The exact field scores, image hashes, failed trials, and deviations from the
original clean-VM protocol are in `REPORT.md` and `TRIAL_MANIFEST.json`.

## Separate native Codex CLI comparison

The exploratory CLI method was **not frozen in advance**. Its first run selected
the Node launcher alone and missed the native `codex.exe` child; the script was
then corrected using image-derived process metadata. The [CLI process scan](cli_tui_active_010_results/cli_ram_known_scan.json)
used the exact synthetic prompt, answer, marker, and prefixes from ground truth
after capture. It counted bytes in Volatility `windows.memmap` user-space rows
for the selected active native CLI and launcher processes. The [whole-image scan](cli_tui_active_010_results/cli_ram_physical_counts.json)
counted the same known values without process attribution. These are content
presence checks, not a blind turn reconstruction. The [local session-file summary](cli_tui_active_010_results/local_file_baseline.json)
is an independent disk observation.

With a retained private image and matching `ground_truth.json`, the CLI checks
can be rerun from the research root as follows:

```powershell
$trial = 'C:\path\to\cli_tui_active_010'
$image = Join-Path $trial 'private\memory.raw'
$vol = 'C:\Users\Win10\Desktop\volatility3-2.8.0\vol.py'
python $vol -q --offline -r json -f $image windows.pslist > (Join-Path $trial 'private\pslist.json')
python $vol -q --offline -r json -f $image windows.cmdline > (Join-Path $trial 'private\cmdline.json')
python .\cli_ram_known_scan.py --trial $trial --vol $vol
python .\cli_ram_physical_counts.py --trial $trial
```

`cli_tui_active_010_results/acquisition.json` records the image SHA-256, while
`copy_verification.json` records hashes of the eight shareable copies. The
private RAM image is never part of the publication bundle, so once removed the
CLI image cannot be independently rescanned from this bundle either.

The separate post-exit image used the **same synthetic turn** after `/exit` and
has its own [acquisition](cli_tui_exit_011_results/acquisition.json),
[physical count](cli_tui_exit_011_results/cli_ram_physical_counts.json),
and [selected-PID metadata](cli_tui_exit_011_results/process_evidence_exit.json).
With that image retained, `windows.pslist`, `windows.cmdline`, and
`windows.psscan` JSON are inputs to `summarize_cli_exit_metadata.py --trial
<trial> --pids 3916 12820`; `cli_ram_physical_counts.py --trial <trial>`
counts exact known values across the full image. The prior CLI PIDs were not
recovered by those process listings. Physical string hits after exit have no
source-process attribution, especially because the investigator and saved
session file contained the same strings.

The [idle image](cli_tui_idle_012_results/acquisition.json) was made later on
the same VM with no new CLI turn. Its [physical counts](cli_tui_idle_012_results/cli_ram_physical_counts.json)
still show the prior values; [prior-PID metadata](cli_tui_idle_012_results/process_evidence_idle.json)
again found no old CLI process. This control is not a clean no-use VM reset and
cannot identify which remaining memory or disk-backed source supplied a hit.

The [resumed image](cli_tui_resume_013_results/acquisition.json) was made after
starting a new native CLI process with `codex resume` on that same saved session,
without submitting a new prompt. Image-derived [process metadata](cli_tui_resume_013_results/process_evidence.json)
selected native PID 12848 and launcher PID 8608 by the trial folder in their
command lines. The [mapped-page known-value scan](cli_tui_resume_013_results/cli_ram_known_scan.json)
used the same `cli_ram_known_scan.py --trial <trial> --vol <vol>` command above; the script's
optional `--process-tag` selector defaults to the trial folder and was added
before this image was analyzed. Exact prior prompt and answer bytes were found
in the new native process. The [saved JSONL summary](cli_tui_resume_013_results/local_file_baseline.json)
is unchanged, so this is a local-file reload condition, not proof that the old
exited process's RAM survived. All four CLI images concern one synthetic turn;
they are not independent repetitions.

## Ordinary-Chrome state-object follow-up

The three September 30 full images and unfiltered state records are private. The
[frozen Chrome method](FROZEN_CHROME_STATE_V1.json) consists of
[`bounded_json.py`](method_chrome_state_v1/bounded_json.py),
[`chrome_state_records.py`](method_chrome_state_v1/chrome_state_records.py), and
[`chrome_state_turns.py`](method_chrome_state_v1/chrome_state_turns.py). Their
SHA-256 values were recorded before the second prompt was submitted. The
[trial summary](CHROME_FOLLOWUP_20260930.json), per-trial acquisition and copy
verification files, selection JSON and five-field visible-turn scores are public.
The [navigation-state score](chrome_anonymous_cdp_away_003/score.json) reports
the third capture's non-recovery separately. The
[synthetic fixture](chrome_state_synthetic_fixture.json) contains one complete
two-message state object from each *visible* Chrome image, without unrelated RAM bytes.

From the repository root, replay the join on that retained fixture:

```bash
python3 public/research/chatgpt-windows-ram/method_chrome_state_v1/chrome_state_turns.py \
  --parsed public/research/chatgpt-windows-ram/chrome_state_synthetic_fixture.json \
  --output /tmp/chrome-state-replay.json
jq '.candidate_turns | length' /tmp/chrome-state-replay.json
```

The tested count is `2`, one candidate per conversation. This checks the join
logic only. Rescanning the full images requires private access to the verified
raw files; the article gives the Volatility and parser commands for that path.
The later, separately frozen SSE grammar was also run retrospectively on both
Chrome NetworkService maps from visible-002. It framed zero complete events in
either map, while the Chrome renderer-state result remained two turns;
MemProcFS matched 64/64 sampled mapped pages. These are different grammars and
process scopes, not conflicting scores for the same method.

## Retrospective native request/core join

The [October 1 ledger](CLI_REQUEST_CORE_RETROSPECTIVE_20261001.json) reports a
new, separately labeled grammar developed on the retained museum image and
then applied to the earlier lighthouse and observatory images. The
[downloadable method](method_cli_request_core_v1/README.md) contains the exact
Volatility/parser command and a synthetic join test. From its directory, run
`python3 -m unittest test_cli_request_core_turns.py`. That test checks the
identifier rule and conflict handling, not recovery from the private RAM files.
All three full-image checks used a hash-verified raw image and one image-derived
native process map; the relay was checked separately. No ground-truth values
were passed to the parser. The older frozen-method scores are unchanged.

The [prospective fresh-turn ledger](CLI_REQUEST_CORE_PROSPECTIVE_20261001.json)
reports a fourth, new image acquired after that method freeze. Run the same
parser on its image-selected native PID 5968 map and separately on relay PID
5708, as shown in the article. Its native result was one candidate; relay
zero. The sealed native output matched four independently host-observed fields,
and MemProcFS reread both accepted record occurrences. This new trial does not
change the three-image retrospective scores or the earlier core/model failures.
The [reviewed viewer file](CLI_REQUEST_CORE_PROSPECTIVE_VIEWER_20261001.json)
contains only selected synthetic fields checked against the private recovery
and host score. The [terminal figure](screenshots/86-cli-fresh-parser-direct.png)
instead shows the unchanged parser running on the complete, verified image.
Its source hash and crop are recorded in [screenshot provenance](ACTUAL_SCREENSHOTS.json).

## Earlier VMware client-open snapshot

The [pretest ledger](CLIENT_OPEN_SNAPSHOT_CONTROL_20261001.json) reports a
separate saved-memory format check across every active `ChatGPT.exe`, Chrome
and Edge renderer in that image. The [VMware-aware adapter](method_vmware_snapshot_v1/README.md)
shows the Bash Volatility mapping command and the Windows MemProcFS scan. Its
synthetic test can be run with `python -m unittest test_scan_vmware_snapshot.py`
from the method directory. No private `.vmem`, process map, or recovered
account content is in the public bundle. Zero structural signatures in this
pretest state are not a scored conversation result.

## Signed-in Edge visible-turn follow-up

The [signed-in visible-turn ledger](EDGE_SIGNEDIN_VISIBLE_20261001.json) distinguishes
two memory images of one completed synthetic turn: a saved VMware state and a
subsequent direct WinPmem gzip acquisition. The [actual-page screenshot
crop](screenshots/22-signedin-edge-teapot-visible.png) was captured between
them. The compressed host copy matches the guest-recorded SHA-256; its full
decompressed stream and a temporary NTFS sparse raw copy matched the recorded
raw digest. That temporary raw copy was removed after analysis; the verified
gzip and saved VMware memory remain private.

`select_browser_renderers.py` takes only image-derived `pslist` and `cmdline`
JSON, not the prompt or conversation ID. Its renderer-envelope scan found the
submission in saved memory but not a complete answer. The
[signed-in SSE method](method_signedin_sse_v1/README.md) instead selects the
unique active Edge NetworkService utility, frames complete `data:` events,
verifies the intervening control-line bytes, and joins user/system/assistant
ancestry, answer patches, markers, and completion. Its development scan of the
saved VMware state yielded one exact visible C/P/R turn; the unchanged frozen
method yielded no candidate in the later direct image of the *same* turn. For
that later image, I also ran the same event scanner and joiner separately on
the resident user maps of all 11 active Edge processes selected from
`windows.pslist`. Six complete events appeared in one renderer, none in the
other ten processes, and no process produced a joined candidate. The browser
parent's one `data:` signature was incomplete. This is a timing comparison,
not prospective new-prompt validation or a whole-physical-memory proof.
Unfiltered signed-in records stay private. `posthoc_known_raw.py` is deliberately a
different diagnostic: it receives the screen's exact values and can report
physical and mapped occurrence counts, but it cannot reconstruct a turn.

The later image's NetworkService still had the same PID and process-creation
metadata. I compared the **15 previously recovered event addresses**, not
known text, with its new `windows.memmap`. All 15 virtual ranges were mapped,
none had the earlier record hash, nine had the same physical spans, and
MemProcFS confirmed all 15 later reads and translations. This is a post-hoc
buffer-lifetime check, not a new turn search. For equivalent *private* inputs,
from the repository root in PowerShell:

```powershell
py scripts/ram-research/compare_same_va_records.py `
  --reference 'C:\private\saved-network-sse.json' `
  --later-image 'D:\private\verified-direct.raw' `
  --later-memmap 'C:\private\direct-network-memmap.json' `
  --sdk-root 'D:\tools\MemProcFS' --pid 2936 `
  --output 'C:\private\same-va-comparison.json'
```

I also applied the frozen SSE grammar retrospectively to the earlier saved
Edge state where the prompt appeared but no answer rendered. Its image-selected
NetworkService yielded zero complete events; the
[failed-response ledger](EDGE_SIGNEDIN_UI_EMPTY_20261001.json) keeps that state
out of the finished-answer comparison. The older no-submit image similarly
yielded zero signatures and turns when the later Chrome state-object method
was rerun across all three Edge renderers. The [control record](edge_no_submit_control_001/RESULTS.json)
labels that check retrospective, not a second control capture.

## Same-tab Chrome multi-turn boundary

The [two-turn ledger](CHROME_MULTITURN_VISIBLE_20261001.json) records one later
capture of two finished turns in one anonymous Chrome tab. The article shows
the guest submission and acquisition commands. On the private verified raw
image, use the same frozen Chrome selection, per-renderer `windows.memmap`,
`chrome_state_records.py`, and `chrome_state_turns.py` commands shown for the
earlier visible Chrome image. All three renderer PIDs are selected before
reading the page observations. Seal the joiner's output hash before running
`score_chrome_multiturn.py` with the two submission records and the DOM-ID
observations from before and after the follow-up. Those observations are
private scoring inputs, never RAM-parser inputs. `test_chrome_multiturn_join.py`
and `test_score_chrome_multiturn.py` are synthetic checks of the join and
score rules, not replacements for the acquired image. The public bundle
provides the reviewed [screenshots](ACTUAL_SCREENSHOTS.json) and counts but
not the full raw memory or unfiltered page records.

## Unsent Chrome draft control

The [draft ledger](CHROME_DRAFT_NOSUBMIT_20261001.json) and [actual page
screenshot](screenshots/36-chrome-unsent-draft-crop.png) document one fresh
anonymous Chrome tab with text in its composer but no submitted message. The
article includes the guest-side commands. CDP `Input.insertText` filled the
composer without dispatching Send or Enter. The separately
retained page observations checked the new-chat URL, exact composer text and
zero submitted-message elements before and after WinPmem acquisition.

On the hash-verified private raw image, use image-derived `windows.pslist` and
`windows.cmdline` to select all active `chrome.exe --type=renderer` processes,
then `windows.memmap` and the unchanged frozen Chrome state parser/joiner as
in the visible-turn trial. Seal the zero-candidate output *before* running
`posthoc_draft_known_text.py` with the independently observed draft. The
post-hoc script rehashes the full raw image, counts both UTF-8 and UTF-16LE
physical copies, and maps exact bytes to each selected renderer. The optional
`crosscheck_draft_hits_memprocfs.py` rereads the first mapped hit of each
encoding with MemProcFS. These exact-byte diagnostics receive the known draft;
they cannot establish submission or count as blind reconstruction. Full image,
unfiltered maps and page observations stay private.

## Same-tab Chrome reload boundary

The [reload ledger](CHROME_RELOAD_20261001.json) and [actual screenshot
provenance](ACTUAL_SCREENSHOTS.json) record a completed anonymous turn before
and an empty new-chat page after `Page.reload` on the same target. The article
contains the guest-side sequence. CDP `Page.reload` reloaded the same target
without closing or replacing it. The live page's two
message IDs and text were retained privately before reload; the target ID,
URL, and absence of submitted DOM elements were checked afterward and again
after acquisition.

On the verified private raw image, select all active Chrome renderers from
image-derived `windows.pslist` and `windows.cmdline`, map each with
`windows.memmap`, then run the unchanged frozen `chrome_state_records.py` and
`chrome_state_turns.py` on those maps. Seal the output before invoking
`score_chrome_reload.py` with the separately saved pre/post page records. A
zero candidate is a reportable result. Only after scoring, the independent
pre-reload values may be supplied to `posthoc_known_raw.py`; its exact-byte
counts cannot turn the frozen zero into a reconstructed message relationship.
`crosscheck_posthoc_hits_memprocfs.py` rereads one mapped hit per present
encoding and value with independent MemProcFS bytes/translations. Full image,
addresses and page records remain private.

The [screen-only repeat](CHROME_RELOAD_SCREEN_ONLY_20261001.json) uses the same
frozen RAM parser and reload action, but `submit_quiet` never requests the
answer as text. `inspect_count` reads only the URL and number of UUID-shaped
message elements; an actual PNG records the finished answer. The article gives
the guest commands. Hash the private screenshot, seal the zero-candidate RAM
output, and only *then* transcribe an answer-only sentence. Run
`score_chrome_reload_screenonly.py` with the saved submission, pre-reload
count, reload, post-reload count, post-acquisition count, screenshot metadata
and PNG. Its output scores at most conversation ID, prompt and that sentence;
it does not independently score message IDs or the full response. Finally,
`posthoc_known_raw.py` and `crosscheck_posthoc_hits_memprocfs.py` can check
exact physical/mapped bytes separately. The sentence's one active-renderer
copy is not itself a reconstructed turn or proof of its V8 object type.

## Visible Chrome turn with no answer-text probe

The [visible screen-only ledger](CHROME_VISIBLE_SCREEN_ONLY_20261001.json) is a
fresh completed turn acquired *before* any reload. `submit_quiet` sent the
synthetic prompt, `inspect_count` checked the same conversation URL and two
message elements on both sides of WinPmem acquisition, and `screenshot` saved
the finished answer as PNG pixels. The article includes the guest commands and
the full/cropped actual screenshot. The controller did not return answer text
or DOM message IDs.

For the verified private image, Volatility
`windows.info`, `windows.pslist`, `windows.cmdline`, image-selected renderer
`windows.memmap`, and the unchanged September 30 Chrome parser/joiner were run without
ground-truth values. Seal `chrome_v1_turns_private.json` before transcribing
the screenshot. `score_chrome_visible_screenonly.py` then checks target and
page stability, pre-acquisition screenshot SHA-256 and chronology, absence of
answer text in the controller records, and candidate C/P/full rendered R.
The resulting 3/3 score does **not** independently verify DOM U/A; their
relationship is internal to the recovered object. On the same raw image,
`crosscheck_records_memprocfs.py` independently verifies both accepted record
occurrences and virtual-to-physical translations. The private gzip archive
can regenerate the removed temporary sparse raw.

## Flat-physical Chrome-state contrast

The [contrast ledger](PHYSICAL_CHROME_STATE_CONTRAST_20261001.json) adds a
separate whole-image scan to the closed-only, two-tab, screen-only reload and
screen-only visible experiments. It is not a
Volatility process map. The adapter verifies both the compressed archive and
its complete decompressed byte stream, expands the latter only in host RAM,
then feeds one physical identity row to the unchanged bounded Chrome-state
grammar. For a local copy of the private two-tab archive, run from the blog
repository root in PowerShell with `indexed_gzip` 1.10.3 installed (the shared
scanner module imports it):

```powershell
$case = Get-Content .\public\research\chatgpt-windows-ram\CHROME_TWO_TABS_CLOSE_ONE_20261001.json -Raw | ConvertFrom-Json
py .\scripts\ram-research\scan_physical_chrome_state.py `
  --archive 'D:\Research-Private\chrome-two-tabs-close-one-005.raw.gz' `
  --archive-sha256 $case.acquisition.archive_sha256 `
  --raw-size $case.acquisition.decompressed_logical_bytes `
  --raw-sha256 $case.acquisition.decompressed_sha256 `
  --output 'D:\Research-Private\chrome-two-tabs-physical-state-replay.json'
```

Use the matching public ledger and private archive for the other three rows.
The parser receives no expected conversation or prompt, and its unfiltered
JSON must remain outside the public site. A record spanning nonadjacent
physical pages is outside this flat scan's reach; a record found here has no
process attribution until checked against a separate virtual map. The blog
repository contains the adapter source; the public evidence bundle contains
only its summary hashes, not the private RAM archives.

For the separate Edge close-tab SSE check, use its matching private archive:

```powershell
$edge = Get-Content .\public\research\chatgpt-windows-ram\EDGE_CLOSE_TAB_20261001.json -Raw | ConvertFrom-Json
py .\scripts\ram-research\scan_physical_sse.py `
  --archive 'D:\Research-Private\edge-anonymous-cdp-close-005.raw.gz' `
  --archive-sha256 $edge.acquisition.archive_sha256 `
  --raw-size $edge.acquisition.decompressed_logical_bytes `
  --raw-sha256 $edge.acquisition.decompressed_sha256 `
  --output 'D:\Research-Private\edge-close-physical-sse-replay.json'
```

The [Edge physical ledger](EDGE_CLOSE_PHYSICAL_SSE_20261001.json) reports
framed-event counts, not just `data:` prefix hits. A flat physical scan cannot
recover an SSE event whose pages are physically scattered or attach an event
to Edge without an independent process map.

## Synthetic UTF-8 digest boundary

Run `py -m unittest discover -s scripts/ram-research -p test_pilot_utf8_digest_boundary.py -v` from the repository root. This builds
two artificial one-record images and runs the released pilot parser without
changing it. The [fixture](PILOT_UTF8_DIGEST_BOUNDARY_20261001.json) records
the ASCII full-byte match and the unescaped-UTF-8 digest mismatch. It tests a
known source-code boundary, not a new RAM capture or any old image's content.
