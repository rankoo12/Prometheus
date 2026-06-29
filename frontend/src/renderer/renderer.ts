// No imports/exports here on purpose: this compiles to a plain browser script.
// Types for window.prometheus come from the ambient global.d.ts.

const pickBtn = document.getElementById("pick") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLParagraphElement;
const outputEl = document.getElementById("output") as HTMLPreElement;

pickBtn.addEventListener("click", async () => {
  statusEl.textContent = "Selecting clip…";
  outputEl.textContent = "";
  try {
    const clipPath = await window.prometheus.pickClip();
    if (!clipPath) {
      statusEl.textContent = "Cancelled.";
      return;
    }
    statusEl.textContent = `Probing ${clipPath} …`;
    const info = await window.prometheus.probe(clipPath);
    statusEl.textContent = "probe() round-trip OK ✓";
    outputEl.textContent = JSON.stringify(info, null, 2);
  } catch (err) {
    statusEl.textContent = "Error";
    outputEl.textContent = err instanceof Error ? err.message : String(err);
  }
});
