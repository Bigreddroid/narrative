import { useState, useRef, useCallback, lazy, Suspense } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

// Reverse-image geolocation. Upload a photo → a vision-LLM infers where it was
// taken and returns the DANA-style OODA reasoning trace (Observe → Orient →
// Decide → Act). We show the whole trace, not just a pin, so the user can judge
// the guess — the honest answer to a black-box "map pin" (cf. SpectrAI/GeoSpy).

const WorldMap = lazy(() => import("../components/graph/WorldMap.jsx"));

const CRIMSON = "#C80028";
const MAX_MB = 8;

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-paper/10 overflow-hidden">
        <div className="h-full" style={{ width: `${pct}%`, backgroundColor: CRIMSON }} />
      </div>
      <span className="text-[11px] font-mono text-paper/60 tabular-nums">{pct}%</span>
    </div>
  );
}

function TraceList({ label, items }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className="text-[10px] font-mono uppercase tracking-widest text-paper/40 mb-1.5">{label}</p>
      <ul className="space-y-1">
        {items.map((t, i) => (
          <li key={i} className="text-[12px] text-paper/80 leading-snug flex gap-2">
            <span className="text-crimson/60 mt-0.5">▪</span>
            <span>{t}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function GeoLocate() {
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const pickFile = useCallback((f) => {
    setError(null);
    setResult(null);
    if (!f) return;
    if (!f.type.startsWith("image/")) { setError("Please choose an image file."); return; }
    if (f.size > MAX_MB * 1024 * 1024) { setError(`Image too large (max ${MAX_MB} MB).`); return; }
    setFile(f);
    setPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(f); });
  }, []);

  const onDrop = (e) => { e.preventDefault(); pickFile(e.dataTransfer.files?.[0]); };

  const locate = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.postForm("/geolocate", fd);
      setResult(res);
    } catch (e) {
      setError(e.status === 402 ? "Image geolocation is a paid-tier feature."
             : e.status === 0 ? "Can't reach the server."
             : e.message || "Geolocation failed.");
    } finally {
      setLoading(false);
    }
  };

  const best = result?.available ? result.best : null;
  const candidates = result?.available ? result.trace.decide : [];
  const nodes = candidates.map((c, i) => ({
    id: `cand-${i}`, lat: c.lat, lng: c.lng,
    title: c.place, category: "geolocation",
    current_status: i === 0 ? "escalating" : "stable",
    importance: 90 - i * 15,
  }));

  return (
    <div className="min-h-screen bg-ink text-paper flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-paper/10">
        <button onClick={() => navigate(-1)} aria-label="Back" className="text-paper/50 hover:text-paper">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 4l-6 6 6 6" /></svg>
        </button>
        <div>
          <h1 className="text-[13px] font-semibold tracking-wide">Image Geolocation</h1>
          <p className="text-[10px] text-paper/45 font-mono uppercase tracking-widest">reverse-image · vision reasoning</p>
        </div>
      </div>

      <div className="flex-1 grid md:grid-cols-2 gap-0">
        {/* Left: upload + trace */}
        <div className="p-4 space-y-4 overflow-y-auto md:max-h-[calc(100vh-56px)]">
          {/* Dropzone */}
          <div
            onDrop={onDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileRef.current?.click()}
            className="border border-dashed border-paper/20 hover:border-crimson/50 cursor-pointer transition-colors p-4 flex items-center gap-4"
          >
            <input ref={fileRef} type="file" accept="image/*" className="hidden"
                   onChange={(e) => pickFile(e.target.files?.[0])} />
            {preview ? (
              <img src={preview} alt="upload preview" className="w-24 h-24 object-cover border border-paper/15" />
            ) : (
              <div className="w-24 h-24 flex items-center justify-center border border-paper/10 text-paper/30">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></svg>
              </div>
            )}
            <div className="text-[12px] text-paper/60 leading-snug">
              <p className="text-paper/85 font-medium">{file ? file.name : "Drop a photo or click to choose"}</p>
              <p className="mt-0.5 text-paper/40">JPEG / PNG / WebP, up to {MAX_MB} MB. No location metadata needed — the model reasons from what it sees.</p>
            </div>
          </div>

          <button
            onClick={locate}
            disabled={!file || loading}
            className="w-full py-2.5 text-[12px] font-semibold uppercase tracking-widest transition-colors disabled:opacity-40"
            style={{ backgroundColor: CRIMSON, color: "#F0EDE8" }}
          >
            {loading ? "Analyzing image…" : "Locate"}
          </button>

          {error && <p className="text-[12px] text-crimson">{error}</p>}

          {result && !result.available && (
            <div className="border border-paper/10 bg-paper/[0.03] p-3 text-[12px] text-paper/70 leading-snug">
              <p className="text-paper/85 font-medium mb-1">Couldn't geolocate this image</p>
              <p>{result.reason}</p>
            </div>
          )}

          {best && (
            <div className="space-y-4">
              {/* Best guess */}
              <div className="border border-crimson/30 bg-crimson/[0.04] p-3 space-y-2">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-[15px] font-semibold text-paper">{best.place}</p>
                  <span className="text-[11px] text-paper/50">{best.country}</span>
                </div>
                <ConfidenceBar value={best.confidence} />
                {best.why && <p className="text-[12px] text-paper/70 leading-snug">{best.why}</p>}
                <p className="text-[10px] font-mono text-paper/35">
                  {best.lat.toFixed(4)}, {best.lng.toFixed(4)}
                  {result.provider ? ` · ${result.provider}` : ""}
                </p>
              </div>

              {/* OODA trace */}
              <div className="space-y-3.5">
                <TraceList label="Observe" items={result.trace.observe} />
                <TraceList label="Orient" items={result.trace.orient} />
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-paper/40 mb-1.5">Decide — candidates</p>
                  <div className="space-y-1.5">
                    {candidates.map((c, i) => (
                      <div key={i} className="border border-paper/10 p-2">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-[12px] font-medium text-paper/90">{i + 1}. {c.place}{c.country ? `, ${c.country}` : ""}</span>
                          <span className="text-[10px] font-mono text-paper/45">{Math.round((c.confidence || 0) * 100)}%</span>
                        </div>
                        {c.why && <p className="text-[11px] text-paper/55 mt-0.5 leading-snug">{c.why}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: map */}
        <div className="relative min-h-[300px] md:h-[calc(100vh-56px)] border-l border-paper/10">
          <Suspense fallback={<div className="absolute inset-0 flex items-center justify-center text-paper/30 text-[11px]">Loading map…</div>}>
            <WorldMap
              nodes={nodes}
              isDark
              focus={best ? { lng: best.lng, lat: best.lat, scale: 3.5 } : null}
              selectedNodeId={best ? "cand-0" : null}
            />
          </Suspense>
          {!best && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <p className="text-[11px] text-paper/30 font-mono uppercase tracking-widest">Upload a photo to plot the location</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
