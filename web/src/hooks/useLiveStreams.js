import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

// Curated official fallback — mirrors the backend's default set so the player
// still works if the API is briefly unreachable. NO simulated data: these are
// real broadcaster-published streams.
const FALLBACK_CHANNELS = [
  { id: "aljazeera-en", name: "Al Jazeera English", lang: "en", region: "QA", type: "hls",
    src: "https://live-hls-web-aje.getaj.net/AJE/01.m3u8", official: true },
  { id: "dw-en", name: "DW English", lang: "en", region: "DE", type: "hls",
    src: "https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/index.m3u8", official: true },
];

export function useLiveStreams() {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get("/live-news/streams")
      .then((data) => {
        if (!alive) return;
        setChannels(Array.isArray(data?.channels) ? data.channels : []);
      })
      .catch((err) => {
        if (!alive) return;
        // Official fallback list (not simulated) so the tab degrades gracefully.
        setChannels(FALLBACK_CHANNELS);
        setError(err);
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { channels, loading, error };
}
