import { useState, useEffect } from "react";
import { canAccess } from "../lib/tiers.js";

const USER_KEY = "narrative_user";

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
}

export function useUser() {
  const [user, setUser] = useState(getStoredUser);

  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === USER_KEY) setUser(getStoredUser());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const can = (feature) => canAccess(user?.tier || "free", feature);

  return { user, can, tier: user?.tier || "free" };
}
