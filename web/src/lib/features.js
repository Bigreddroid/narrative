// Feature flags for v1 surface scoping — see docs/SURFACE-AUDIT.md.
//
// The v1 buyer is the corporate Global Security / GSOC / duty-of-care team, so a
// few capabilities that belong to *later* doors (gov/defense IMINT, the SOC
// analyst-pivot crowd) are hidden from this buyer's navigation. Hiding is
// deliberately NOT deletion: the routes, pages, and engine code all stay exactly
// where they are — flipping a flag back to `true` restores the surface in one line.
//
// A build can also re-enable a surface without touching code (e.g. a gov/defense
// build that wants photo geolocation) by setting the matching env var:
//   VITE_FEATURE_GEOLOCATE=true
const flag = (envKey, fallback) => {
  const v = import.meta.env[envKey];
  if (v === undefined || v === "") return fallback;
  return v === "true";
};

export const FEATURES = {
  // Photo geolocation (vision LLM). An IMINT party trick for this buyer; its real
  // home is gov/defense IMINT, a later door. Off for v1.
  geolocate: flag("VITE_FEATURE_GEOLOCATE", false),
};
