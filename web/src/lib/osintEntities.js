// Extract OSINT-investigatable entities from free text (event summaries, titles).
// Mirrors the backend detect_entity_kind() patterns so each hit deep-links to
// /osint?value=&kind= and resolves to that kind's curated lookups. Best-effort:
// these feed a manual investigate pivot, so a stray match is harmless.

function validIp(v) {
  const parts = v.split(".");
  return parts.length === 4 && parts.every((p) => {
    const n = Number(p);
    return p !== "" && n >= 0 && n <= 255 && String(n) === p;
  }) && v !== "0.0.0.0";
}

// Order matters: more specific kinds first. crypto (0x / bc1 / base58) before the
// generic hex `hash` so wallet addresses aren't read as file hashes.
const PATTERNS = [
  ["cve",     /\bCVE-\d{4}-\d{4,}\b/gi, null],
  ["vehicle", /\bIMO\s?\d{7}\b|\bMMSI\s?\d{9}\b/gi, null],
  ["ip",      /\b(?:\d{1,3}\.){3}\d{1,3}\b/g, validIp],
  ["crypto",  /\b0x[0-9a-fA-F]{40}\b|\b0x[0-9a-fA-F]{64}\b|\bbc1[a-z0-9]{20,87}\b|\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b/g, null],
  ["hash",    /\b[0-9a-fA-F]{64}\b|\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{32}\b/g, null],
];

export function extractEntities(text, { cap = 8 } = {}) {
  const blob = String(text || "");
  const out = [];
  const seen = new Set();
  for (const [kind, re, validate] of PATTERNS) {
    const rx = new RegExp(re.source, re.flags);
    let m;
    while ((m = rx.exec(blob)) !== null) {
      const value = m[0];
      if (validate && !validate(value)) continue;
      const key = value.toLowerCase();
      if (seen.has(key)) continue;   // a value claims one kind (first/most-specific wins)
      seen.add(key);
      out.push({ value, kind });
      if (out.length >= cap) return out;
    }
  }
  return out;
}
