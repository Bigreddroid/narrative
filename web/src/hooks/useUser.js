import { useState, useEffect } from "react";
import { canAccess } from "../lib/tiers.js";

const USER_KEY = "narrative_user";

// Same-tab reactivity: the `storage` event only fires in OTHER tabs, so writing
// the stored user (onboarding, the lens switcher, Settings save) wouldn't refresh
// components in the current tab. We dispatch this custom event on every write so
// useUser — and everything built on it (useProfile) — re-reads immediately.
const USER_EVENT = "narrative:user";

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY)) || null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
  window.dispatchEvent(new Event(USER_EVENT));
}

export function useUser() {
  const [user, setUser] = useState(getStoredUser);

  useEffect(() => {
    const refresh = () => setUser(getStoredUser());
    const onStorage = (e) => { if (e.key === USER_KEY) refresh(); };
    window.addEventListener("storage", onStorage);   // cross-tab
    window.addEventListener(USER_EVENT, refresh);      // same-tab
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(USER_EVENT, refresh);
    };
  }, []);

  const can = (feature) => canAccess(user?.tier || "free", feature);

  return { user, can, tier: user?.tier || "free" };
}
