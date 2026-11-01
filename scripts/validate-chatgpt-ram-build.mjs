// Check the built copies and crosslinks without making a browser/network request.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const relative = "research/chatgpt-windows-ram";
const source = path.join(site, "public", relative);
const built = path.join(site, "dist", relative);
const manifest = JSON.parse(fs.readFileSync(path.join(source, "ASSET_MANIFEST.json"), "utf8"));
const hash = bytes => crypto.createHash("sha256").update(bytes).digest("hex").toUpperCase();
function allFiles(directory, relative = "") {
  const result = [];
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const nextRelative = relative ? `${relative}/${item.name}` : item.name;
    const nextPath = path.join(directory, item.name);
    // OneDrive placeholders can appear as links in Dirent even when lstat identifies a regular file.
    const entry = fs.lstatSync(nextPath);
    if (entry.isSymbolicLink()) throw new Error(`Symlink in built evidence: ${nextRelative}`);
    if (entry.isDirectory()) result.push(...allFiles(nextPath, nextRelative));
    else if (entry.isFile()) result.push(nextRelative);
    else throw new Error(`Unexpected built evidence type: ${nextRelative}`);
  }
  return result;
}
const expected = new Set(["ASSET_MANIFEST.json", ...manifest.files.map(file => file.path)]);
const actual = new Set(allFiles(built));
for (const name of actual) if (!expected.has(name)) throw new Error(`Unreviewed built evidence: ${name}`);
for (const name of expected) if (!actual.has(name)) throw new Error(`Built evidence missing: ${name}`);
if (hash(fs.readFileSync(path.join(built, "ASSET_MANIFEST.json"))) !==
    hash(fs.readFileSync(path.join(source, "ASSET_MANIFEST.json")))) {
  throw new Error("Built manifest differs from reviewed source");
}
for (const file of manifest.files) {
  const raw = fs.readFileSync(path.join(built, file.path));
  if (raw.length !== file.bytes || hash(raw) !== file.sha256) throw new Error(`Built evidence mismatch: ${file.path}`);
}
const articles = ["chatgpt-windows-ram-case-study", "chatgpt-browser-state-changes", "codex-cli-windows-ram"]
  .map(slug => fs.readFileSync(path.join(site, "src/content/posts", `${slug}.md`), "utf8"));
const provenance = JSON.parse(fs.readFileSync(path.join(source, "ACTUAL_SCREENSHOTS.json"), "utf8"));
const screenshotLinks = new Set(
  articles.flatMap(article => [...article.matchAll(/\/research\/chatgpt-windows-ram\/(screenshots\/[^\s)]+)/g)].map(match => match[1]))
);
const screenshotEntries = new Map();
for (const entry of provenance.screenshots) {
  if (screenshotEntries.has(entry.image)) throw new Error(`Duplicate screenshot provenance: ${entry.image}`);
  screenshotEntries.set(entry.image, entry);
  if (hash(fs.readFileSync(path.join(source, entry.image))).toLowerCase() !== entry.public_sha256.toLowerCase()) {
    throw new Error(`Screenshot provenance hash mismatch: ${entry.image}`);
  }
  if (entry.derived_from &&
      hash(fs.readFileSync(path.join(source, entry.derived_from))).toLowerCase() !==
      entry.derived_from_sha256.toLowerCase()) {
    throw new Error(`Screenshot source hash mismatch: ${entry.image}`);
  }
  if (entry.derived_from_private_original) {
    if (!/^[0-9a-f]{64}$/i.test(entry.original_sha256 ?? "") ||
        (entry.derived_from_sha256 &&
         entry.derived_from_sha256.toLowerCase() !== entry.original_sha256.toLowerCase())) {
      throw new Error(`Private screenshot source digest mismatch: ${entry.image}`);
    }
  }
}
const lowLevelFigures = JSON.parse(fs.readFileSync(path.join(source, "LOW_LEVEL_FULL_RAM_FIGURES_20261027.json"), "utf8"));
const b1B5Figures = JSON.parse(fs.readFileSync(path.join(source, "B1_B5_FIGURE_PROVENANCE_20261030.json"), "utf8"));
for (const entry of [...lowLevelFigures.published_figures, ...lowLevelFigures.derived_figures, ...lowLevelFigures.terminal_figures]) {
  if (screenshotEntries.has(entry.path)) throw new Error(`Duplicate screenshot provenance: ${entry.path}`);
  screenshotEntries.set(entry.path, entry);
  if (hash(fs.readFileSync(path.join(source, entry.path))) !== entry.sha256) {
    throw new Error(`Screenshot provenance hash mismatch: ${entry.path}`);
  }
}
for (const [image, entry] of Object.entries(b1B5Figures.published_figures)) {
  if (screenshotEntries.has(image)) throw new Error(`Duplicate screenshot provenance: ${image}`);
  screenshotEntries.set(image, entry);
  if (hash(fs.readFileSync(path.join(source, image))) !== entry.sha256) {
    throw new Error(`Screenshot provenance hash mismatch: ${image}`);
  }
}
for (const image of screenshotLinks) {
  if (!screenshotEntries.has(image)) throw new Error(`Article screenshot lacks provenance: ${image}`);
}
for (const folder of ["method_cli_core_v1", "method_cli_model_input_v1"]) {
  const freeze = JSON.parse(fs.readFileSync(path.join(source, folder, "FROZEN_METHOD.json"), "utf8"));
  for (const file of freeze.files) {
    if (hash(fs.readFileSync(path.join(source, folder, file.path))).toLowerCase() !== file.sha256) {
      throw new Error(`Frozen parser changed: ${folder}/${file.path}`);
    }
  }
}
const requestFreeze = JSON.parse(fs.readFileSync(path.join(source, "FROZEN_CLI_REQUEST_CORE_V1.json"), "utf8"));
for (const [file, expected] of Object.entries(requestFreeze.source_sha256)) {
  if (hash(fs.readFileSync(path.join(source, "method_cli_request_core_v1", file))) !== expected) {
    throw new Error(`Frozen parser changed: method_cli_request_core_v1/${file}`);
  }
}
const signedInFreeze = JSON.parse(fs.readFileSync(path.join(source, "FROZEN_SIGNEDIN_SSE_V1.json"), "utf8"));
for (const [file, expected] of Object.entries(signedInFreeze.method_files)) {
  if (hash(fs.readFileSync(path.join(source, "method_signedin_sse_v1", file))) !== expected) {
    throw new Error(`Frozen parser changed: method_signedin_sse_v1/${file}`);
  }
}
const html = slug => fs.readFileSync(path.join(site, "dist/posts", slug, "index.html"), "utf8");
if (!html("cheater-catf-2026").includes('href="/posts/chatgpt-windows-ram-case-study/"') ||
    !html("chatgpt-windows-ram-case-study").includes('href="/posts/cheater-catf-2026/"')) {
  throw new Error("Bidirectional post links missing from the built pages");
}
console.log(JSON.stringify({ built_evidence_files_match: manifest.files.length,
  article_screenshots_with_matching_provenance: screenshotLinks.size,
  registered_screenshots: screenshotEntries.size,
  registered_screenshots_not_embedded: screenshotEntries.size - screenshotLinks.size,
  frozen_methods_unchanged: 4, bidirectional_article_links: true,
  limitation: "Static integrity checks do not replace visual review or original RAM extraction." }, null, 2));
