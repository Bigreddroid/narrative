import { describe, it, expect } from "vitest";
import { extractEntities } from "./osintEntities.js";

describe("extractEntities", () => {
  it("extracts a CVE id", () => {
    const e = extractEntities("Actors exploited CVE-2024-3094 in the wild.");
    expect(e).toContainEqual({ value: "CVE-2024-3094", kind: "cve" });
  });

  it("extracts an ETH wallet as crypto, not hash", () => {
    const addr = "0x" + "a".repeat(40);
    const e = extractEntities(`Funds moved to ${addr} overnight.`);
    expect(e).toContainEqual({ value: addr, kind: "crypto" });
    expect(e.some((x) => x.kind === "hash")).toBe(false);
  });

  it("extracts a sha256 file hash", () => {
    const h = "d".repeat(64);
    const e = extractEntities(`Sample sha256 ${h} flagged.`);
    expect(e).toContainEqual({ value: h, kind: "hash" });
  });

  it("extracts a valid IP and rejects out-of-range octets", () => {
    const e = extractEntities("C2 at 8.8.8.8 but 999.1.1.1 is junk.");
    expect(e).toContainEqual({ value: "8.8.8.8", kind: "ip" });
    expect(e.some((x) => x.value === "999.1.1.1")).toBe(false);
  });

  it("extracts a vessel IMO", () => {
    const e = extractEntities("Tanker IMO 9074729 went dark off Hormuz.");
    expect(e).toContainEqual({ value: "IMO 9074729", kind: "vehicle" });
  });

  it("finds nothing in plain prose", () => {
    expect(extractEntities("A quiet diplomatic meeting in Geneva today.")).toEqual([]);
  });

  it("dedupes and caps", () => {
    const e = extractEntities("CVE-2024-3094 CVE-2024-3094", { cap: 8 });
    expect(e).toHaveLength(1);
  });
});
