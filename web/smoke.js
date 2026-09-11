// Proves the built page converts a real PDF, the way datarail.org/docshift will.
//
//   cd web && npm run build && npm test
//
// Runs the bundle in dist/web -- the exact files that get deployed -- on the
// same Pyodide release the page loads from jsDelivr, with the same sample PDF
// packaging/smoke_test.py feeds the desktop builds: text on two pages, an
// image, and the drawings pdf2docx can only clip with OpenCV.

import { readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { loadPyodide, version as installedPyodide } from "pyodide";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const bundle = resolve(process.argv[2] ?? join(ROOT, "dist", "web"));

function fail(message) {
  // A GitHub Actions error annotation; plain enough to read anywhere else.
  console.log(`::error title=Web smoke test failed::${message}`);
  process.exit(1);
}

const { startEngine, PYODIDE_VERSION } = await import(pathToFileURL(join(bundle, "engine.js")));
if (installedPyodide !== PYODIDE_VERSION) {
  fail(`the page loads Pyodide ${PYODIDE_VERSION} but ${installedPyodide} is installed here; ` +
    `update the version in web/package.json`);
}

const started = Date.now();
const engine = await startEngine({
  loadPyodide,
  readAsset: (path) => readFile(join(bundle, path)),
  onStatus: (status) => console.log(`engine: ${status}`),
});
console.log(`engine ready in ${((Date.now() - started) / 1000).toFixed(1)}s`);
const { pyodide } = engine;

// The sample PDF, drawn by the desktop smoke test's own make_pdf().
pyodide.FS.writeFile("/tmp/smoke_test.py", await readFile(join(ROOT, "packaging", "smoke_test.py")));
const pdf = pyodide.runPython(`
import sys
from pathlib import Path
sys.path.insert(0, "/tmp")
import smoke_test
smoke_test.make_pdf(Path("/tmp/sample.pdf"))
Path("/tmp/sample.pdf").read_bytes()
`).toJs();

const progress = [];
const converted = Date.now();
const result = engine.convert("sample.pdf", pdf, (line) => progress.push(line));
if (!result.ok) fail(`converting a real PDF failed: ${result.message}`);
if (result.name !== "sample.docx") fail(`expected sample.docx, got ${result.name}`);
if (result.pages !== 2 || result.missing_count !== 0) {
  fail(`expected 2 complete pages, got ${result.pages} with ${result.missing_count} missing`);
}

pyodide.FS.writeFile("/tmp/out.docx", result.docx);
const [hasFirst, hasSecond, images] = pyodide.runPython(`
import docx
document = docx.Document("/tmp/out.docx")
text = "\\n".join(paragraph.text for paragraph in document.paragraphs)
images = sum("image" in rel.reltype for rel in document.part.rels.values())
["Shifted by DocShift" in text, "The second page survives" in text, images]
`).toJs();
if (!hasFirst || !hasSecond) fail("text from the PDF is missing from the DOCX");
if (images < 2) fail(`expected the image plus the drawings OpenCV clips, found ${images} image(s)`);
console.log(`converted in ${((Date.now() - converted) / 1000).toFixed(1)}s: ` +
  `text from both pages, and ${images} images, ${result.docx.length} bytes`);

for (const expected of ["Opening the PDF", "Reading page 1 of 2", "Writing the DOCX", "Writing page 2 of 2"]) {
  if (!progress.includes(expected)) fail(`progress never said "${expected}"; it said: ${progress.join(" | ")}`);
}
console.log(`progress reported: ${progress.join(" > ")}`);

const refused = engine.convert("fake.pdf", new TextEncoder().encode("not a pdf"));
if (refused.ok || refused.message !== "fake.pdf is not a PDF.") {
  fail(`a file that is not a PDF was not refused properly: ${JSON.stringify(refused)}`);
}
console.log(`a file that is not a PDF is refused: "${refused.message}"`);
