# Second fresh capture: core-v1 remains zero

This is the same September 29 raw image evaluated in `cli_api_heldout_002_model`,
not another capture. Both methods were frozen before the new synthetic request.
The native backend PID 9144 was live. The host observed completion at
05:19:20.507455 UTC; WinPmem acquired 05:19:23.1894378–05:19:52.6600930 UTC
(delay 2.681982 seconds; interval 29.4706552 seconds; exit 0).

The full 7,147,094,016-byte raw image and 2,938,200,095-byte archive are retained
privately. Pinned-TLS copy and complete decompression matched their hashes.
Volatility's native map contains 22,121 user rows; 125,888 kernel rows were
excluded. MemProcFS matched all 32 deterministic mapping/byte samples and every
occurrence of the two recovered core records.

The unchanged core-v1 method returned **zero candidates**. `task_complete` and a
standalone `agentMessage` survived, but no accepted complete user item linked
the prompt and thread to that turn. The observer relay had one standalone
assistant object and zero candidates. Reachability is not exclusive ownership.

The synthetic host observation is separately labeled `observation-not-recovery.json`;
it must not be presented as a recovered turn. No parser rule was changed against
this image before scoring. This is a method failure in selected resident user
mappings, not proof of erasure or a recovery-rate estimate.

From the public bundle root:

```bash
python3 method_cli_core_v1/replay_cli_core_fixture.py \
  --method method_cli_core_v1 \
  --fixture cli_api_heldout_002_core/source-byte-fixture.json \
  --output /tmp/core-second-fresh-replay.json
```

The exact source-byte replay must recover two records and zero candidates. The
image/map used for that replay is artificial; original extraction and attribution
cannot be independently reproduced from these small public fixtures.
