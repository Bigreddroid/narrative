// Mock/sample data may ONLY be shown when explicitly in demo mode
// (set VITE_DEMO_MODE=true). In every other build the app shows real backend
// data or an honest empty/error state — it never passes fabricated data off as real.
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";
