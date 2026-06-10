/* app.js — UI wiring for the gurmukhifix demo. SPDX-License-Identifier: MIT */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const SF = window.GurmukhiFix;

  // Example inputs per script: a few "messy OCR" strings plus a clean one.
  const EXAMPLES = {
    gurmukhi: [
      { label: "Sihari error", text: "ਿਸੱਖ ਧਰਮ" },
      { label: "Nukta order", text: "ਖਾ਼ਸ ਗੱਲ" },
      { label: "Already clean", text: "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ" },
    ],
    punjabi: [
      { label: "Sihari error", text: "ਿਕਸਾਨ ਵਰਗ" },
      { label: "Nukta order", text: "ਭਾਸਾ਼ ਬੋਲੀ" },
      { label: "Already clean", text: "ਪੰਜਾਬੀ ਮਾਂ ਬੋਲੀ" },
    ],
    devanagari: [
      { label: "Already clean", text: "नमस्ते दुनिया" },
      { label: "Vowel at start", text: "ाकमल देश" },
      { label: "Hindi phrase", text: "हिंदी भाषा" },
    ],
  };

  // Tesseract language codes for the experimental image mode.
  const TESS_LANG = { gurmukhi: "pan", punjabi: "pan", devanagari: "hin" };

  const SEV_NAME = { 100: "reject", 10: "warn", 1: "review" };

  let currentScript = "gurmukhi";

  // ── Setup script selector + examples ───────────────────────────────────────
  function initSelector() {
    const sel = $("script-select");
    Object.entries(SF.SCRIPTS).forEach(([key, s]) => {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = s.label;
      sel.appendChild(opt);
    });
    sel.value = currentScript;
    sel.addEventListener("change", () => {
      currentScript = sel.value;
      renderExamples();
      $("input").value = SF.SCRIPTS[currentScript].sample;
      run();
    });
  }

  function renderExamples() {
    const box = $("examples");
    box.innerHTML = "";
    (EXAMPLES[currentScript] || []).forEach((ex) => {
      const chip = document.createElement("button");
      chip.className = "chip";
      chip.type = "button";
      chip.textContent = ex.label;
      chip.addEventListener("click", () => {
        $("input").value = ex.text;
        run();
      });
      box.appendChild(chip);
    });
  }

  // ── Core run ───────────────────────────────────────────────────────────────
  function run() {
    const input = $("input").value;
    let result;
    try {
      result = SF.correct(input, currentScript);
    } catch (e) {
      $("output").textContent = "";
      return;
    }
    $("output").textContent = result.output;
    renderReport(result);
  }

  function renderReport(r) {
    const box = $("report");
    if (!r.input.trim()) { box.innerHTML = ""; return; }

    const changed = r.changes.length > 0;
    const cls = changed ? "ok" : (r.after.badness > 0 ? "warn" : "clean");
    const headline = changed
      ? `${r.changes.length} correction${r.changes.length > 1 ? "s" : ""} applied`
      : (r.after.badness > 0 ? "No confident fix — flagged for review" : "Already clean — no changes needed");

    let html = `<div class="report-head ${cls}"><span class="dot"></span>${headline}</div>`;

    html += `<div class="metrics">
      <div class="metric"><span>Validity badness</span><b>${r.before.badness} → ${r.after.badness}</b></div>
      <div class="metric"><span>Characters</span><b>${Array.from(r.output).length}</b></div>
    </div>`;

    if (changed) {
      html += '<div class="changes"><h4>Corrections</h4><ul>';
      r.changes.forEach((c) => {
        html += `<li><code class="from">${esc(c.from)}</code><span class="ar">→</span><code class="to">${esc(c.to)}</code><span class="rule">${esc(c.rule)}</span></li>`;
      });
      html += "</ul></div>";
    }

    const vios = r.after.violations;
    if (vios.length) {
      html += '<div class="violations"><h4>Remaining flags</h4><div class="vchips">';
      vios.forEach((v) => {
        html += `<span class="vchip ${SEV_NAME[v.sev] || "review"}">${esc(v.label)}</span>`;
      });
      html += "</div></div>";
    }

    box.innerHTML = html;
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  // ── Copy buttons ───────────────────────────────────────────────────────────
  function initCopy() {
    $("copy-btn").addEventListener("click", () => copyText($("output").textContent, $("copy-btn")));
    document.querySelectorAll(".copy-btn[data-copy]").forEach((btn) => {
      btn.addEventListener("click", () => copyText(btn.getAttribute("data-copy"), btn));
    });
  }
  function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      const old = btn.textContent;
      btn.textContent = "Copied ✓";
      setTimeout(() => (btn.textContent = old), 1400);
    }).catch(() => {});
  }

  // ── Experimental Tesseract.js image OCR ────────────────────────────────────
  let tesseractLoaded = false;
  function loadTesseract() {
    return new Promise((resolve, reject) => {
      if (tesseractLoaded && window.Tesseract) return resolve();
      const sc = document.createElement("script");
      sc.src = "https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js";
      sc.onload = () => { tesseractLoaded = true; resolve(); };
      sc.onerror = () => reject(new Error("Failed to load Tesseract.js"));
      document.head.appendChild(sc);
    });
  }

  function initOcr() {
    $("ocr-toggle").addEventListener("click", () => {
      const panel = $("ocr-panel");
      panel.hidden = !panel.hidden;
    });
    const file = $("ocr-file");
    const runBtn = $("ocr-run");
    file.addEventListener("change", () => { runBtn.disabled = !file.files.length; });
    runBtn.addEventListener("click", async () => {
      if (!file.files.length) return;
      const status = $("ocr-status");
      const lang = TESS_LANG[currentScript] || "eng";
      runBtn.disabled = true;
      status.textContent = "Loading OCR engine…";
      try {
        await loadTesseract();
        status.textContent = `Recognising (${lang})…`;
        const { data } = await window.Tesseract.recognize(file.files[0], lang, {
          logger: (m) => {
            if (m.status === "recognizing text") {
              status.textContent = `Recognising… ${Math.round(m.progress * 100)}%`;
            }
          },
        });
        $("input").value = (data.text || "").trim();
        run();
        status.textContent = "Done — cleaned by gurmukhifix below.";
      } catch (e) {
        status.textContent = "OCR failed: " + e.message;
      } finally {
        runBtn.disabled = false;
      }
    });
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    // Preselect a script from ?script= (used by the per-script pages).
    const wanted = new URLSearchParams(location.search).get("script");
    if (wanted && SF.SCRIPTS[wanted]) currentScript = wanted;
    initSelector();
    renderExamples();
    initCopy();
    initOcr();
    $("input").value = SF.SCRIPTS[currentScript].sample;
    let t;
    $("input").addEventListener("input", () => { clearTimeout(t); t = setTimeout(run, 120); });
    run();
  });
})();
