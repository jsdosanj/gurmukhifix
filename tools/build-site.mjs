/*
 * build-site.mjs — static-site generator for the gurmukhifix GitHub Pages site.
 *
 * One layout, one nav, one footer → every page stays consistent. Run with:
 *     node tools/build-site.mjs
 * It writes HTML into docs/. The interactive demo assets (assets/*.js, *.css)
 * are maintained by hand; this generator only produces page markup.
 * SPDX-License-Identifier: MIT
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const DOCS = resolve(ROOT, "docs");
const BASE_URL = "https://gurmukhifix.dosanjhlabs.com";
const REPO = "https://github.com/jsdosanj/gurmukhifix";
const PYPI = "https://pypi.org/project/gurmukhifix/";

const write = (rel, content) => {
  const p = resolve(DOCS, rel);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, content);
  console.log("wrote", rel);
};

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// ── Layout ──────────────────────────────────────────────────────────────────
function layout({ title, description, rel, active, body, home = false, canonical }) {
  const nav = [
    ["demo", rel + "index.html#demo", "Demo"],
    ["scripts", rel + "scripts/", "Scripts"],
    ["blog", rel + "blog/", "Blog"],
    ["install", rel + "index.html#install", "Install"],
    ["license", rel + "license.html", "License"],
  ]
    .map(([k, href, label]) => `<a href="${href}"${k === active ? ' class="here"' : ""}>${label}</a>`)
    .join("\n        ");

  const scripts = home
    ? `\n  <script src="${rel}assets/gurmukhifix.js"></script>\n  <script src="${rel}assets/app.js"></script>`
    : "";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${esc(title)}</title>
  <meta name="description" content="${esc(description)}" />
  <link rel="canonical" href="${canonical || BASE_URL + "/"}" />
  <meta property="og:title" content="${esc(title)}" />
  <meta property="og:description" content="${esc(description)}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="${canonical || BASE_URL + "/"}" />
  <meta property="og:image" content="${BASE_URL}/assets/og.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${esc(title)}" />
  <meta name="twitter:description" content="${esc(description)}" />
  <meta name="twitter:image" content="${BASE_URL}/assets/og.png" />
  <link rel="icon" href="${rel}assets/favicon.svg" type="image/svg+xml" />
  <link rel="apple-touch-icon" href="${rel}assets/apple-touch-icon.png" />
  <meta name="theme-color" content="#0a0b14" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Gurmukhi:wght@400;500;700&family=Noto+Serif+Gurmukhi:wght@600;700&family=Noto+Sans+Devanagari:wght@400;600&family=Noto+Naskh+Arabic:wght@400;600&family=Noto+Nastaliq+Urdu:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="${rel}assets/styles.css" />
  <script type="application/ld+json">${JSON.stringify({
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "gurmukhifix",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Cross-platform (Python 3.10+)",
    description,
    url: BASE_URL + "/",
    codeRepository: REPO,
    downloadUrl: PYPI,
    license: "https://spdx.org/licenses/MIT.html",
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
    author: { "@type": "Person", name: "Jasvant Singh Dosanjh" },
  })}</script>
</head>
<body>
  <div class="bg-aurora" aria-hidden="true"></div>
  <header class="nav">
    <a class="brand" href="${rel}index.html">
      <span class="brand-mark">ਸ</span>
      <span class="brand-name">gurmukhifix</span>
    </a>
    <nav class="nav-links">
        ${nav}
        <a class="nav-cta" href="${REPO}" target="_blank" rel="noopener">GitHub ↗</a>
    </nav>
  </header>
${body}
  <footer class="footer">
    <div class="footer-inner">
      <div>
        <span class="brand-mark small">ਸ</span>
        <strong>gurmukhifix</strong>
        <p>OCR post-processing for South Asian &amp; Persian scripts. Free &amp; open source under the MIT licence.</p>
      </div>
      <div class="footer-links">
        <a href="${rel}scripts/">Scripts</a>
        <a href="${rel}blog/">Blog</a>
        <a href="${rel}license.html">Licence</a>
        <a href="${REPO}" target="_blank" rel="noopener">GitHub</a>
        <a href="${PYPI}" target="_blank" rel="noopener">PyPI</a>
      </div>
    </div>
    <p class="footer-fine">Demo runs entirely client-side. Built for researchers, archivists and digitisation teams.</p>
  </footer>${scripts}
</body>
</html>
`;
}

// ── Reusable fragments ──────────────────────────────────────────────────────
const sectionHead = (h2, p) => `    <div class="section-head"><h2>${h2}</h2><p>${p}</p></div>`;

const beatBox = `
  <section class="doc-section">
    <div class="doc-wrap">
      <h2>Why this beats the alternatives</h2>
      <div class="beat-grid">
        <div class="beat"><h3>vs. Tesseract alone</h3><p>Tesseract turns pixels into characters. It has <em>no</em> linguistic knowledge — it can't know that a dependent vowel may not begin a word, or that a sign written to the left of a letter must be encoded after it. gurmukhifix adds exactly those rules.</p></div>
        <div class="beat"><h3>vs. find-and-replace / spellcheck</h3><p>A blind substitution table rewrites correct letters too and corrupts good text. gurmukhifix is <strong>evidence-gated</strong>: a fix is applied only when it makes the text more valid, so already-correct Unicode is never changed.</p></div>
        <div class="beat"><h3>vs. doing nothing</h3><p>Raw OCR often <em>looks</em> right but is malformed Unicode — wrong code-point order, dropped marks. That silently breaks search, indexing, fonts and copy-paste. gurmukhifix produces canonical, well-formed text.</p></div>
      </div>
    </div>
  </section>`;

// ── Per-script content ──────────────────────────────────────────────────────
const SCRIPTS = [
  {
    key: "gurmukhi", name: "Gurmukhi", native: "ਗੁਰਮੁਖੀ", cls: "gur", glyph: "ੴ", jsDemo: true,
    blurb: "The script of Sikh scripture and one of the writing systems for Punjabi.",
    where: "Gurmukhi is used for the Guru Granth Sahib and centuries of Sikh and Punjabi manuscripts across north-west India. Most historical material is handwritten, where Tesseract struggles most.",
    problems: [
      { t: "Sihari written before its consonant", b: "The vowel sign sihari (ਿ) is drawn to the <em>left</em> of its consonant, but Unicode requires it to be stored <em>after</em>. Tesseract outputs what it sees, so the order is wrong.", before: "ਿਸੱਖ", after: "ਸਿੱਖ" },
      { t: "Nukta drifts after the vowel", b: "A nukta (਼) belongs immediately after its consonant (consonant → nukta → vowel). OCR often emits the vowel first, which Unicode normalisation will not fix.", before: "ਖਾ਼ਸ", after: "ਖ਼ਾਸ" },
      { t: "Aspirated pairs look alike", b: "Handwritten ਕ/ਖ, ਗ/ਘ, ਪ/ਫ differ by a single stroke and are frequently swapped.", before: "—", after: "—" },
    ],
    fixes: [
      "Reorders an orphaned sihari to follow its base consonant.",
      "Moves a misplaced nukta into canonical consonant + nukta + vowel order.",
      "Repairs aspirated-pair and nasalisation confusions only when the surrounding word becomes more valid.",
      "Normalises to NFC and flags impossible sequences (e.g. a vowel sign starting a word).",
    ],
    examples: [
      ["ਿਸੱਖ ਧਰਮ", "ਸਿੱਖ ਧਰਮ", "Sihari reordered after its consonant"],
      ["ਖਾ਼ਸ ਗੱਲ", "ਖ਼ਾਸ ਗੱਲ", "Nukta moved before the vowel sign"],
      ["ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "Already correct — left untouched"],
    ],
  },
  {
    key: "punjabi", name: "Punjabi", native: "ਪੰਜਾਬੀ", cls: "gur", glyph: "ਪੰ", jsDemo: true,
    blurb: "Punjabi written in the Gurmukhi script — it builds on every Gurmukhi rule.",
    where: "Punjabi is the everyday language of the Punjab. Its config <code>extends</code> Gurmukhi, inheriting all of those rules and adding Punjabi-specific ones for loanwords and nasalisation.",
    problems: [
      { t: "Nukta letters for loanwords", b: "Perso-Arabic loanwords use nukta letters ਸ਼ ਖ਼ ਗ਼ ਜ਼ ਫ਼. The nukta is easily dropped or misordered in OCR.", before: "ਭਾਸਾ਼", after: "ਭਾਸ਼ਾ" },
      { t: "Tippi vs bindi nasalisation", b: "The two nasalisation marks (ੰ tippi, ਂ bindi) are visually similar and context-dependent.", before: "—", after: "—" },
      { t: "All Gurmukhi failure modes", b: "Because Punjabi uses the Gurmukhi script, every sihari and aspirated-pair issue applies here too.", before: "ਿਕਸਾਨ", after: "ਕਿਸਾਨ" },
    ],
    fixes: [
      "Inherits the full Gurmukhi rule set via config <code>extends</code>.",
      "Restores nukta order for loanword letters (ਸ਼ ਖ਼ ਗ਼ ਜ਼ ਫ਼).",
      "Handles tippi/bindi nasalisation as evidence-gated corrections.",
      "Reorders sihari and normalises to clean NFC Unicode.",
    ],
    examples: [
      ["ਿਕਸਾਨ ਵਰਗ", "ਕਿਸਾਨ ਵਰਗ", "Sihari reordered"],
      ["ਭਾਸਾ਼ ਬੋਲੀ", "ਭਾਸ਼ਾ ਬੋਲੀ", "Nukta moved before the vowel"],
      ["ਪੰਜਾਬੀ ਮਾਂ ਬੋਲੀ", "ਪੰਜਾਬੀ ਮਾਂ ਬੋਲੀ", "Already correct — untouched"],
    ],
  },
  {
    key: "hindi", name: "Hindi", native: "हिन्दी", cls: "dev", glyph: "हि", jsDemo: true,
    blurb: "Hindi written in the Devanagari script.",
    where: "Hindi is written in Devanagari and appears across north-Indian printed and handwritten records. gurmukhifix focuses on matra (vowel-sign) attachment and nasalisation.",
    problems: [
      { t: "Matra with no consonant", b: "A dependent vowel (matra) must attach to a consonant. A matra at the start of a word, or two in a row, is structurally impossible and signals an OCR error.", before: "ाकमल", after: "flagged" },
      { t: "Anusvara vs chandrabindu", b: "The nasalisation marks ं (anusvara) and ँ (chandrabindu) are easily confused.", before: "—", after: "—" },
      { t: "Sibilant ambiguity", b: "श, ष and स look similar in many hands and are routinely swapped.", before: "—", after: "—" },
    ],
    fixes: [
      "Flags matra-at-word-start and consecutive matras as REJECT for review.",
      "Corrects anusvara/chandrabindu and sibilant confusions when it improves validity.",
      "Restores nukta order for क़ ख़ ग़ ज़ फ़.",
      "Normalises to NFC and reports out-of-script code-points.",
    ],
    examples: [
      ["नमस्ते दुनिया", "नमस्ते दुनिया", "Already correct — untouched"],
      ["हिंदी भाषा", "हिंदी भाषा", "Valid — passes through"],
      ["ाकमल देश", "ाकमल देश ⚑", "Vowel sign at word start — flagged for review"],
    ],
  },
  {
    key: "devanagari", name: "Devanagari", native: "देवनागरी", cls: "dev", glyph: "दे", jsDemo: true,
    blurb: "The shared base script behind Hindi, Marathi, Nepali and Sanskrit.",
    where: "Use <code>--lang devanagari</code> for mixed or non-Hindi Devanagari material — Marathi, Nepali, Sanskrit. It inherits the Hindi rules and adds script-general ones.",
    problems: [
      { t: "Same structural matra rules", b: "Every Devanagari language shares the consonant + matra structure, so the same orphaned-matra checks apply.", before: "ाक", after: "flagged" },
      { t: "Stray Vedic accents", b: "Sanskrit scans pick up spurious udatta/anudatta accent marks from speckle.", before: "—", after: "—" },
      { t: "Avagraha noise", b: "The avagraha (ऽ) is often a misread danda or mark.", before: "—", after: "—" },
    ],
    fixes: [
      "Inherits the full Hindi rule set via config <code>extends</code>.",
      "Strips spurious Vedic accent marks and stray avagraha.",
      "Applies the Devanagari matra-validity checks.",
      "Normalises to NFC.",
    ],
    examples: [
      ["भारत देश", "भारत देश", "Already correct — untouched"],
      ["मराठी भाषा", "मराठी भाषा", "Valid Marathi — passes through"],
      ["ाक", "ाक ⚑", "Vowel sign at word start — flagged"],
    ],
  },
  {
    key: "urdu", name: "Urdu", native: "اُردُو", cls: "ara", glyph: "اُ", jsDemo: false,
    blurb: "Urdu in the Nasta'liq style — a connected, right-to-left script.",
    where: "Urdu administrative and literary records from north-west India are written in Nasta'liq, a flowing connected script that is hard for OCR. Available through the Python package.",
    problems: [
      { t: "Nukta placement changes meaning", b: "A single nukta distinguishes ب/پ and د/ذ — different letters, different words. Misplacing it corrupts meaning, not just shape.", before: "—", after: "—" },
      { t: "Hamza carrier ambiguity", b: "A standalone hamza (ء) needs the right carrier (أ, ئ, …) depending on context.", before: "—", after: "—" },
      { t: "Connected-letter breaks", b: "Tesseract can split a single connected glyph into separate letters with spurious spaces.", before: "—", after: "—" },
    ],
    fixes: [
      "Applies nukta-placement rules for the common confusable pairs.",
      "Recovers the correct hamza carrier from context.",
      "Optional, evidence-aware rejoining of broken connected letters (off by default so real word spaces are never deleted).",
      "Normalises to NFC.",
    ],
    examples: [
      ["اردو زبان", "اردو زبان", "Valid — passes through"],
      ["محبت کا پیغام", "محبت کا پیغام", "Valid — untouched"],
    ],
  },
  {
    key: "farsi", name: "Farsi", native: "فارسی", cls: "ara", glyph: "فا", jsDemo: false,
    blurb: "Persian (Farsi) — Arabic-script with Persian-specific letters.",
    where: "Persian was the court and administrative language across much of north-west India for centuries. Its records mix Persian letters that OCR often maps to the wrong Arabic forms. Available through the Python package.",
    problems: [
      { t: "Yeh variants", b: "Persian ye (ی) is frequently encoded as Arabic yaa (ي) or alef maqsura (ى), breaking search.", before: "—", after: "—" },
      { t: "Kaf / gaf confusion", b: "ک and گ differ by a small stroke and are routinely swapped.", before: "—", after: "—" },
      { t: "Persian letters read as Arabic", b: "پ چ ژ گ are often misread as their nukta-less Arabic equivalents.", before: "—", after: "—" },
    ],
    fixes: [
      "Canonicalises yeh and kaf/gaf variants to their Persian forms.",
      "Restores Persian-specific letters (پ چ ژ گ).",
      "Optional, evidence-aware joining repair for broken glyphs.",
      "Normalises to NFC.",
    ],
    examples: [
      ["زبان فارسی", "زبان فارسی", "Valid — passes through"],
      ["کتاب مطالعه", "کتاب مطالعه", "Valid — untouched"],
    ],
  },
];

// ── Script page ─────────────────────────────────────────────────────────────
function scriptPage(s) {
  const problems = s.problems
    .map((p) => {
      const ex = p.before !== "—"
        ? `<div class="ba"><code class="${s.cls} bad">${esc(p.before)}</code><span>→</span><code class="${s.cls} good">${esc(p.after)}</code></div>`
        : "";
      return `<article class="problem"><h3>${p.t}</h3><p>${p.b}</p>${ex}</article>`;
    })
    .join("\n        ");

  const fixes = s.fixes.map((f) => `<li>${f}</li>`).join("\n          ");

  const rows = s.examples
    .map(([raw, clean, note]) => `<tr><td><code class="${s.cls}">${esc(raw)}</code></td><td><code class="${s.cls} good">${esc(clean)}</code></td><td>${esc(note)}</td></tr>`)
    .join("\n          ");

  const cta = s.jsDemo
    ? `<a class="btn btn-primary" href="../index.html?script=${s.key}#demo">Try ${s.name} in the playground →</a>`
    : `<a class="btn btn-primary" href="${PYPI}" target="_blank" rel="noopener">Use via the Python package →</a>`;

  const body = `
  <section class="doc-hero">
    <div class="doc-wrap">
      <a class="back" href="../scripts/">← All scripts</a>
      <div class="doc-title"><span class="doc-glyph ${s.cls}">${s.glyph}</span>
        <div><h1>${s.name} <span class="native ${s.cls}">${s.native}</span></h1><p>${s.blurb}</p></div>
      </div>
    </div>
  </section>

  <section class="doc-section">
    <div class="doc-wrap">
      <h2>Where it's used</h2>
      <p class="lead">${s.where}</p>
    </div>
  </section>

  <section class="doc-section alt">
    <div class="doc-wrap">
      <h2>What Tesseract gets wrong</h2>
      <div class="problem-grid">
        ${problems}
      </div>
    </div>
  </section>

  <section class="doc-section">
    <div class="doc-wrap">
      <h2>How gurmukhifix fixes it</h2>
      <ul class="fix-list">
          ${fixes}
      </ul>
    </div>
  </section>

  <section class="doc-section alt">
    <div class="doc-wrap">
      <h2>Examples</h2>
      <table class="ex-table">
        <thead><tr><th>Raw OCR</th><th>gurmukhifix</th><th>What happened</th></tr></thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>
  </section>
${beatBox}
  <section class="doc-cta"><div class="doc-wrap">${cta}</div></section>`;

  return layout({
    title: `${s.name} OCR correction — gurmukhifix`,
    description: `How gurmukhifix cleans Tesseract OCR for ${s.name} into well-formed Unicode, and why it beats Tesseract alone.`,
    rel: "../", active: "scripts", body,
    canonical: `${BASE_URL}/scripts/${s.key}.html`,
  });
}

// ── Scripts index ───────────────────────────────────────────────────────────
function scriptsIndex() {
  const cards = SCRIPTS.map(
    (s) => `<a class="doc-card" href="${s.key}.html"><span class="glyph ${s.cls}">${s.glyph}</span><h3>${s.name} <small class="${s.cls}">${s.native}</small></h3><p>${s.blurb}</p><span class="more">Read the deep-dive →</span></a>`
  ).join("\n        ");
  const body = `
  <section class="doc-hero">
    <div class="doc-wrap"><h1>Scripts, explained</h1><p class="lead">A plain-English deep-dive into how gurmukhifix corrects each script, and why a post-processor beats raw Tesseract.</p></div>
  </section>
  <section class="doc-section">
    <div class="doc-wrap">
      <div class="doc-cards">
        ${cards}
      </div>
    </div>
  </section>`;
  return layout({
    title: "Scripts — gurmukhifix", description: "Deep-dive guides to how gurmukhifix corrects Gurmukhi, Punjabi, Hindi, Devanagari, Urdu and Farsi OCR.",
    rel: "../", active: "scripts", body, canonical: `${BASE_URL}/scripts/`,
  });
}

// ── Blog ────────────────────────────────────────────────────────────────────
function blogPage() {
  const body = `
  <article class="post">
    <div class="doc-wrap">
      <a class="back" href="../index.html">← Home</a>
      <p class="post-kicker">Field notes</p>
      <h1>Why we built gurmukhifix: 600 years of manuscripts vs. one stubborn OCR problem</h1>
      <p class="post-meta">On digitising north-west India's written heritage — and why Tesseract alone wasn't enough.</p>

      <p class="lead">It started with a pile of scans. Thousands of them: handwritten manuscripts, ledgers and printed pages from north-west India spanning roughly the 1400s to the present day. Gurmukhi scripture and Punjabi correspondence. Persian and Urdu administrative records. Hindi and Devanagari texts. The goal was simple to state and hard to do — turn the images into searchable, reusable digital text.</p>

      <h2>The promise and the wall</h2>
      <p>Modern OCR feels like magic on clean printed English. So we pointed Tesseract at the collection and waited. What came back looked, at a glance, like text. But when we tried to <em>search</em> it, index it, or paste it into a document, it fell apart.</p>
      <p>For handwritten Gurmukhi and Urdu, character error rates routinely ran past 30–40%. Worse, the errors weren't random noise — they were <strong>systematic</strong>, and they produced Unicode that was subtly, invisibly broken.</p>

      <h2>The bug you can't see</h2>
      <p>Take one example that haunted the Gurmukhi pages. The vowel sign <em>sihari</em> (ਿ) is written to the <em>left</em> of the consonant it belongs to — but the Unicode standard says it must be <em>stored after</em> that consonant. Tesseract, faithfully, writes down what it sees: the sihari first. The result renders almost correctly on screen, so it passes the eye test. Then you search for the word and get nothing, because at the byte level it's a different, impossible sequence.</p>
      <p>Persian and Urdu had their own version of this: a single misplaced or dropped nukta turning ب into پ, or ی silently encoded as ي. Hindi had matras detached from their consonants. Every script had a handful of these — predictable, rule-shaped failures that no amount of re-running Tesseract would fix, because <strong>Tesseract has no idea what the script's rules are</strong>. Its job is pixels to characters. It does not know that a dependent vowel cannot begin a word.</p>

      <h2>Larivaar, padched, and where words begin</h2>
      <p>There is a second, deeper version of the same problem, and it is unique to Gurbani. Historically the Guru Granth Sahib was written <em>larivaar</em> — one unbroken stream of letters, with no spaces between words at all. Later <em>padched</em> ("word-split") saroops added the spaces to aid reading. OCR of either has to decide where one word ends and the next begins, and it gets that wrong constantly: fusing words that belong apart, or splitting one mid-cluster.</p>
      <figure class="saroop-figure">
        <div class="saroop-grid">
          <div><img src="../assets/larivaar.png" alt="Mool Mantar written larivaar — a continuous stream of Gurmukhi with no spaces between words" loading="lazy" /><figcaption>Larivaar — no word breaks</figcaption></div>
          <div><img src="../assets/padched.png" alt="The same Mool Mantar written padched — a space between every word" loading="lazy" /><figcaption>Padched — word-separated</figcaption></div>
        </div>
        <figcaption class="saroop-cap">The same Mool Mantar. Word boundaries are precisely what OCR — and any search index built on it — has to get right, and precisely what gurmukhifix reasons about, gated against a verbatim Gurbani lexicon so a real scripture word is never split or rewritten.</figcaption>
      </figure>

      <h2>Why the obvious fixes didn't work</h2>
      <p>The tempting first move is a find-and-replace table: "whenever you see X, write Y." We tried versions of that. It was a disaster. A blind substitution rewrites the letters that were <em>already correct</em>, and on a corpus that is mostly correct, that means you corrupt far more than you fix. An early naive pass actually made the text <em>worse</em> than raw Tesseract — by a lot.</p>
      <p>The other tempting move is "just train a better model." That helps the recognition step, but it's expensive, needs labelled handwriting data we didn't have, and still leaves the structural Unicode problems untouched.</p>

      <h2>The idea: correct only with evidence</h2>
      <p>What finally worked was a different framing. Don't guess. Only change a character when there's <strong>evidence</strong> that the change makes the text more linguistically valid. If a word is already well-formed, leave it completely alone. If a sihari is sitting where a vowel sign can't legally sit, reorder it — because that move provably resolves a violation. If two letters are genuinely ambiguous and there's no signal which is right, don't flip a coin; flag it for a human.</p>
      <p>That principle — <em>evidence-gated correction</em> — became gurmukhifix. It sits <em>after</em> OCR — any engine now: Tesseract, Surya, Gemini, Google Vision — and applies the rules the recognizer can't: reorder the sihari, canonicalise the nukta, normalise to clean NFC Unicode, and flag anything it isn't sure about. Two things make it <em>safe</em> rather than merely clever. A 67,000-word <strong>Gurbani lexicon</strong> locks verbatim scripture, so a real Gurbani word is never split or rewritten; and every substitution must carry positive evidence — a validity gain or a dictionary hit — so a blind guess between two valid letters is refused, not taken. That no-corruption guarantee is <strong>property-tested</strong> across every script and the entire Guru Granth Sahib in continuous integration.</p>

      <h2>Why all these scripts, together</h2>
      <p>The archives of north-west India don't come neatly sorted by script. A single shelf might hold Gurmukhi scripture, a Persian land record and an Urdu letter. Existing post-processing tools, where they existed at all, covered one script in isolation. We needed one pipeline that understood Gurmukhi, Punjabi, Hindi, Devanagari, Urdu and Farsi — sharing an engine, differing only in their rules. That's what gurmukhifix is.</p>

      <h2>The result</h2>
      <p>On 300 real lines of Sri Guru Granth Sahib Ji with the most common OCR error injected, gurmukhifix drives character error rate to <strong>zero</strong> — and corrupts <strong>zero</strong> clean lines. It ships with 400+ tests, an honest reproducible benchmark, and a browser demo that will take an image or a whole PDF, OCR it, and clean the result — with nothing ever leaving your machine. The text that comes out is canonical Unicode you can actually search, index and trust.</p>
      <p>It is not an OCR engine, and it can't recover handwriting the recognizer fundamentally couldn't read. It is the missing layer between "the OCR ran" and "the text is usable." For anyone trying to make six centuries of a region's writing searchable, that layer turned out to be the whole game.</p>

      <p class="post-cta">gurmukhifix is free and open source under the MIT licence. <a href="../index.html#demo">Try the live demo</a> or <a href="${PYPI}" target="_blank" rel="noopener">pip install gurmukhifix</a> — it's on PyPI.</p>
    </div>
  </article>`;
  return layout({
    title: "Why we built gurmukhifix — gurmukhifix blog",
    description: "Digitising thousands of north-west Indian manuscripts (1400s–today) exposed systematic, invisible OCR errors. Here's why Tesseract alone wasn't enough — and how evidence-gated correction fixed it.",
    rel: "../", active: "blog", body, canonical: `${BASE_URL}/blog/`,
  });
}

// ── Licence page ────────────────────────────────────────────────────────────
function licensePage() {
  const mit = `MIT License

Copyright (c) 2026 Jasvant Singh Dosanjh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`;
  const body = `
  <section class="doc-hero"><div class="doc-wrap"><h1>Free to use — MIT licence</h1><p class="lead">gurmukhifix is released under the MIT licence: the most permissive, widely-trusted open-source licence there is.</p></div></section>
  <section class="doc-section"><div class="doc-wrap">
    <h2>In plain English</h2>
    <div class="lic-grid">
      <div class="lic yes"><h3>✓ You can</h3><ul><li>Use it for <strong>anything</strong> — personal, academic, government or commercial.</li><li>Copy, modify and redistribute it.</li><li>Bundle it inside closed-source or paid products.</li><li>Use it with no fee, ever.</li></ul></div>
      <div class="lic must"><h3>You only must</h3><ul><li>Keep the copyright notice and this licence text in copies of the software.</li></ul></div>
      <div class="lic no"><h3>No</h3><ul><li>Warranty — it's provided "as is".</li><li>Liability on the authors.</li></ul></div>
    </div>
    <p class="lead">That's it. There are no other strings. Anyone, anywhere, may use gurmukhifix for free.</p>
    <h2>Full licence text</h2>
    <pre class="lic-text">${esc(mit)}</pre>
    <p class="muted">Canonical copy: <a href="${REPO}/blob/main/LICENSE" target="_blank" rel="noopener">LICENSE in the repository</a> · SPDX-License-Identifier: MIT</p>
  </div></section>`;
  return layout({
    title: "Licence (MIT) — gurmukhifix", description: "gurmukhifix is free and open source under the MIT licence — usable by anyone, for anything, including commercial use.",
    rel: "", active: "license", body, canonical: `${BASE_URL}/license.html`,
  });
}

// ── 404 ─────────────────────────────────────────────────────────────────────
function notFound() {
  // Absolute base path so a 404 at any depth still finds its assets.
  const b = "/";
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Not found — gurmukhifix</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Noto+Sans+Gurmukhi:wght@700&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="${b}assets/styles.css" /></head>
<body><div class="bg-aurora" aria-hidden="true"></div>
<section class="notfound"><span class="brand-mark big">ਸ</span><h1>404</h1><p>That page wandered off. Let's get you back.</p>
<div class="hero-cta"><a class="btn btn-primary" href="${b}">Home</a><a class="btn btn-ghost" href="${b}scripts/">Scripts</a></div></section>
</body></html>
`;
}

// ── Home (ported, single-source nav/footer) ────────────────────────────────
function homePage() {
  const scriptCards = SCRIPTS.map(
    (s) => `<a class="script-card" href="scripts/${s.key}.html"><span class="card-tag ${s.jsDemo ? "in-demo" : "exp"}">${s.jsDemo ? "In the demo" : "Experimental"}</span><span class="glyph ${s.cls}">${s.glyph}</span><h3>${s.name}</h3><p>${s.blurb}</p><span class="more">Deep-dive →</span></a>`
  ).join("\n        ");

  const body = `
  <section class="hero" id="top">
    <div class="hero-inner">
      <div class="badge">OCR post-processing engine</div>
      <h1>Clean Unicode for<br /><span class="grad">handwritten Gurmukhi</span> &amp; Indic scripts</h1>
      <p class="lede">OCR mangles connected scripts: sihari lands before its consonant, nuktas drift, diacritics scatter. <strong>gurmukhifix</strong> repairs OCR output — from Tesseract, Surya, Gemini or any engine — into well-formed Unicode. Gurmukhi and Indic scripts first (Urdu &amp; Farsi are experimental), and it <strong>never</strong> corrupts text that was already correct — including Gurbani.</p>
      <div class="hero-cta">
        <a class="btn btn-primary" href="#demo">Try the live demo</a>
        <a class="btn btn-ghost" href="${PYPI}" target="_blank" rel="noopener">pip install gurmukhifix</a>
      </div>
      <div class="hero-proof">
        <div><b>0.00</b><span>corrected CER on 300 real SGGS lines</span></div>
        <div><b>6</b><span>scripts — Gurmukhi/Indic first</span></div>
        <div><b>0</b><span>silent corruptions, property-tested</span></div>
      </div>
    </div>
    <div class="hero-card">
      <div class="mini-row"><span class="mini-label">Raw OCR</span><code class="mini gur">ਿਸੱਖ ਧਰਮ</code></div>
      <div class="mini-arrow">↓ gurmukhifix</div>
      <div class="mini-row"><span class="mini-label">Unicode</span><code class="mini gur good">ਸਿੱਖ ਧਰਮ</code></div>
      <p class="mini-note">Sihari <code>ਿ</code> reordered after its base consonant — the #1 systematic Gurmukhi OCR error.</p>
    </div>
  </section>

  <section class="demo" id="demo">
${sectionHead("Interactive playground", "Paste raw OCR text and watch it become clean, well-formed Unicode. Everything runs in your browser.")}
    <p class="demo-note">This is a lightweight in-browser preview covering Gurmukhi, Punjabi, Hindi and Devanagari. The installable package is authoritative — it adds Gurbani dictionary-gating, a verbatim-scripture lock, and Urdu/Farsi. <a href="${PYPI}" target="_blank" rel="noopener">pip install gurmukhifix ↗</a></p>
    <div class="demo-toolbar">
      <label class="field"><span>Script</span><select id="script-select"></select></label>
      <div class="examples" id="examples"></div>
      <button class="btn btn-ghost small" id="ocr-toggle" type="button">📄 OCR an image or PDF</button>
    </div>
    <div class="ocr-panel" id="ocr-panel" hidden>
      <p>Drop in an <strong>image or a PDF</strong>. Digital PDFs are read straight from their text layer; scans and photos are OCR'd in your browser with <a href="https://tesseract.projectnaptha.com/" target="_blank" rel="noopener">Tesseract.js</a> (multi-page, up to 15), then cleaned by gurmukhifix. <strong>Everything runs locally — nothing is uploaded.</strong> Handwriting accuracy is limited; this demos the pipeline, not production OCR.</p>
      <div class="ocr-row"><input type="file" id="ocr-file" accept="image/*,application/pdf,.pdf" /><button class="btn btn-primary small" id="ocr-run" type="button" disabled>Extract → gurmukhifix</button><span class="ocr-status" id="ocr-status"></span></div>
    </div>
    <div class="demo-grid">
      <div class="pane"><div class="pane-head"><span>Input — raw OCR</span></div><textarea id="input" class="script-text" spellcheck="false" aria-label="Raw OCR input" placeholder="Paste OCR output here…"></textarea></div>
      <div class="pane"><div class="pane-head"><span>Output — clean Unicode</span><span class="pane-actions"><button class="copy-btn" id="download-btn" type="button">Download .txt</button><button class="copy-btn" id="copy-btn" type="button">Copy</button></span></div><div id="output" class="script-text output" aria-live="polite"></div></div>
    </div>
    <div class="report" id="report"></div>
  </section>

  <section class="how" id="how">
${sectionHead("How it works", "gurmukhifix is a post-processor, not an OCR engine. Tesseract turns the image into characters; gurmukhifix applies the linguistic rules Tesseract can't.")}
    <div class="pipeline">
      <div class="step"><span class="step-n">1</span><h3>Image → OCR</h3><p>Run any engine — Tesseract (TSV/hOCR), Surya, Gemini, Google Vision. gurmukhifix reads them all.</p></div>
      <div class="step-arrow">→</div>
      <div class="step"><span class="step-n">2</span><h3>Confidence routing</h3><p>≥85% passes through, &lt;60% is flagged, the middle band is corrected.</p></div>
      <div class="step-arrow">→</div>
      <div class="step"><span class="step-n">3</span><h3>Evidence-gated repair</h3><p>A fix is applied only if it <em>lowers</em> script-validity badness — correct text is never changed.</p></div>
      <div class="step-arrow">→</div>
      <div class="step"><span class="step-n">4</span><h3>Clean Unicode</h3><p>Corrected text, a per-fix report and preserved layout metadata.</p></div>
    </div>
    <div class="feature-grid">
      <article class="feature"><h3>Sihari reordering</h3><p>The dependent vowel <code class="gur">ਿ</code> is written before its consonant but must be encoded after it. gurmukhifix moves it back.</p></article>
      <article class="feature"><h3>Nukta canonicalisation</h3><p>A nukta after a vowel sign (<code class="gur">ਸਾ਼</code>) is reordered to the canonical consonant+nukta+vowel (<code class="gur">ਸ਼ਾ</code>).</p></article>
      <article class="feature"><h3>Never corrupts good text</h3><p>Corrections require validity evidence. Already-correct Unicode round-trips byte-for-byte — enforced by CI.</p></article>
      <article class="feature"><h3>Validity report</h3><p>Orphaned matras, impossible sequences and out-of-script code-points are surfaced with severity.</p></article>
      <article class="feature"><h3>Batch + learning</h3><p>Parallel batch processing and a SQLite store that promotes repeatedly-confirmed corrections.</p></article>
      <article class="feature"><h3>Layout preserved</h3><p>Bounding boxes flow through end-to-end so downstream tools can rebuild the page.</p></article>
    </div>
  </section>

  <section class="saroop-showcase">
${sectionHead("Larivaar &amp; padched — where words begin", 'Gurbani was written <em>larivaar</em>, one unbroken stream of letters, and later <em>padched</em> with a space between each word. Deciding where words begin is exactly what OCR gets wrong — and what gurmukhifix reasons about, gated against a verbatim Gurbani lexicon so a real scripture word is never split or rewritten.')}
    <div class="saroop-wrap">
      <figure class="saroop-figure">
        <div class="saroop-grid">
          <div><img src="assets/larivaar.png" alt="The Mool Mantar written larivaar — a continuous stream of Gurmukhi with no spaces between words" loading="lazy" /><figcaption>Larivaar — no word breaks</figcaption></div>
          <div><img src="assets/padched.png" alt="The same Mool Mantar written padched — a space between every word" loading="lazy" /><figcaption>Padched — word-separated</figcaption></div>
        </div>
      </figure>
    </div>
  </section>

  <section class="scripts" id="scripts">
${sectionHead("Six scripts, one pipeline", 'One shared engine, per-script rules via <code>extends</code>. Gurmukhi, Punjabi, Hindi and Devanagari run in the demo above; Urdu &amp; Farsi ship in the package as experimental (structural-only). Click any script for a plain-English deep-dive.')}
    <div class="script-cards">
        ${scriptCards}
    </div>
  </section>

  <section class="install" id="install">
${sectionHead("Get started", "On PyPI, MIT-licensed and free for anyone. gurmukhifix reads output from any OCR engine — Tesseract, Surya, Gemini or Google Vision.")}
    <p class="install-badges">
      <a href="${PYPI}" target="_blank" rel="noopener"><img src="https://img.shields.io/pypi/v/gurmukhifix?color=8b7cff&label=PyPI&logo=pypi&logoColor=white" alt="gurmukhifix on PyPI" height="22" /></a>
      <img src="https://img.shields.io/pypi/pyversions/gurmukhifix?color=37d0c4&logo=python&logoColor=white" alt="Supported Python versions" height="22" />
      <img src="https://img.shields.io/badge/licence-MIT-46d39a" alt="MIT licence" height="22" />
    </p>
    <div class="code-cards">
      <div class="code-card"><div class="code-head"><span>Install</span><button class="copy-btn" data-copy="pip install gurmukhifix">Copy</button></div><pre><code>pip install gurmukhifix</code></pre></div>
      <div class="code-card"><div class="code-head"><span>Run Tesseract → gurmukhifix</span><button class="copy-btn" data-copy="tesseract page.png out --oem 1 --psm 6 tsv
gurmukhifix correct --input out.tsv --lang gurmukhi --output ./results">Copy</button></div><pre><code>tesseract page.png out --oem 1 --psm 6 tsv
gurmukhifix correct --input out.tsv \\
  --lang gurmukhi --output ./results</code></pre></div>
      <div class="code-card"><div class="code-head"><span>Batch a folder</span><button class="copy-btn" data-copy="gurmukhifix batch --input-dir ./pages --lang devanagari --workers 4">Copy</button></div><pre><code>gurmukhifix batch --input-dir ./pages \\
  --lang devanagari --workers 4</code></pre></div>
    </div>
  </section>`;
  return layout({
    title: "gurmukhifix — OCR post-processing for South Asian & Persian scripts",
    description: "gurmukhifix corrects Tesseract OCR for handwritten Gurmukhi, Punjabi, Hindi, Devanagari, Urdu and Farsi — fixing sihari placement, nukta order and diacritics into clean Unicode. Free & open source.",
    rel: "", active: "demo", home: true, body, canonical: `${BASE_URL}/`,
  });
}

// ── Sitemap + robots ────────────────────────────────────────────────────────
function sitemap() {
  const urls = [
    "/", "/scripts/", "/blog/", "/license.html",
    ...SCRIPTS.map((s) => `/scripts/${s.key}.html`),
  ];
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${BASE_URL}${u}</loc></url>`).join("\n")}
</urlset>
`;
}
const robots = `User-agent: *\nAllow: /\nSitemap: ${BASE_URL}/sitemap.xml\n`;

// ── Build ───────────────────────────────────────────────────────────────────
write("index.html", homePage());
write("scripts/index.html", scriptsIndex());
SCRIPTS.forEach((s) => write(`scripts/${s.key}.html`, scriptPage(s)));
write("blog/index.html", blogPage());
write("license.html", licensePage());
write("404.html", notFound());
write("sitemap.xml", sitemap());
write("robots.txt", robots);
console.log("\nSite built into docs/");
