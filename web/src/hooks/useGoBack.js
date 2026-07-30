import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

/**
 * History-aware "back", shared by every surface that offers one.
 *
 * Back has to be history-aware rather than a hardcoded parent link: these surfaces
 * write their own state to the query string with replace:true, so history holds the
 * page the reader ARRIVED from, and popping it returns them there instead of to a
 * parent they may never have visited. With nothing to pop — a link opened cold in a
 * new tab — it falls through to `fallback`, which each surface sets to its real parent.
 *
 * `window.history.state.idx` is null for the first entry of a history session, which
 * is the case that must not call navigate(-1) (it would leave the app entirely).
 *
 * Extracted from SurfaceNav so the feed's back button cannot drift from the one the
 * decks use. Two implementations of "back" that disagree is worse than none.
 */
export function useGoBack(fallback = "/world") {
  const navigate = useNavigate();
  return useCallback(() => {
    if (window.history.state?.idx > 0) navigate(-1);
    else navigate(fallback);
  }, [navigate, fallback]);
}

export default useGoBack;
