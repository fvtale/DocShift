// The page's side of DocShift: choosing a file, showing progress, handing
// back the DOCX. All the Python runs in worker.js; this file only talks to it.

const DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const $ = (id) => document.getElementById(id);
const ui = {
  drop: $("drop"),
  file: $("file"),
  picked: $("picked"),
  status: $("status"),
  convert: $("convert"),
  working: $("working"),
  outcome: $("outcome"),
  done: $("done"),
  download: $("download"),
  gaps: $("gaps"),
  error: $("error"),
};

// What the engine reports while it loads, as the status line says it.
const LOADING = {
  "Starting Python": "Starting the converter…",
  "Downloading the converter": "Downloading the converter (about 38 MB, first time only)…",
  "Loading the conversion engine": "Almost ready…",
};

let worker = null;
let ready = false;
let chosen = null; // the File to convert
let busy = false; // converting, or waiting on the engine so it can
let waiting = false; // Convert was pressed before the engine was ready
let downloadUrl = null;

function say(text) {
  ui.status.textContent = text;
}

function setBusy(on) {
  busy = on;
  ui.working.hidden = !on;
  ui.convert.disabled = on || !chosen;
  ui.file.disabled = on;
  ui.drop.classList.toggle("locked", on);
}

function clearOutcome() {
  ui.outcome.hidden = true;
  ui.done.hidden = true;
  ui.gaps.hidden = true;
  ui.error.hidden = true;
  if (downloadUrl) {
    URL.revokeObjectURL(downloadUrl);
    downloadUrl = null;
  }
}

function showError(text) {
  ui.outcome.hidden = false;
  ui.error.textContent = text;
  ui.error.hidden = false;
}

function size(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// The same test as check_pdf() in docshift/core/convert.py: a PDF header in
// the first kilobyte, whatever the file is called.
async function looksLikePdf(file) {
  const head = new Uint8Array(await file.slice(0, 1024).arrayBuffer());
  return new TextDecoder("latin1").decode(head).includes("%PDF-");
}

function startWorker() {
  if (worker) return;
  worker = new Worker(new URL("worker.js", import.meta.url), { type: "module" });
  worker.onmessage = ({ data }) => receive(data);
  worker.onerror = (event) => {
    event.preventDefault();
    stopped(event.message || "its script could not be loaded");
  };
  worker.postMessage({ type: "warm" });
}

// Throws the engine away, so the next conversion starts a fresh one.
function resetWorker() {
  worker?.terminate();
  worker = null;
  ready = false;
  waiting = false;
}

function receive(message) {
  switch (message.type) {
    case "status":
      say(LOADING[message.text] ?? `${message.text}…`);
      break;
    case "ready":
      ready = true;
      if (waiting) {
        waiting = false;
        send();
      } else if (chosen && !busy) {
        say(`Ready to convert ${chosen.name}.`);
      }
      break;
    case "failed-to-start":
      stopped(message.message);
      break;
    case "result":
      finish(message);
      break;
  }
}

async function send() {
  const file = chosen;
  say(`Converting ${file.name}…`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  worker.postMessage({ type: "convert", name: file.name, bytes }, [bytes.buffer]);
}

function finish(result) {
  setBusy(false);
  if (result.restart) resetWorker();
  if (!result.ok) {
    say("Conversion failed.");
    showError(result.message);
    return;
  }

  downloadUrl = URL.createObjectURL(new Blob([result.docx], { type: DOCX_TYPE }));
  ui.download.href = downloadUrl;
  ui.download.download = result.name;
  ui.download.textContent = `Download ${result.name}`;
  ui.outcome.hidden = false;
  ui.done.hidden = false;
  say(`Done: ${result.name}, ${result.pages} page${result.pages === 1 ? "" : "s"}.`);

  if (result.missing_count) {
    const missing = result.missing.charAt(0).toUpperCase() + result.missing.slice(1);
    const verb = result.missing_count === 1 ? "is" : "are";
    ui.gaps.textContent = `${missing} could not be converted and ${verb} missing from the DOCX.`;
    ui.gaps.hidden = false;
  }
  ui.download.focus();
}

// The engine could not load, or died under it.
function stopped(reason) {
  const hadStarted = ready;
  resetWorker();
  setBusy(false);
  if (hadStarted) {
    say("Conversion failed.");
    showError(
      `The converter stopped: ${reason}. A very large PDF can use more memory ` +
        `than a browser tab is allowed; DocShift for Windows has no such limit.`,
    );
  } else {
    say("The converter could not load.");
    showError(
      `The converter could not load: ${reason}. Check your connection and try ` +
        `again, or use DocShift for Windows, which works offline.`,
    );
  }
}

async function choose(file) {
  if (!file || busy) return;
  clearOutcome();
  chosen = null;
  ui.convert.disabled = true;
  ui.picked.textContent = `${file.name} · ${size(file.size)}`;
  ui.picked.hidden = false;

  // Refused here, before the converter downloads for nothing.
  if (!(await looksLikePdf(file))) {
    say("That file is not a PDF.");
    showError(`${file.name} is not a PDF.`);
    return;
  }

  chosen = file;
  ui.convert.disabled = false;
  // Start loading now, while they reach for the button.
  startWorker();
  say(ready ? `Ready to convert ${file.name}.` : "Loading the converter…");
}

ui.convert.addEventListener("click", () => {
  if (!chosen || busy) return;
  clearOutcome();
  setBusy(true);
  startWorker();
  if (ready) {
    send();
  } else {
    waiting = true;
    say("Loading the converter…");
  }
});

ui.file.addEventListener("change", () => {
  const file = ui.file.files[0];
  // Cleared so that choosing the same file again still counts as a change.
  ui.file.value = "";
  choose(file);
});

// A PDF dropped anywhere on the page is taken, rather than the browser
// navigating away to display it and losing the page.
for (const type of ["dragenter", "dragover"]) {
  window.addEventListener(type, (event) => {
    event.preventDefault();
    if (!busy) ui.drop.classList.add("over");
  });
}
window.addEventListener("dragleave", (event) => {
  if (!event.relatedTarget) ui.drop.classList.remove("over");
});
window.addEventListener("drop", (event) => {
  event.preventDefault();
  ui.drop.classList.remove("over");
  choose(event.dataTransfer?.files?.[0]);
});

// Leaving mid-conversion throws the work away. Ask first, as the desktop app
// does when its window is closed partway through.
window.addEventListener("beforeunload", (event) => {
  if (busy) event.preventDefault();
});

if (typeof WebAssembly !== "object" || typeof Worker !== "function") {
  ui.file.disabled = true;
  ui.drop.classList.add("locked");
  showError(
    "This browser cannot run the converter: it needs WebAssembly and Web Workers, " +
      "which every current browser has.",
  );
}
