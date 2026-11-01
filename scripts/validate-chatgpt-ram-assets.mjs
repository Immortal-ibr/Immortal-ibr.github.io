// Integrity/type checks are safeguards, not proof of a complete privacy audit.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { fileURLToPath } from "node:url";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const root = path.join(site, "public/research/chatgpt-windows-ram");
const hash = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");
const sameDigest = (bytes, expected) => hash(bytes).toUpperCase() === String(expected).toUpperCase();
const manifest = JSON.parse(fs.readFileSync(path.join(root, "ASSET_MANIFEST.json"), "utf8"));
const allowed = new Set([".md", ".json", ".py", ".ps1", ".txt", ".png", ".jpg", ".jpeg", ".bin"]);
const listed = new Set(manifest.files.map((entry) => entry.path));
if (listed.size !== manifest.files.length || listed.has("ASSET_MANIFEST.json")) {
  throw new Error("Duplicate or self-inventoried manifest entry");
}
function allFiles(directory, relative = "") {
  const result = [];
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const nextRelative = relative ? `${relative}/${item.name}` : item.name;
    const nextPath = path.join(directory, item.name);
    if (item.isSymbolicLink()) throw new Error(`Symlink in public evidence: ${nextRelative}`);
    if (item.isDirectory()) result.push(...allFiles(nextPath, nextRelative));
    else if (item.isFile()) result.push(nextRelative);
    else throw new Error(`Unexpected public asset type: ${nextRelative}`);
  }
  return result;
}
const actual = new Set(allFiles(root).filter((name) => name !== "ASSET_MANIFEST.json"));
for (const name of actual) if (!listed.has(name)) throw new Error(`Unreviewed public asset: ${name}`);
for (const name of listed) if (!actual.has(name)) throw new Error(`Inventoried public asset missing: ${name}`);
for (const entry of manifest.files) {
  const target = path.resolve(root, entry.path);
  if (!target.startsWith(root + path.sep)) throw new Error("Escaping asset path");
  if (!allowed.has(path.extname(target).toLowerCase())) throw new Error(`Unexpected public file type: ${entry.path}`);
  const bytes = fs.readFileSync(target);
  if (bytes.length > 10_000_000) throw new Error(`Unexpected large public file: ${entry.path}`);
  if (bytes.length !== entry.bytes || hash(bytes).toUpperCase() !== entry.sha256) throw new Error(`Manifest mismatch: ${entry.path}`);
}

const provenance = JSON.parse(fs.readFileSync(path.join(root, "ACTUAL_SCREENSHOTS.json"), "utf8"));
let privateOriginals = 0;
for (const shot of provenance.screenshots) {
  const bytes = fs.readFileSync(path.join(root, shot.image));
  if (!sameDigest(bytes, shot.public_sha256)) throw new Error(`Screenshot mismatch: ${shot.image}`);
  if (shot.source_data_scope === "private_original") {
    if (!/^[0-9a-f]{64}$/i.test(shot.original_sha256 ?? "")) throw new Error(`Missing original digest: ${shot.image}`);
    if (shot.source_sha256 && !/^[0-9a-f]{64}$/i.test(shot.source_sha256)) throw new Error(`Invalid private source digest: ${shot.image}`);
    privateOriginals++;
  } else {
    if (shot.source_data_scope && shot.source_data_scope !== "public_file") throw new Error(`Unknown source scope: ${shot.image}`);
    const source = path.resolve(root, shot.source_data);
    if (!source.startsWith(root + path.sep)) throw new Error(`Escaping screenshot source: ${shot.image}`);
    if (!sameDigest(fs.readFileSync(source), shot.source_sha256)) throw new Error(`Source mismatch: ${shot.source_data}`);
  }
  const metadata = await sharp(bytes).metadata();
  if (metadata.width !== shot.width || metadata.height !== shot.height) throw new Error(`Screenshot dimensions changed: ${shot.image}`);
  if (shot.derived_from) {
    const original = fs.readFileSync(path.join(root, shot.derived_from));
    if (!sameDigest(original, shot.derived_from_sha256)) throw new Error(`Crop source changed: ${shot.image}`);
    const expected = await sharp(original).extract(shot.crop).ensureAlpha().raw().toBuffer();
    const actual = await sharp(bytes).ensureAlpha().raw().toBuffer();
    if (!actual.equals(expected)) throw new Error(`Crop is not an exact pixel extraction: ${shot.image}`);
  }
  if (shot.derived_from_private_original) {
    if (shot.derived_from || !/^[0-9a-f]{64}$/i.test(shot.derived_from_sha256 ?? "")) {
      throw new Error(`Invalid private crop provenance: ${shot.image}`);
    }
    if (shot.derived_from_sha256.toUpperCase() !== shot.original_sha256?.toUpperCase()) {
      throw new Error(`Private crop source digest changed: ${shot.image}`);
    }
  }
  if (shot.input_public_file) {
    const input = path.resolve(root, shot.input_public_file);
    if (!input.startsWith(root + path.sep) || !sameDigest(fs.readFileSync(input), shot.input_public_sha256)) {
      throw new Error(`Terminal input file changed: ${shot.image}`);
    }
  }
}

const article = fs.readFileSync(path.join(site, "src/content/posts/chatgpt-windows-ram-case-study.md"), "utf8");
const links = [...article.matchAll(/\]\((\/research\/chatgpt-windows-ram\/[^)]+)\)/g)].map((m) => m[1]);
const cover = article.match(/^image:\s*(\/research\/chatgpt-windows-ram\/\S+)/m)?.[1];
if (cover) links.push(cover);
for (const link of new Set(links)) {
  const target = path.join(site, "public", link.split("#")[0]);
  if (!fs.statSync(target).isFile()) throw new Error(`Missing linked asset: ${link}`);
}
console.log(JSON.stringify({
  manifest_files_checked: manifest.files.length,
  actual_screenshot_assets_checked: provenance.screenshots.length,
  private_originals_not_reverified: privateOriginals,
  distinct_capture_originals: new Set(provenance.screenshots.map(shot => shot.original_sha256)).size,
  research_asset_links_checked: new Set(links).size,
  limitation: "Integrity, bounds and file types do not establish a complete privacy review or RAM extraction provenance.",
}, null, 2));
