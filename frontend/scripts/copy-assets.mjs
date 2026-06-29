// Copy non-TS renderer assets into dist/ after tsc. (tsc only emits .js.)
import { cpSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const copies = [["src/renderer/index.html", "dist/renderer/index.html"]];

for (const [from, to] of copies) {
  mkdirSync(dirname(to), { recursive: true });
  cpSync(from, to);
}
console.log("copied assets:", copies.map(([, to]) => to).join(", "));
