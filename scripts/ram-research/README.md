# Clean-VM follow-up tooling

Development and replay scripts for the September 29–October 1 follow-ups.
The earlier frozen methods and published pilot fixtures remain unchanged;
the experiment ledger in the article distinguishes captures from replays.

- `PROTOCOL.md`: reset, separation, validation, capture matrix, and reporting rules.
- `bounded_json.py`: **host** framing parser under development. It accepts only
  uncompressed raw physical bytes and a matching Volatility user-space memmap.
  Do not give it a VMware VMEM unless the offsets have been converted to a flat
  physical image first. Its stream-item signature is still client-specific.
- `select_browser_renderers.py`: chooses every active Chrome or Edge renderer
  from image-derived `windows.pslist` and `windows.cmdline` JSON. It accepts no
  known prompt or conversation ID and reports missing command lines separately.
- `test_bounded_json.py`: synthetic framing/SSE regressions, not experimental RAM
  captures. Run `python -m unittest discover -s scripts/ram-research -v`.
- `flatten_vmware.py`: matched VMEM/VMSN to guest-physical raw conversion using
  Volatility's actual region mappings. Verify Windows identity on both outputs.
- `crosscheck_memprocfs.py`: independent process inventory and deterministic
  mapping/byte samples from the same image. Full command lines stay private.
- `count_known_raw_gzip.py`: post-hoc exact-value count over a verified private
  gzip image, drawing synthetic values from independently recorded page and DOM
  observations. It is not a blind reconstruction method.
- `attribute_known_browser_hits.py`: post-hoc counts across chosen Volatility
  resident user mappings; first-hit addresses stay private.
- `classify_observer_mapped_hits.py`: post-hoc context check for *all* mapped
  known prompt/answer hits in a selected process. It records only structural
  offsets, optionally rereads the exact observation string with MemProcFS, and
  keeps its addresses and result outside the repository. It is not a blind parser.
- `crosscheck_known_hits_memprocfs.py`: checks representative mapped hit bytes
  and translations against independent MemProcFS reads.
- `count_known_vmware_mapped.py`: post-hoc exact-value control over VMware-aware
  resident renderer mappings. It takes independently observed synthetic values,
  never supplies them to the structural parsers, and cannot prove a turn.
- `verify_archive.py`: private zstandard archiving with full decompression/hash
  verification. It does not delete the raw image.
- `verify_gzip_copy.py`: checks the transferred archive and the full decompressed
  raw digest, refusing to replace an existing image or report.
- `scan_verified_gzip.py`: verifies both compressed and decompressed SHA-256,
  then exposes the raw address space through seek/read to an **unchanged**
  browser-state or CLI request/core parser. This avoids a second multi-GB raw
  copy. `--backend memory` expands the verified image in host RAM when random
  seeks into indexed gzip are slow; allow enough free memory for the full raw
  image. Unfiltered output must stay outside the repository.
- `scan_verified_gzip_batch.py`: verifies one gzip once and reuses its in-memory
  address space for several unchanged parser/map combinations. The October 15
  blank-tab trial used this to scan all active Chrome maps and the exited old
  renderer without writing a second raw image.
- `posthoc_known_gzip.py`: separate, ground-truth-supplied exact-byte residue
  counts over the same verified gzip and selected process maps. Run it only
  after structural outputs are sealed; it cannot reconstruct a turn. Its
  unfiltered first-hit addresses stay private.
- `test_scan_verified_gzip.py`: synthetic compressed/raw equivalence and
  wrong-digest regressions for that adapter; no private RAM is included.
- `verify_direct_gzip.py`: checks the transferred archive against the guest's
  compressed digest and reads to gzip EOF, recording raw size and digest
  without creating another multi-GB file. Direct streaming has no independent
  guest-side raw digest.
- `estimate_sparse_raw.py` and `inflate_sparse_raw.py`: conservative space
  estimate and a temporary NTFS sparse raw image for Volatility's flat-file
  input. The signed-in case's derived raw copy was removed after analysis;
  its hash-verified gzip archive remains private.
- `browser_json_envelopes.py` and `scan_vmware_browser_envelopes.py`: bounded
  structural request/event scanners for the signed-in UI development case.
  They receive no known prompt or ID. Unfiltered signed-in records stay
  private; a complete response/turn is not inferred from a request envelope.
- `select_edge_network_service.py`: selects exactly one active Edge
  NetworkService utility from image-derived process and command-line JSON.
- `sse_event_records.py` and `signedin_sse_turns.py`: complete SSE framing,
  verified inter-event control bytes, ancestry and response-patch join for the
  saved signed-in Edge state. The core method was frozen before the later
  direct acquisition was parsed. The saved state produced one full turn; the
  later image of that same turn produced none under the unchanged method.
- `score_signedin_sse.py`: compares a sealed recovery output with separately
  recorded visible conversation ID, prompt and answer. It reports 3/3 visible
  fields and explicitly does not claim independent DOM verification of the
  recovered user/assistant IDs.
