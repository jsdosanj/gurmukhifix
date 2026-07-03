/*
 * gurmukhifix.js — a faithful in-browser port of the gurmukhifix post-processing
 * pipeline for the interactive demo. It mirrors the Python engine's
 * evidence-gated approach: corrections are applied only when they lower the
 * script-validity "badness" of the text, so well-formed Unicode is never
 * corrupted. Reordering passes (sihari, nukta) are deterministic Unicode fixes.
 *
 * This is a self-contained subset covering the Indic scripts (Gurmukhi,
 * Punjabi, Devanagari/Hindi); the installable Python package additionally
 * handles Urdu and Farsi. SPDX-License-Identifier: MIT
 */
(function (global) {
  "use strict";

  const REJECT = 100, WARN = 10, REVIEW = 1;

  // ── Per-script data ──────────────────────────────────────────────────────
  // Ranges are inclusive [lo, hi] codepoint pairs.
  const SCRIPTS = {
    gurmukhi: {
      label: "Gurmukhi",
      sample: "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ",
      consonants: [[0x0a15, 0x0a39], [0x0a59, 0x0a5e]],
      matras: [0x0a3e, 0x0a3f, 0x0a40, 0x0a41, 0x0a42, 0x0a47, 0x0a48, 0x0a4b, 0x0a4c],
      sihari: 0x0a3f,
      nukta: 0x0a3c,
      valid: [[0x0a00, 0x0a7f], [0x0020, 0x007e]],
      // wrong -> correct (directional; applied only with validity evidence)
      confusion: { "ਸ਼": "ਸ", "ਖ਼": "ਖ", "ਗ਼": "ਗ", "ਜ਼": "ਜ", "ਫ਼": "ਫ" },
    },
    punjabi: {
      label: "Punjabi",
      sample: "ਪੰਜਾਬੀ ਮਾਂ ਬੋਲੀ",
      consonants: [[0x0a15, 0x0a39], [0x0a59, 0x0a5e]],
      matras: [0x0a3e, 0x0a3f, 0x0a40, 0x0a41, 0x0a42, 0x0a47, 0x0a48, 0x0a4b, 0x0a4c],
      sihari: 0x0a3f,
      nukta: 0x0a3c,
      valid: [[0x0a00, 0x0a7f], [0x0020, 0x007e]],
      confusion: { "ਸ਼": "ਸ", "ਖ਼": "ਖ", "ਗ਼": "ਗ", "ਜ਼": "ਜ", "ਫ਼": "ਫ" },
    },
    hindi: {
      label: "Hindi",
      sample: "नमस्ते दुनिया",
      consonants: [[0x0915, 0x0939], [0x0958, 0x095f]],
      matras: [0x093e, 0x093f, 0x0940, 0x0941, 0x0942, 0x0943, 0x0944, 0x0947, 0x0948, 0x094b, 0x094c],
      // The i-matra (ि) is the Devanagari analogue of the sihari: drawn before its
      // consonant, encoded after. Reordered by the same pass.
      sihari: 0x093f,
      nukta: 0x093c,
      valid: [[0x0900, 0x097f], [0x0020, 0x007e]],
      confusion: {},
    },
    devanagari: {
      label: "Devanagari",
      sample: "नमस्ते दुनिया",
      consonants: [[0x0915, 0x0939], [0x0958, 0x095f]],
      matras: [0x093e, 0x093f, 0x0940, 0x0941, 0x0942, 0x0943, 0x0944, 0x0947, 0x0948, 0x094b, 0x094c],
      sihari: 0x093f,
      nukta: 0x093c,
      valid: [[0x0900, 0x097f], [0x0020, 0x007e]],
      confusion: {},
    },
  };

  function cp(ch) { return ch.codePointAt(0); }
  function inRanges(code, ranges) { return ranges.some(([lo, hi]) => code >= lo && code <= hi); }
  function isConsonant(ch, s) { return ch ? inRanges(cp(ch), s.consonants) : false; }
  function isMatra(ch, s) { return ch ? s.matras.indexOf(cp(ch)) !== -1 : false; }

  // Does the dependent sign at index i have a base consonant, skipping one nukta?
  function hasBaseConsonant(text, i, s) {
    let j = i - 1;
    if (j >= 0 && cp(text[j]) === s.nukta) j -= 1;
    return j >= 0 && isConsonant(text[j], s);
  }

  // ── Validity ─────────────────────────────────────────────────────────────
  function violations(text, s) {
    const out = [];
    const chars = Array.from(text);

    // dependent vowel at word start (after a space or at index 0) — REJECT
    chars.forEach((ch, i) => {
      if (isMatra(ch, s)) {
        const prev = i > 0 ? chars[i - 1] : " ";
        if (prev === " " || prev === "\n") {
          out.push({ sev: REJECT, label: "vowel sign at word start", ch, pos: i });
        } else if (!hasBaseConsonant(chars, i, s)) {
          out.push({ sev: WARN, label: "vowel sign with no base consonant", ch, pos: i });
        }
      }
    });

    // consecutive dependent vowels — REJECT
    for (let i = 1; i < chars.length; i++) {
      if (isMatra(chars[i], s) && isMatra(chars[i - 1], s)) {
        out.push({ sev: REJECT, label: "consecutive vowel signs", ch: chars[i - 1] + chars[i], pos: i - 1 });
      }
    }

    // codepoints outside the script's Unicode blocks — REVIEW
    chars.forEach((ch, i) => {
      const c = cp(ch);
      if (c <= 0x1f || c === 0x20) return;
      if (!inRanges(c, s.valid)) {
        out.push({ sev: REVIEW, label: `out-of-script U+${c.toString(16).toUpperCase().padStart(4, "0")}`, ch, pos: i });
      }
    });

    return out;
  }

  function badness(text, s) {
    return violations(text, s).reduce((acc, v) => acc + v.sev, 0);
  }

  // ── Deterministic reordering passes ──────────────────────────────────────
  function sihariReorder(text, s, changes) {
    if (s.sihari == null) return text;
    const chars = Array.from(text);
    const res = [];
    let i = 0;
    while (i < chars.length) {
      const ch = chars[i];
      const orphan = !(i > 0 && (isConsonant(chars[i - 1], s) ||
        (cp(chars[i - 1]) === s.nukta && isConsonant(chars[i - 2], s))));
      if (cp(ch) === s.sihari && orphan && isConsonant(chars[i + 1], s)) {
        res.push(chars[i + 1], ch);
        changes.push({ from: ch + chars[i + 1], to: chars[i + 1] + ch, rule: "sihari reorder" });
        i += 2;
      } else {
        res.push(ch);
        i += 1;
      }
    }
    return res.join("");
  }

  function nuktaOrder(text, s, changes) {
    if (s.nukta == null) return text;
    const chars = Array.from(text);
    for (let i = 1; i < chars.length; i++) {
      if (cp(chars[i]) === s.nukta && isMatra(chars[i - 1], s)) {
        const matra = chars[i - 1];
        chars[i - 1] = chars[i];
        chars[i] = matra;
        changes.push({ from: matra + String.fromCodePoint(s.nukta), to: String.fromCodePoint(s.nukta) + matra, rule: "nukta order" });
      }
    }
    return chars.join("");
  }

  // ── Evidence-gated confusion repair ──────────────────────────────────────
  function gatedConfusion(text, s, changes) {
    const keys = Object.keys(s.confusion);
    if (!keys.length) return text;
    let guard = text.length + 8;
    while (guard-- > 0) {
      const base = badness(text, s);
      if (base <= 0) break;
      let best = null;
      for (let pos = 0; pos < text.length; pos++) {
        for (const key of keys) {
          if (!text.startsWith(key, pos)) continue;
          const cand = text.slice(0, pos) + s.confusion[key] + text.slice(pos + key.length);
          const delta = base - badness(cand, s);
          if (delta > 0 && (!best || delta > best.delta)) {
            best = { delta, pos, key, repl: s.confusion[key], cand };
          }
        }
      }
      if (!best) break;
      changes.push({ from: best.key, to: best.repl, rule: "confusion repair" });
      text = best.cand;
    }
    return text;
  }

  // ── Public API ───────────────────────────────────────────────────────────
  function correct(input, scriptName) {
    const s = SCRIPTS[scriptName];
    if (!s) throw new Error("Unknown script: " + scriptName);

    const original = (input || "").normalize("NFC");
    const before = { badness: badness(original, s), violations: violations(original, s) };

    const changes = [];
    let text = original;
    if (text !== original) changes.push({ from: "(input)", to: "(NFC)", rule: "normalize" });

    text = gatedConfusion(text, s, changes);
    text = sihariReorder(text, s, changes);
    text = nuktaOrder(text, s, changes);

    // Per-word safety net: never emit text worse than the input.
    if (text !== original && badness(text, s) > before.badness) {
      text = original;
      changes.length = 0;
    }

    const after = { badness: badness(text, s), violations: violations(text, s) };
    return { input: original, output: text, changes, before, after };
  }

  global.GurmukhiFix = { correct, badness, violations, SCRIPTS };
})(window);
