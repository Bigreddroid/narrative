import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { api } from "../lib/api.js";

const KEY = "narrative_following";

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); }
  catch { return []; }
}
function save(list) { localStorage.setItem(KEY, JSON.stringify(list)); }

const FollowingContext = createContext(null);

// Follows persist to the backend (/api/v1/follows) so they sync across devices,
// with localStorage kept as a rich, instant, offline-safe display cache. Each
// item carries `followId` (the backend row id) needed to unfollow.
export function FollowingProvider({ children }) {
  const [followed, setFollowed] = useState(load);

  // On mount, reconcile with the backend (source of truth for WHICH events are
  // followed); merge cached event fields for rich rendering. Silent on failure
  // (not signed in / offline) — the localStorage list stays in use.
  useEffect(() => {
    let cancelled = false;
    api.get("/follows/")
      .then((data) => {
        if (cancelled || !Array.isArray(data?.follows)) return;
        const cache = Object.fromEntries(load().map((e) => [e.id, e]));
        const merged = data.follows.map((f) => ({
          ...(cache[f.narrative_event_id] || {}),
          id: f.narrative_event_id,
          followId: f.id,
          canonical_title: cache[f.narrative_event_id]?.canonical_title || f.event_title,
          current_status: cache[f.narrative_event_id]?.current_status || f.event_status,
        }));
        setFollowed(merged);
        save(merged);
      })
      .catch(() => { /* keep localStorage-only */ });
    return () => { cancelled = true; };
  }, []);

  const follow = useCallback((event) => {
    if (followed.find((f) => f.id === event.id)) return;
    const next = [...followed, { ...event, followedAt: Date.now() }];
    setFollowed(next);
    save(next);
    api.post("/follows/", { narrative_event_id: event.id, follow_keywords: event.follow_keywords || [] })
      .then((res) => {
        if (!res?.id) return;
        setFollowed((cur) => {
          const n = cur.map((f) => (f.id === event.id ? { ...f, followId: res.id } : f));
          save(n);
          return n;
        });
      })
      .catch((err) => {
        // Free-tier limit reached — revert the optimistic add. Other errors
        // (offline / already-following / not-signed-in) keep the local entry.
        if (err?.status === 402) {
          setFollowed((cur) => {
            const n = cur.filter((f) => f.id !== event.id);
            save(n);
            return n;
          });
        }
      });
  }, [followed]);

  const unfollow = useCallback((eventId) => {
    const target = followed.find((f) => f.id === eventId);
    const next = followed.filter((f) => f.id !== eventId);
    setFollowed(next);
    save(next);
    if (target?.followId) api.delete(`/follows/${target.followId}`).catch(() => {});
  }, [followed]);

  const isFollowing = useCallback((eventId) => followed.some((f) => f.id === eventId), [followed]);

  return (
    <FollowingContext.Provider value={{ followed, follow, unfollow, isFollowing }}>
      {children}
    </FollowingContext.Provider>
  );
}

export function useFollowing() {
  const ctx = useContext(FollowingContext);
  if (!ctx) throw new Error("useFollowing must be used inside FollowingProvider");
  return ctx;
}