- `compare_same_va_records.py`: post-hoc comparison of previously recovered
  event addresses against a later image of the same process. It checks exact
  hashes, mapped and physical spans, and optionally MemProcFS reads; it does
  not search for new records or prove erasure elsewhere.
- `posthoc_known_raw.py`: separately receives the observed synthetic values
  for exact-byte residue counts. Its output cannot be scored as blind recovery.
- `test_fixture_verifier.py`: verifies that public fixture checks execute fresh
  joins, ignore stale replay reports and reject changed frozen code.
- `cli_rpc_records.py`: bounded public-wire RPC grammar, plus a development-only
  format inspection option. Unfiltered inspection output must remain private.
- `cli_core_events.py`: a different grammar for the three native serializations
  observed in the development capture. Links by exact turn ID, never by known
  text. A standalone assistant ID remains unbound even if its text matches.
- `score_cli_core.py`: seals the RAM-parser output before reading host-only RPC
  observations; scores five linked fields and timestamps separately.
- `crosscheck_records_memprocfs.py`: independently rereads every recovered record
  occurrence and compares exact byte hashes and virtual-to-physical translations.
- `score_chrome_multiturn.py`: post-seal scorer for two turns in one Chrome tab.
  It checks that the first DOM pair survives the second submission and scores
  the two RAM candidates separately; the frozen state parser and joiner receive
  none of the page observations. `test_chrome_multiturn_join.py` separately
  records the frozen joiner's behavior on synthetic two- and four-message states.
- `posthoc_draft_known_text.py` uses a known, unsubmitted draft only
  after the frozen Chrome parser's output has been sealed; it counts exact
  physical and mapped bytes, not turns. `crosscheck_draft_hits_memprocfs.py`
  independently checks representative mapped bytes and translations.
- `score_chrome_reload.py`
  checks the pre/post target and DOM state *after* the frozen RAM output is
  sealed; a zero candidate is recorded rather than treated as a scorer error.
  Its synthetic tests cover both zero and exact five-field recovery.
- The lower-observer reload repeat submitted a synthetic prompt without reading its
  answer as text, then checked only the page URL and UUID-shaped message count.
  The finished answer was preserved as actual PNG pixels. After sealing the blind
  RAM output, `score_chrome_reload_screenonly.py` verifies the pre/post target,
  screenshot hash and absent answer sentence in controller JSON. It can score
  only C/P/answer fragment, not independent message IDs or a full response;
  four synthetic tests cover its guardrails. Known-value byte checks remain
  separate from this scorer.
- `score_chrome_visible_screenonly.py`: post-seal C/P/full-response scorer for
  a fresh visible Chrome turn acquired with the same quiet controller. It
  checks a pre-acquisition PNG hash, target/page stability across WinPmem,
  chronology and absence of answer text in controller JSON. Five synthetic
  tests cover exact, zero, changed-target, chronology and observer-contamination
  cases. It never upgrades the two internally linked RAM IDs to independently
  observed DOM IDs.
- `cli_model_turns.py`: separate development grammar for `user.text` model-input
  metadata plus a completed terminal RPC. It excludes generated environment
  context and never equates a model-input ID with an API user-item ID.
- `score_cli_model.py`: seals and scores C/T/P/R/A for that separate method;
  core-v1's C/T/U/P/R failure cannot be relabeled as its validation success.
- `freeze_cli_core.py`: snapshots either method before a new submission. A freeze
  and synthetic tests are not additional RAM captures.
- `export_cli_core_case.py` / `export_cli_model_case.py`: post-score publication
  filters that refuse extra fields or unrelated text. A failed case's host
  observation is labeled NOT a RAM recovery. Private RPC/format scans are never
  copied wholesale into the public bundle.
- `replay_cli_core_fixture.py` / `replay_cli_model_fixture.py`: verify frozen
  source and exact record-byte digests before fresh framing/joining. Their tiny
  image/maps are artificial and cannot verify original process attribution.

Parser outputs, RAM images, profile copies, and ground truth stay outside this
repository. The public bundle is populated only after private-data review.

References:

- [WinPmem source and acquisition documentation](https://github.com/Velocidex/WinPmem)
- [WinPmem release containing the pinned 1.0-rc2 asset](https://github.com/Velocidex/WinPmem/releases/tag/v4.0.rc1)
- [Volatility memmap implementation](https://github.com/volatilityfoundation/volatility3/blob/v2.8.0/volatility3/framework/plugins/windows/memmap.py)
- [WHATWG SSE parsing and dispatch rules](https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream)
- [Official Codex CLI documentation](https://learn.chatgpt.com/docs/codex/cli)
- [Official app-server protocol and version-specific schema generation](https://learn.chatgpt.com/docs/app-server)

The WinPmem executable used for staging is pinned to
`86691bb4af2c17dd9ec4834c04a99ad51e04f780a07d1b05bc382a5d1892e0c4`.
This matches the upstream release asset digest. The `signed` filename refers to
the bundled driver; the outer executable does not have an Authenticode signature.
