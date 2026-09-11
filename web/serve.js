// Serves the built page locally the way datarail.org will: dist/web at
// /docshift/, and everything else -- the site's shared /assets/circuit.css and
// circuit.js above all -- fetched from the live site, so the header, rails and
// colours look exactly as they will once deployed.
//
//   cd web && npm run build && npm run serve    ->  http://localhost:8765/docshift/

import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("../dist/web/", import.meta.url)));
const PORT = Number(process.argv[2] ?? 8765);
const SITE = "https://datarail.org";
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".ico": "image/x-icon",
  ".whl": "application/octet-stream",
};

createServer(async (request, response) => {
  const url = new URL(request.url, "http://localhost");
  try {
    if (url.pathname === "/" || url.pathname === "/docshift") {
      response.writeHead(302, { location: "/docshift/" }).end();
      return;
    }
    if (url.pathname.startsWith("/docshift/")) {
      const path = decodeURIComponent(url.pathname.slice("/docshift/".length)) || "index.html";
      const file = normalize(join(ROOT, path));
      if (!file.startsWith(ROOT + sep)) {
        response.writeHead(403).end();
        return;
      }
      const body = await readFile(file);
      response
        .writeHead(200, {
          "content-type": TYPES[extname(file)] ?? "application/octet-stream",
          "cache-control": "no-cache",
        })
        .end(body);
      return;
    }
    const upstream = await fetch(SITE + url.pathname + url.search);
    response
      .writeHead(upstream.status, {
        "content-type": upstream.headers.get("content-type") ?? "application/octet-stream",
      })
      .end(Buffer.from(await upstream.arrayBuffer()));
  } catch (error) {
    response.writeHead(error.code === "ENOENT" ? 404 : 500).end(String(error.message));
  }
}).listen(PORT, () => console.log(`DocShift at http://localhost:${PORT}/docshift/`));
