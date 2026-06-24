import { useEffect, useRef, useState } from "react";

// Plays a single live channel. `type: "hls"` mounts hls.js (native HLS on
// Safari); `type: "youtube"` renders an official YouTube-live iframe embed.
// hls.js is dynamically imported so it only loads when an HLS channel plays
// (keeps it out of the main bundle).
export default function HlsPlayer({ channel }) {
  const videoRef = useRef(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setErr(null);
    if (!channel || channel.type !== "hls") return;
    const video = videoRef.current;
    if (!video) return;

    let hls;
    let cancelled = false;

    // Safari / iOS play HLS natively.
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = channel.src;
      video.play().catch(() => {});
      return () => { video.removeAttribute("src"); video.load(); };
    }

    import("hls.js").then(({ default: Hls }) => {
      if (cancelled) return;
      if (!Hls.isSupported()) {
        setErr("HLS not supported in this browser.");
        return;
      }
      hls = new Hls({ enableWorker: true, lowLatencyMode: true });
      hls.loadSource(channel.src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data?.fatal) setErr("Stream unavailable — the broadcaster feed may be down or geo-restricted.");
      });
    }).catch(() => setErr("Failed to load player."));

    return () => { cancelled = true; if (hls) hls.destroy(); };
  }, [channel]);

  if (!channel) {
    return (
      <div className="flex items-center justify-center w-full h-full text-[11px] uppercase tracking-widest"
        style={{ color: "rgba(240,237,232,0.35)" }}>
        Select a channel
      </div>
    );
  }

  if (channel.type === "youtube") {
    return (
      <iframe
        key={channel.id}
        title={channel.name}
        src={channel.src + (channel.src.includes("?") ? "&" : "?") + "autoplay=1&mute=1"}
        className="w-full h-full"
        style={{ border: 0 }}
        allow="autoplay; encrypted-media; picture-in-picture"
        allowFullScreen
        referrerPolicy="strict-origin-when-cross-origin"
        sandbox="allow-scripts allow-same-origin allow-presentation"
      />
    );
  }

  return (
    <div className="relative w-full h-full bg-black">
      <video
        ref={videoRef}
        className="w-full h-full"
        controls
        muted
        autoPlay
        playsInline
      />
      {err && (
        <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-[12px]"
          style={{ color: "rgba(240,237,232,0.6)", backgroundColor: "rgba(0,0,0,0.7)" }}>
          {err}
        </div>
      )}
    </div>
  );
}
