import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const evidenceRoot = path.join(
  path.resolve(scriptDir, ".."),
  "public",
  "research",
  "chatgpt-windows-ram",
);
const manifestName = "ASSET_MANIFEST.json";

function listFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) return listFiles(absolute);
    if (!entry.isFile()) return [];
    return [absolute];
  });
}

const files = listFiles(evidenceRoot)
  .filter((absolute) => path.basename(absolute) !== manifestName)
  .map((absolute) => {
    const contents = fs.readFileSync(absolute);
    return {
      path: path.relative(evidenceRoot, absolute).split(path.sep).join("/"),
      bytes: contents.byteLength,
      sha256: crypto.createHash("sha256").update(contents).digest("hex").toUpperCase(),
    };
  })
  .sort((left, right) => left.path.localeCompare(right.path, "en"));

fs.writeFileSync(
  path.join(evidenceRoot, manifestName),
  `${JSON.stringify({ files }, null, 2)}\n`,
  "utf8",
);

console.log(`Recorded ${files.length} public evidence files.`);
