import { createContext, useContext, useState, useCallback } from "react";

const KEY = "narrative_following";

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); }
  catch { return []; }
}
function save(list) { localStorage.setItem(KEY, JSON.stringify(list)); }

const FollowingContext = createContext(null);

export function FollowingProvider({ children }) {
  const [followed, setFollowed] = useState(load);

  const follow = useCallback((event) => {
    setFollowed(prev => {
      if (prev.find(f => f.id === event.id)) return prev;
      const next = [...prev, { ...event, followedAt: Date.now() }];
      save(next);
      return next;
    });
  }, []);

  const unfollow = useCallback((eventId) => {
    setFollowed(prev => {
      const next = prev.filter(f => f.id !== eventId);
      save(next);
      return next;
    });
  }, []);

  const isFollowing = useCallback((eventId) => {
    return followed.some(f => f.id === eventId);
  }, [followed]);

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
