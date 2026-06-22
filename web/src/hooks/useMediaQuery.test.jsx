import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useMediaQuery } from "./useMediaQuery.js";

// Build a controllable matchMedia mock that lets a test flip `matches`
// and fire the "change" event the hook subscribes to.
function installMatchMedia(initialMatches) {
  let listeners = [];
  const mql = {
    matches: initialMatches,
    media: "",
    addEventListener: (_evt, cb) => listeners.push(cb),
    removeEventListener: (_evt, cb) => {
      listeners = listeners.filter((l) => l !== cb);
    },
  };
  window.matchMedia = vi.fn(() => mql);
  return {
    set(matches) {
      mql.matches = matches;
      listeners.forEach((cb) => cb());
    },
    listenerCount: () => listeners.length,
  };
}

describe("useMediaQuery", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the initial match state", () => {
    installMatchMedia(true);
    const { result } = renderHook(() => useMediaQuery("(max-width: 1024px)"));
    expect(result.current).toBe(true);
  });

  it("updates when the media query changes", () => {
    const ctl = installMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery("(max-width: 1024px)"));
    expect(result.current).toBe(false);
    act(() => ctl.set(true));
    expect(result.current).toBe(true);
  });

  it("removes its listener on unmount (no leak)", () => {
    const ctl = installMatchMedia(false);
    const { unmount } = renderHook(() => useMediaQuery("(max-width: 1024px)"));
    expect(ctl.listenerCount()).toBe(1);
    unmount();
    expect(ctl.listenerCount()).toBe(0);
  });

  it("is SSR-safe when matchMedia is unavailable", () => {
    const original = window.matchMedia;
    // @ts-expect-error - simulate an environment without matchMedia
    delete window.matchMedia;
    const { result } = renderHook(() => useMediaQuery("(max-width: 1024px)"));
    expect(result.current).toBe(false);
    window.matchMedia = original;
  });
});
