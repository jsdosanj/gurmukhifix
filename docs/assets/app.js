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
    hindi: [
      { label: "I-matra error", text: "िकताब पढ़ना" },
      { label: "Already clean", text: "नमस्ते दुनिया" },
      { label: "Hindi phrase", text: "हिंदी भाषा" },
    ],
    devanagari: [
      { label: "I-matra error", text: "िकताब" },
      { label: "Vowel at start", text: "ाकमल देश" },
      { label: "Already clean", text: "मराठी भाषा" },
    ],
  };

  // Tesseract language codes for the image/PDF-scan OCR mode.
  const TESS_LANG = { gurmukhi: "pan", punjabi: "pan", hindi: "hin", devanagari: "hin" };

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

  // Build a DOM element with class + text/children. Using textContent (never
  // innerHTML) means OCR/clipboard text can never inject markup — no XSS.
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function renderReport(r) {
    const box = $("report");
    box.replaceChildren();
    if (!r.input.trim()) return;

    const changed = r.changes.length > 0;
    const cls = changed ? "ok" : (r.after.badness > 0 ? "warn" : "clean");
    const headline = changed
      ? `${r.changes.length} correction${r.changes.length > 1 ? "s" : ""} applied`
      : (r.after.badness > 0 ? "No confident fix — flagged for review" : "Already clean — no changes needed");

    const head = el("div", `report-head ${cls}`);
    head.appendChild(el("span", "dot"));
    head.appendChild(document.createTextNode(headline));
    box.appendChild(head);

    const metrics = el("div", "metrics");
    const m1 = el("div", "metric");
    m1.appendChild(el("span", null, "Validity badness"));
    m1.appendChild(el("b", null, `${r.before.badness} → ${r.after.badness}`));
    const m2 = el("div", "metric");
    m2.appendChild(el("span", null, "Characters"));
    m2.appendChild(el("b", null, String(Array.from(r.output).length)));
    metrics.append(m1, m2);
    box.appendChild(metrics);

    if (changed) {
      const wrap = el("div", "changes");
      wrap.appendChild(el("h4", null, "Corrections"));
      const ul = el("ul");
      r.changes.forEach((c) => {
        const li = el("li");
        li.appendChild(el("code", "from", c.from));
        li.appendChild(el("span", "ar", "→"));
        li.appendChild(el("code", "to", c.to));
        li.appendChild(el("span", "rule", c.rule));
        ul.appendChild(li);
      });
      wrap.appendChild(ul);
      box.appendChild(wrap);
    }

    if (r.after.violations.length) {
      const wrap = el("div", "violations");
      wrap.appendChild(el("h4", null, "Remaining flags"));
      const chips = el("div", "vchips");
      r.after.violations.forEach((v) => {
        chips.appendChild(el("span", `vchip ${SEV_NAME[v.sev] || "review"}`, v.label));
      });
      wrap.appendChild(chips);
      box.appendChild(wrap);
    }
  }

  // ── Copy + download ────────────────────────────────────────────────────────
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
  function initDownload() {
    const btn = $("download-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      const text = $("output").textContent || "";
      if (!text.trim()) return;
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `gurmukhifix-${currentScript}.txt`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
  }

  // ── CDN loaders (pinned + Subresource Integrity: a tampered CDN file is
  //    refused by the browser). Both engines run entirely client-side. ─────────
  let tesseractLoaded = false;
  function loadTesseract() {
    return new Promise((resolve, reject) => {
      if (tesseractLoaded && window.Tesseract) return resolve();
      const sc = document.createElement("script");
      sc.src = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
      sc.integrity = "sha384-GJqSu7vueQ9qN0E9yLPb3Wtpd7OrgK8KmYzC8T1IysG1bcvxvIO4qtYR/D3A991F";
      sc.crossOrigin = "anonymous";
      sc.onload = () => { tesseractLoaded = true; resolve(); };
      sc.onerror = () => reject(new Error("Failed to load Tesseract.js"));
      document.head.appendChild(sc);
    });
  }

  const PDFJS_BASE = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/legacy/build/";
  let pdfjsLoaded = false;
  function loadPdfjs() {
    return new Promise((resolve, reject) => {
      if (pdfjsLoaded && window.pdfjsLib) return resolve(window.pdfjsLib);
      const sc = document.createElement("script");
      sc.src = PDFJS_BASE + "pdf.min.js";
      sc.integrity = "sha384-OemFRmhjDZwhIKuUld0HJozkF2YErsgDaCL41trxGQZt4/WgnopJQqQl2DvDZ07Z";
      sc.crossOrigin = "anonymous";
      sc.onload = () => {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_BASE + "pdf.worker.min.js";
        pdfjsLoaded = true;
        resolve(window.pdfjsLib);
      };
      sc.onerror = () => reject(new Error("Failed to load pdf.js"));
      document.head.appendChild(sc);
    });
  }

  // ── Image / PDF extraction ─────────────────────────────────────────────────
  const MAX_PDF_PAGES = 15;
  const MAX_BYTES = 25 * 1024 * 1024;

  async function extractImage(file, lang, status) {
    await loadTesseract();
    status.textContent = `Recognising (${lang})…`;
    const { data } = await window.Tesseract.recognize(file, lang, {
      logger: (m) => {
        if (m.status === "recognizing text")
          status.textContent = `Recognising… ${Math.round(m.progress * 100)}%`;
      },
    });
    return (data.text || "").trim();
  }

  async function extractPdf(file, lang, status) {
    const pdfjs = await loadPdfjs();
    const buf = await file.arrayBuffer();
    const pdf = await pdfjs.getDocument({ data: buf }).promise;
    const pages = Math.min(pdf.numPages, MAX_PDF_PAGES);
    const chunks = [];
    let tesseractReady = false;

    for (let p = 1; p <= pages; p++) {
      status.textContent = `PDF page ${p}/${pages}…`;
      const page = await pdf.getPage(p);

      // 1) Digital PDF — use the embedded text layer directly (fast + exact).
      let text = "";
      try {
        const tc = await page.getTextContent();
        text = tc.items.map((it) => it.str).join(" ").replace(/\s+/g, " ").trim();
      } catch (_) { /* no text layer */ }

      // 2) Scanned page (little/no embedded text) — render + OCR it.
      if (text.replace(/\s/g, "").length < 12) {
        if (!tesseractReady) { await loadTesseract(); tesseractReady = true; }
        const viewport = page.getViewport({ scale: 2 });
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
        const { data } = await window.Tesseract.recognize(canvas, lang, {
          logger: (m) => {
            if (m.status === "recognizing text")
              status.textContent = `PDF page ${p}/${pages} — OCR ${Math.round(m.progress * 100)}%`;
          },
        });
        text = (data.text || "").trim();
      }
      if (text) chunks.push(text);
    }

    const skipped = pdf.numPages - pages;
    const note = skipped > 0 ? `\n\n[… ${skipped} more page(s) not processed in the demo]` : "";
    return chunks.join("\n\n") + note;
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
      const f = file.files[0];
      const status = $("ocr-status");
      const lang = TESS_LANG[currentScript] || "eng";

      if (f.size > MAX_BYTES) {
        status.textContent = "File too large for the in-browser demo (max 25 MB).";
        return;
      }

      runBtn.disabled = true;
      status.textContent = "Loading engine…";
      try {
        const isPdf = f.type === "application/pdf" || /\.pdf$/i.test(f.name);
        const text = isPdf
          ? await extractPdf(f, lang, status)
          : await extractImage(f, lang, status);
        $("input").value = text;
        run();
        status.textContent = text.trim()
          ? "Extracted — cleaned by gurmukhifix below."
          : "No text found. Try a clearer scan, or pick the matching script.";
      } catch (e) {
        status.textContent = "Extraction failed: " + (e && e.message ? e.message : String(e));
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
    initDownload();
    initOcr();
    $("input").value = SF.SCRIPTS[currentScript].sample;
    let t;
    $("input").addEventListener("input", () => { clearTimeout(t); t = setTimeout(run, 120); });
    run();
  });
})();
