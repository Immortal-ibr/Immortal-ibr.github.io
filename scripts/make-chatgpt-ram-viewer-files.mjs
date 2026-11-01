// Compact GUI views of already reviewed public recovery files, never host ground truth.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/research/chatgpt-windows-ram');
const read = relative => {
  const bytes = fs.readFileSync(path.join(root, relative));
  return {value: JSON.parse(bytes), source: relative,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex')};
};
const write = (relative, value) => fs.writeFileSync(path.join(root, relative), JSON.stringify(value, null, 2) + '\n');
const provenance = source => ({
  presentation_only: 'Fields selected from reviewed recovery.json, not an independent recovery or a new experiment',
  source_data: source.source, source_sha256: source.sha256,
});
const requireOne = (rows, label) => {
  if (rows.length !== 1) throw new Error(`Expected one ${label}, got ${rows.length}`);
  return rows[0];
};
const candidates = source => {
  const join = source.value.join;
  if (!join || !Array.isArray(join.candidates) || join.candidate_count !== join.candidates.length) {
    throw new Error(`Inconsistent candidate ledger: ${source.source}`);
  }
  return join.candidates;
};
const isHumanInput = r => r.payload.type === 'message' && r.payload.role === 'user' &&
  r.payload.internal_chat_message_metadata_passthrough?.content_item_kinds?.length > 0 &&
  r.payload.internal_chat_message_metadata_passthrough.content_item_kinds.every(k => k === 'user.text');
const isTerminal = r => r.payload.method === 'turn/completed';

const failedCore = read('cli_api_heldout_001/recovery.json');
if (candidates(failedCore).length !== 0) throw new Error('The failed core score must remain zero');
write('cli_api_heldout_001/result-for-viewer.json', {
  candidate_count: candidates(failedCore).length,
  accepted_user_item_count: failedCore.value.records.filter(r => r.payload.type === 'item_completed').length,
  accepted_record_types: failedCore.value.records.map(r => r.payload.type),
  surviving_records: failedCore.value.records.map(r => r.payload),
  ...provenance(failedCore),
});

const modelDev = read('cli_api_001_model_development/recovery.json');
const input = requireOne(modelDev.value.records.filter(isHumanInput), 'tagged input');
const terminal = requireOne(modelDev.value.records.filter(isTerminal), 'terminal RPC');
if (input.payload.internal_chat_message_metadata_passthrough.turn_id !== terminal.payload.params.turn.id) {
  throw new Error('Model development records do not share the same turn ID');
}
write('cli_api_001_model_development/input-record-for-viewer.json', {
  recovered_payload: input.payload, ...provenance(modelDev),
});
write('cli_api_001_model_development/terminal-record-for-viewer.json', {
  recovered_payload: terminal.payload, ...provenance(modelDev),
});

const museumCore = read('cli_api_heldout_002_core/recovery.json');
const museumModel = read('cli_api_heldout_002_model/recovery.json');
if (candidates(museumCore).length || candidates(museumModel).length) {
  throw new Error('Both museum candidate counts must remain zero');
}
const task = requireOne(museumCore.value.records.filter(r => r.payload.type === 'task_complete'), 'museum completion');
const human = requireOne(museumModel.value.records.filter(isHumanInput), 'museum input');
const metadata = human.payload.internal_chat_message_metadata_passthrough;
if (task.payload.turn_id !== metadata.turn_id) throw new Error('Partial museum link does not match');
write('cli_api_heldout_002_model/partial-link-for-viewer.json', {
  core_v1: {
    candidate_count: candidates(museumCore).length,
    accepted_record_types: museumCore.value.records.map(r => r.payload.type),
    'task_complete.turn_id': task.payload.turn_id,
    'task_complete.last_agent_message': task.payload.last_agent_message,
  },
  model_input_v1: {
    candidate_count: candidates(museumModel).length,
    accepted_terminal_rpc_count: museumModel.value.records.filter(isTerminal).length,
    'metadata.turn_id': metadata.turn_id,
    'metadata.content_item_kinds': metadata.content_item_kinds,
    'content[0].text': human.payload.content[0].text,
  },
  turn_ids_equal: task.payload.turn_id === metadata.turn_id,
  is_full_five_field_reconstruction: false,
  presentation_only: 'Post-score partial T/P/R comparison; both frozen candidate counts stay zero',
  sources: [provenance(museumCore), provenance(museumModel)],
});
console.log('Created four GUI views using only reviewed recovery files; frozen parsers and scores unchanged.');
