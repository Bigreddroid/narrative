import { useState, useEffect } from "react";

// Subscribe to a CSS media query and re-render when it changes.
// SSR-safe (returns `false` until mounted) with proper listener cleanup.
// Use for the few places that need a JS boolean (inline pixel styles);
// prefer Tailwind breakpoint classes everywhere else.
export function useMediaQuery(query) {
  const get = () =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(query).matches
      : false;

  const [matches, setMatches] = useState(get);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange(); // sync in case the query changed between render and effect
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

export default useMediaQuery;
