import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

export function useFollows() {
  const [follows, setFollows] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    api.get("/follows/")
      .then((data) => setFollows(data.follows || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const follow = async (eventId, keywords = []) => {
    const result = await api.post("/follows/", {
      narrative_event_id: eventId,
      follow_keywords: keywords,
    });
    setFollows((prev) => [...prev, result]);
    return result;
  };

  const unfollow = async (followId) => {
    await api.delete(`/follows/${followId}`);
    setFollows((prev) => prev.filter((f) => f.id !== followId));
  };

  return { follows, loading, follow, unfollow, refresh };
}
