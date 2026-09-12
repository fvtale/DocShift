// The Web Worker that runs DocShift's Python for the page.
//
// Pyodide lives here rather than on the page's own thread: a conversion is
// seconds of solid computation, and on the page's thread it would freeze
// scrolling, clicks and the progress line until it finished -- the same
// reason the desktop app converts on a worker thread.
//
// Messages in:   {type: "warm"}                     start loading, if not already
//                {type: "convert", name, bytes}     convert one PDF
// Messages out:  {type: "status", text}             loading or converting
//                {type: "ready"}                    the engine is loaded
//                {type: "failed-to-start", message}
//                {type: "result", ...}              see docshift_web.convert()

import { PYODIDE_URL, startEngine } from "./engine.js";

let starting = null;

function engine() {
  starting ??= (async () => {
    const { loadPyodide } = await import(`${PYODIDE_URL}pyodide.mjs`);
    return startEngine({
      loadPyodide,
      pyodideOptions: { indexURL: PYODIDE_URL },
      readAsset: async (path) => {
        const response = await fetch(new URL(path, import.meta.url));
        if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
        return new Uint8Array(await response.arrayBuffer());
      },
      onStatus: (text) => postMessage({ type: "status", text }),
    });
  })();
  return starting;
}

self.onmessage = async ({ data }) => {
  let ready;
  try {
    ready = await engine();
  } catch (error) {
    postMessage({ type: "failed-to-start", message: String(error?.message ?? error) });
    return;
  }

  if (data.type === "warm") {
    postMessage({ type: "ready" });
    return;
  }

  if (data.type === "convert") {
    try {
      const result = ready.convert(data.name, data.bytes, (text) => postMessage({ type: "status", text }));
      // Hand the converted file over rather than copying it.
      postMessage({ type: "result", ...result }, result.data ? [result.data.buffer] : []);
    } catch (error) {
      // A bug in DocShift, or the tab running out of memory on a huge PDF --
      // not a bad file, which comes back as a result with ok: false. Python
      // may be left in a broken state, so the page starts a fresh engine for
      // the next file.
      postMessage({
        type: "result",
        ok: false,
        restart: true,
        message: `Something went wrong inside DocShift: ${error?.message ?? error}`,
      });
    }
  }
};
