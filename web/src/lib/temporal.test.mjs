// Property test for temporal (pure). Run:  node web/src/lib/temporal.test.mjs
import { ema, momentum, trendLabel, findAnalogs, leadLag } from "./temporal.js";

let passed = 0, failed = 0;
const ok = (n, c) => { if (c) { passed++; console.log(`  ✓ ${n}`); } else { failed++; console.error(`  ✗ ${n}`); } };

// ema / momentum / trend
ok("ema of constant = constant", Math.abs(ema([5, 5, 5, 5]) - 5) < 1e-9);
ok("rising series ⇒ positive momentum", momentum([10, 20, 30, 40, 60]) > 0);
ok("falling series ⇒ negative momentum", momentum([60, 50, 40, 30, 10]) < 0);
ok("flat series ⇒ ~zero momentum", Math.abs(momentum([40, 40, 40, 40])) < 1e-6);
ok("trendLabel rising", trendLabel(10) === "rising");
ok("trendLabel falling", trendLabel(-10) === "falling");
ok("trendLabel stable", trendLabel(0) === "stable");

// findAnalogs: most similar past event ranks first; outcome carried through
const target = { id: "T", category: "conflict", geography: ["Red Sea", "Yemen"], affected_sectors: ["Shipping & Logistics"] };
const history = [
  { id: "H1", category: "conflict", geography: ["Red Sea", "Suez"], sectors: ["Shipping & Logistics"], outcome: "materialized" },
  { id: "H2", category: "economics", geography: ["United States"], sectors: ["Banking"], outcome: "failed" },
  { id: "T", category: "conflict", geography: ["Red Sea"], sectors: [] }, // self — excluded
];
const analogs = findAnalogs(target, history, 3);
ok("analogs exclude self", analogs.every((a) => a.event.id !== "T"));
ok("most similar analog first", analogs[0].event.id === "H1");
ok("analog carries outcome", analogs[0].event.outcome === "materialized");
ok("dissimilar ranks lower or dropped", !analogs.length || analogs[analogs.length - 1].similarity <= analogs[0].similarity);

// leadLag: median days between cause and effect
const evs = [
  { id: "A", first_detected_at: "2026-01-01T00:00:00Z" },
  { id: "B", first_detected_at: "2026-01-11T00:00:00Z" },
  { id: "C", first_detected_at: "2026-01-05T00:00:00Z" },
];
const edges = [{ source: "A", target: "B" }, { source: "A", target: "C" }];
ok("leadLag returns median days", leadLag(evs, edges) === 7); // lags 10 and 4 → median ~7
ok("leadLag null without timestamps", leadLag([{ id: "A" }, { id: "B" }], [{ source: "A", target: "B" }]) === null);

console.log(`\ntemporal: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
