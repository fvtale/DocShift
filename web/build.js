// Stages dist/web/: exactly the folder that becomes datarail.org/docshift.
//
//   cd web && npm run build
//
// Copies the page, packs DocShift's Python into engine.json, and downloads
// the two pure-Python wheels the converter needs from PyPI, checking each one
// against the SHA-256 PyPI publishes for it. CI runs this, smoke-tests the
// result, and uploads it as the DocShift-web artifact.

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { PYODIDE_VERSION } from "./engine.js";

const WEB = dirname(fileURLToPath(import.meta.url));
const ROOT = join(WEB, "..");
const OUT = join(ROOT, "dist", "web");

// Exact versions, not ranges: what deploys must be what CI tested. pdf2docx
// matches the floor in requirements.txt; python-docx is the one it installs
// alongside today.
const WHEELS = { "pdf2docx": "0.5.13", "python-docx": "1.2.0" };

const PAGE = ["index.html", "app.js", "worker.js", "engine.js", ".htaccess"];

// The engine, unchanged from the desktop app, plus the browser's glue.
const PYTHON = {
  "docshift/__init__.py": join(ROOT, "docshift", "__init__.py"),
  "docshift/core/__init__.py": join(ROOT, "docshift", "core", "__init__.py"),
  "docshift/core/convert.py": join(ROOT, "docshift", "core", "convert.py"),
  "docshift_web.py": join(WEB, "docshift_web.py"),
};

async function copy(from, to) {
  await mkdir(dirname(to), { recursive: true });
  await copyFile(from, to);
}

async function wheel(name, version) {
  const response = await fetch(`https://pypi.org/pypi/${name}/${version}/json`);
  if (!response.ok) throw new Error(`PyPI has no ${name} ${version} (HTTP ${response.status})`);
  const file = (await response.json()).urls.find((url) => url.filename.endsWith("-py3-none-any.whl"));
  if (!file) throw new Error(`${name} ${version} has no pure-Python wheel on PyPI`);

  const bytes = Buffer.from(await (await fetch(file.url)).arrayBuffer());
  const digest = createHash("sha256").update(bytes).digest("hex");
  if (digest !== file.digests.sha256) {
    throw new Error(`${file.filename} does not match the SHA-256 PyPI publishes for it`);
  }
  return { filename: file.filename, bytes };
}

function commit() {
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA;
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT }).toString().trim();
  } catch {
    return "unknown";
  }
}

await rm(OUT, { recursive: true, force: true });

for (const file of PAGE) await copy(join(WEB, file), join(OUT, file));
await copy(join(ROOT, "docshift", "gui", "docshift.ico"), join(OUT, "favicon.ico"));

const wheels = [];
for (const [name, version] of Object.entries(WHEELS)) {
  const { filename, bytes } = await wheel(name, version);
  await mkdir(join(OUT, "wheels"), { recursive: true });
  await writeFile(join(OUT, "wheels", filename), bytes);
  wheels.push(filename);
}

const python = {};
for (const [path, source] of Object.entries(PYTHON)) python[path] = await readFile(source, "utf8");

const init = python["docshift/__init__.py"];
const manifest = {
  docshift: init.match(/__version__ = "([^"]+)"/)[1],
  commit: commit(),
  pyodide: PYODIDE_VERSION,
  wheels,
  python,
};
await writeFile(join(OUT, "engine.json"), JSON.stringify(manifest, null, 2) + "\n");

console.log(`dist/web: DocShift ${manifest.docshift} at ${manifest.commit.slice(0, 7)}, Pyodide ${PYODIDE_VERSION}`);
for (const filename of wheels) console.log(`  wheels/${filename}`);
