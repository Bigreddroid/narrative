import { describe, it, expect } from "vitest";
import { canAccess, TIERS, ACCESS, DEV_ACCOUNTS } from "./tiers.js";

describe("canAccess — tier gating", () => {
  it("free tier reaches free features only", () => {
    expect(canAccess("free", "fullFeed")).toBe(true);
    expect(canAccess("free", "eventGraph")).toBe(false);
    expect(canAccess("free", "apiAccess")).toBe(false);
    expect(canAccess("free", "teamSeats")).toBe(false);
  });

  it("pro tier reaches free + pro features but not intelligence/enterprise", () => {
    expect(canAccess("pro", "fullFeed")).toBe(true);
    expect(canAccess("pro", "eventGraph")).toBe(true);
    expect(canAccess("pro", "apiAccess")).toBe(false);
    expect(canAccess("pro", "webhooks")).toBe(false);
  });

  it("intelligence tier reaches through intelligence but not enterprise", () => {
    expect(canAccess("intelligence", "apiAccess")).toBe(true);
    expect(canAccess("intelligence", "export")).toBe(true);
    expect(canAccess("intelligence", "teamSeats")).toBe(false);
  });

  it("enterprise tier reaches every defined feature", () => {
    for (const feature of Object.keys(ACCESS)) {
      expect(canAccess("enterprise", feature)).toBe(true);
    }
  });

  it("Stripe 'paid' tier unlocks all paid features (monetization parity)", () => {
    // Regression guard: the Stripe webhook sets tier='paid'. If TIERS lacks it,
    // canAccess falls back to free and paying customers get a locked UI.
    expect(TIERS.paid).toBeDefined();
    for (const feature of Object.keys(ACCESS)) {
      expect(canAccess("paid", feature)).toBe(true);
    }
    // ...but 'paid' is not admin.
    expect(TIERS.paid.rank).toBeLessThan(TIERS.admin.rank);
  });

  it("OSINT catalog is a free taster; entity investigate is paid (pro+)", () => {
    expect(canAccess("free", "osint")).toBe(true);            // browse taster
    expect(canAccess("free", "osintInvestigate")).toBe(false); // gated
    expect(canAccess("pro", "osintInvestigate")).toBe(true);
    expect(canAccess("paid", "osintInvestigate")).toBe(true);
  });

  it("admin outranks enterprise (highest rank)", () => {
    expect(TIERS.admin.rank).toBeGreaterThan(TIERS.enterprise.rank);
    expect(canAccess("admin", "whiteLabel")).toBe(true);
  });

  it("unknown tier is treated as free (fail-closed)", () => {
    expect(canAccess("bogus", "fullFeed")).toBe(true);
    expect(canAccess("bogus", "eventGraph")).toBe(false);
    expect(canAccess(undefined, "apiAccess")).toBe(false);
  });

  it("unknown feature is denied for everyone (fail-closed)", () => {
    expect(canAccess("admin", "doesNotExist")).toBe(false);
    expect(canAccess("enterprise", "alsoFake")).toBe(false);
  });

  it("dev accounts map to their named tiers", () => {
    expect(DEV_ACCOUNTS["free@narrative.dev"].tier).toBe("free");
    expect(DEV_ACCOUNTS["enterprise@narrative.dev"].tier).toBe("enterprise");
    expect(DEV_ACCOUNTS["admin@narrative.dev"].tier).toBe("admin");
    // Every dev account references a real tier.
    for (const acct of Object.values(DEV_ACCOUNTS)) {
      expect(TIERS[acct.tier]).toBeDefined();
    }
  });
});
