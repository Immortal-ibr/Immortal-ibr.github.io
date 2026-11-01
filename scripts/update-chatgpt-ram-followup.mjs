// Assemble the follow-up ledger from reviewed public outputs, not private RPC logs.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."),
  "public/research/chatgpt-windows-ram");
const read = (name) => JSON.parse(fs.readFileSync(path.join(root, name), "utf8").replace(/^\uFEFF/, ""));
const digest = (name) => crypto.createHash("sha256").update(fs.readFileSync(path.join(root, name))).digest("hex");
const layouts = [
  { key: "lighthouse", bundles: [["cli_api_dev_002", "core-v1", "development"]] },
  { key: "observatory", bundles: [["cli_api_heldout_001", "core-v1", "fresh frozen-method test"],
    ["cli_api_001_model_development", "model-input-v1", "post-score development on the SAME image"]] },
  { key: "museum", bundles: [["cli_api_heldout_002_core", "core-v1", "fresh frozen-method test"],
    ["cli_api_heldout_002_model", "model-input-v1", "fresh frozen-method test"]] },
];
const captures = layouts.map(({ key, bundles }) => {
  const base = bundles[0][0];
  const acquisition = read(`${base}/acquisition.json`);
  const copy = read(`${base}/copy-verification.json`);
  const evaluations = bundles.map(([bundle, method, role]) => {
    const score = read(`${bundle}/score.json`);
    const records = read(`${bundle}/recovery.json`);
    const crosscheck = read(`${bundle}/memprocfs-records.json`);
    if (score.raw_sha256 !== copy.raw_sha256 || score.recovered_output_sha256 !== digest(`${bundle}/recovery.json`)) {
      throw new Error(`Mismatched sealed evidence in ${bundle}`);
    }
    return { bundle, method, role, score_file: `${bundle}/score.json`,
      recovered_output_sha256: score.recovered_output_sha256,
      candidate_count: score.candidate_count,
      scored_field_set: method === "core-v1" ? ["thread", "turn", "api_user_item", "prompt", "response"]
        : ["thread", "turn", "prompt", "response", "assistant_item"],
      exact_candidate_scores: score.candidate_scores,
      source_records: records.records.length,
      source_occurrences_crosschecked: crosscheck.occurrences.length,
      all_record_bytes_and_translations_match: crosscheck.all_record_bytes_and_translations_match,
      response_to_acquisition_seconds: score.response_to_acquisition_seconds };
  });
  const partial = {};
  if (key === "museum") {
    const tasks = read(`${base}/recovery.json`).records.filter(r => r.payload.type === "task_complete");
    const inputs = read(`${bundles[1][0]}/recovery.json`).records.filter(r => r.payload.type === "message");
    if (tasks.length !== 1 || inputs.length !== 1 || tasks[0].payload.turn_id !==
        inputs[0].payload.internal_chat_message_metadata_passthrough.turn_id) {
      throw new Error("The reported post-score partial turn link does not match its source records");
    }
    partial.post_score_partial_evidence = {
      fields_linked: ["turn", "prompt", "response"],
      thread_binding_recovered: false, assistant_id_independently_bound: false,
      source_record_sha256: [tasks[0].record_sha256, inputs[0].record_sha256],
      scope: "Manual cross-representation comparison AFTER scoring; neither frozen zero result changes",
    };
  }
  return { key, trial_id: acquisition.trial_id, ...partial,
    acquisition_start_utc: acquisition.started_utc, acquisition_end_utc: acquisition.ended_utc,
    acquisition_seconds: acquisition.elapsed_seconds, acquisition_exit_code: acquisition.exit_code,
    raw_logical_bytes: copy.raw_logical_bytes, raw_sha256: copy.raw_sha256,
    archive_bytes: copy.archive_bytes, archive_sha256: copy.archive_sha256,
    full_copy_and_decompression_verified: copy.copy_verified && copy.decompressed_digest_verified,
    full_image_disposition: "Raw image AND verified archive retained privately outside OneDrive; not published",
    evaluations };
});
const freezes = ["method_cli_core_v1", "method_cli_model_input_v1"].map((folder) => ({
  folder, manifest_sha256: digest(`${folder}/FROZEN_METHOD.json`), ...read(`${folder}/FROZEN_METHOD.json`),
}));
const output = {
  study_date: "2026-09-29", scope: "Separate instrumented native app-server stdio follow-up; not browser or TUI validation",
  complete_acquisitions: captures.length, evaluated_method_image_pairs: captures.reduce((n, c) => n + c.evaluations.length, 0),
  controls_or_primary_matrix_completed: false,
  environment: { windows: "Windows 10 Pro 22H2, 19045 UBR 4894", vmware: "17.5.2 build 23775571",
    configured_ram_bytes: 6073352192, vcpus: 4, native_cli: "0.158.0-alpha.2.1",
    volatility: "3 Framework 2.8.0, Bash in Kali WSL", memprocfs: "5.14.9.199",
    acquisition_tool_sha256: "86691bb4af2c17dd9ec4834c04a99ad51e04f780a07d1b05bc382a5d1892e0c4" },
  separation: { reset_before_each_capture: true, reset_point: "ram-tools-ready-20260929-v1, UID 3",
    account_history_reset: false, observation_and_scoring_logs: "host only",
    intended_request_enters_guest: true, native_session_behavior_disabled: false,
    guest_relay: "Opaque 16 KiB stdio/network buffers; separately analyzed observer effect",
    transport: "Private VMware NAT, TLS 1.2, pinned ephemeral certificate; no firewall change",
    first_party_credentials_exported: false, account_identity_claimed: false },
  freezes, captures,
  limits: ["Core-v1 failed both fresh tests; model-input-v1 failed its one fresh test",
    "The observatory model result is development on the failed core image, not a held-out success",
    "No model-input message ID is equated with an API user-item ID",
    "Model-input create_time is not a human submission timestamp",
    "No causal acquisition-delay conclusion, recovery-rate estimate, or exclusive page ownership claim",
    "Public source-byte fixtures replay framing/joining on artificial maps, not whole-image extraction",
    "Listener preflights are not captures; ordinary Chrome/Edge/app/TUI matrix remains unexecuted"],
};
fs.writeFileSync(path.join(root, "FOLLOWUP_MANIFEST_20260929.json"), JSON.stringify(output, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ captures: output.complete_acquisitions, method_image_pairs: output.evaluated_method_image_pairs }));
