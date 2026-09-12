// Boots DocShift's Python and runs conversions.
//
// Shared by the page's Web Worker on datarail.org/docshift and by CI's smoke
// test in Node, so nothing here touches the DOM. The caller supplies Pyodide's
// loadPyodide() and a way to read the page's own files; everything else is the
// same in both places.

// One pin for the whole web build. build.js stamps it into engine.json and
// smoke.js refuses to run against any other release, so CI always tests the
// Python the page actually loads.
export const PYODIDE_VERSION = "314.0.6";
export const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

// Pyodide's own builds of pdf2docx's compiled dependencies, fetched from
// jsDelivr: about 38 MB on the first visit, then cached by the browser.
// pdf2docx and python-docx are plain Python and ship beside this file.
const PACKAGES = [
  "micropip",
  "numpy",
  "opencv-python",
  "pymupdf",
  "lxml",
  "fonttools",
  "typing-extensions",
];

export async function startEngine({
  loadPyodide,
  readAsset,
  pyodideOptions = {},
  onStatus = () => {},
}) {
  const manifest = JSON.parse(new TextDecoder().decode(await readAsset("engine.json")));

  onStatus("Starting Python");
  const pyodide = await loadPyodide(pyodideOptions);
  if (pyodide.version !== PYODIDE_VERSION) {
    throw new Error(`expected Pyodide ${PYODIDE_VERSION}, loaded ${pyodide.version}`);
  }

  onStatus("Downloading the converter");
  await pyodide.loadPackage(PACKAGES, { messageCallback: () => {} });

  pyodide.FS.mkdirTree("/tmp/wheels");
  for (const wheel of manifest.wheels) {
    pyodide.FS.writeFile(`/tmp/wheels/${wheel}`, await readAsset(`wheels/${wheel}`));
  }
  const micropip = pyodide.pyimport("micropip");
  // Without their dependencies: pdf2docx asks for opencv-python-headless,
  // which Pyodide ships as opencv-python, and for fire, which only its own
  // command line uses. Everything it does need is loaded above. (callKwargs:
  // a plain JS object passed to Python arrives as one positional argument.)
  await micropip.install.callKwargs(
    manifest.wheels.map((wheel) => `emfs:/tmp/wheels/${wheel}`),
    { deps: false },
  );
  micropip.destroy();

  // DocShift's own Python arrives inside engine.json rather than as .py files
  // on the server, where a web host may try to run them instead of serving them.
  const site = pyodide.runPython("import sysconfig; sysconfig.get_paths()['purelib']");
  for (const [path, source] of Object.entries(manifest.python)) {
    const target = `${site}/${path}`;
    pyodide.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    pyodide.FS.writeFile(target, source);
  }

  onStatus("Loading the conversion engine");
  const web = pyodide.pyimport("docshift_web");
  // Load both engines -- pdf2docx with NumPy, OpenCV and MuPDF behind it, and
  // the Word reader -- now rather than on the first conversion, which should
  // start the moment someone presses Convert.
  pyodide.runPython(
    "from docshift.core.pdf_to_docx import _load_engine; _load_engine()\n" +
      "import docshift.core.docx_to_pdf\n",
  );

  return {
    manifest,
    pyodide,

    // Runs synchronously inside Python. In the browser that is the worker's
    // thread, never the page's, so the page stays responsive throughout.
    convert(name, bytes, onProgress = () => {}) {
      const result = web.convert_bytes(name, bytes, onProgress);
      try {
        return result.toJs({ dict_converter: Object.fromEntries });
      } finally {
        result.destroy();
      }
    },
  };
}
