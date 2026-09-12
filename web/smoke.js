// Proves the built page converts real files, both ways, as datarail.org/docshift will.
//
//   cd web && npm run build && npm test
//
// Runs the bundle in dist/web -- the exact files that get deployed -- on the
// same Pyodide release the page loads from jsDelivr, with the same samples
// packaging/smoke_test.py feeds the desktop builds: a PDF with text on two
// pages, an image and the drawings pdf2docx can only clip with OpenCV, and a
// Word document with a heading, a list, a table and a picture.

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

// Both samples come from the desktop smoke test, so the page and the .exe are
// held to the same documents.
pyodide.FS.writeFile("/tmp/smoke_test.py", await readFile(join(ROOT, "packaging", "smoke_test.py")));
const [pdf, docx] = pyodide.runPython(`
import sys
from pathlib import Path
sys.path.insert(0, "/tmp")
import smoke_test
smoke_test.make_pdf(Path("/tmp/sample.pdf"))
smoke_test.make_docx(Path("/tmp/letter.docx"))
[Path("/tmp/sample.pdf").read_bytes(), Path("/tmp/letter.docx").read_bytes()]
`).toJs();

// -- PDF to DOCX --------------------------------------------------------------

const progress = [];
let clock = Date.now();
const toDocx = engine.convert("sample.pdf", pdf, (line) => progress.push(line));
if (!toDocx.ok) fail(`converting a real PDF failed: ${toDocx.message}`);
if (toDocx.name !== "sample.docx") fail(`expected sample.docx, got ${toDocx.name}`);
if (toDocx.pages !== 2 || toDocx.missing_count !== 0) {
  fail(`expected 2 complete pages, got ${toDocx.pages} with ${toDocx.missing_count} missing`);
}

pyodide.FS.writeFile("/tmp/out.docx", toDocx.data);
const [hasFirst, hasSecond, images] = pyodide.runPython(`
import docx
document = docx.Document("/tmp/out.docx")
text = "\\n".join(paragraph.text for paragraph in document.paragraphs)
images = sum("image" in rel.reltype for rel in document.part.rels.values())
["Shifted by DocShift" in text, "The second page survives" in text, images]
`).toJs();
if (!hasFirst || !hasSecond) fail("text from the PDF is missing from the DOCX");
if (images < 2) fail(`expected the image plus the drawings OpenCV clips, found ${images} image(s)`);
console.log(`PDF to DOCX in ${((Date.now() - clock) / 1000).toFixed(1)}s: ` +
  `text from both pages, and ${images} images, ${toDocx.data.length} bytes`);

for (const expected of ["Opening the PDF", "Reading page 1 of 2", "Writing the DOCX"]) {
  if (!progress.includes(expected)) fail(`progress never said "${expected}": ${progress.join(" | ")}`);
}
console.log(`progress reported: ${progress.join(" > ")}`);

// -- DOCX to PDF --------------------------------------------------------------

clock = Date.now();
const toPdf = engine.convert("letter.docx", docx);
if (!toPdf.ok) fail(`converting a real Word document failed: ${toPdf.message}`);
if (toPdf.name !== "letter.pdf") fail(`expected letter.pdf, got ${toPdf.name}`);
if (toPdf.kind !== "pdf") fail(`expected a pdf, got ${toPdf.kind}`);

pyodide.FS.writeFile("/tmp/out.pdf", toPdf.data);
const [drawn, pictures] = pyodide.runPython(`
import pymupdf
with pymupdf.open("/tmp/out.pdf") as document:
    text = " ".join(" ".join(page.get_text().split()) for page in document)
    pictures = sum(len(page.get_images()) for page in document)
[text, pictures]
`).toJs();
for (const line of ["Shifted by DocShift", "The second paragraph survives", "New York"]) {
  if (!drawn.includes(line)) fail(`"${line}" is missing from the PDF`);
}
if (!pictures) fail("the picture is missing from the PDF");
console.log(`DOCX to PDF in ${((Date.now() - clock) / 1000).toFixed(1)}s: ` +
  `its text, its table, and ${pictures} picture(s), ${toPdf.data.length} bytes`);

// -- what it refuses ----------------------------------------------------------

const refused = engine.convert("notes.pdf", new TextEncoder().encode("not a pdf"));
if (refused.ok || refused.message !== "notes.pdf is not a PDF or a Word document.") {
  fail(`a file that is neither was not refused properly: ${JSON.stringify(refused)}`);
}
console.log(`a file that is neither is refused: "${refused.message}"`);
