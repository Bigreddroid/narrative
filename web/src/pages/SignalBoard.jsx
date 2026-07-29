// ─────────────────────────────────────────────────────────────────────────────
// SignalBoard (/deck) — the TweetDeck-style operator board, full viewport.
//
// DeckView already existed but was trapped in a 600px box at the bottom of the
// analyst dashboard. It is the strongest operator surface in the product and it
// deserved its own room: independently-scrolling columns by status, category and
// INT discipline, over the live event graph.
//
// Deliberately separate from /wipro/exec: the executive surface stays feed-free —
// that separation IS the product thesis. This is where an operator goes when the
// executive answer prompts "show me everything".
//
// Needs the backend running (DeckView reads the live event feed); the executive
// deck does not.
// ─────────────────────────────────────────────────────────────────────────────
import { useNavigate } from "react-router-dom";
import DeckView from "../components/DeckView.jsx";
import SurfaceNav from "../components/layout/SurfaceNav.jsx";

// This board used to stay dark in both themes and hide the day/night switch. The
// reasoning was that a wall-mounted operator surface is read for hours in a dim
// room, where a white board is glare — but the effect was that /deck was the one
// surface that ignored the switch and carried its own greys, so the palette broke
// the moment you moved between surfaces. It now shares the exec deck's --xd-* ramp
// (hence `exec-deck` on the root) and offers the switch like everywhere else;
// an operator who wants the dark wall simply leaves it on night.
const BOARD_LINKS = [
  { to: "/wipro/exec", label: "Executive deck" },
  { to: "/wipro",      label: "Analyst board" },
  { to: "/world",      label: "Feed" },
];

export default function SignalBoard() {
  const navigate = useNavigate();
  return (
    <div className="exec-deck flex flex-col h-[calc(100vh-var(--app-header-h,0px))] min-h-[600px] bg-[var(--xd-0)] text-[var(--xd-23)]">
      <SurfaceNav links={BOARD_LINKS} fallback="/world" tone="var"
        className="flex-shrink-0" />
      <header className="px-5 py-3 border-b border-[var(--xd-8)] flex flex-wrap items-baseline gap-x-4 gap-y-1 flex-shrink-0">
        <h1 className="font-display text-[1.4rem] leading-none text-[var(--xd-23)]">SIGNAL DECK</h1>
        <p className="text-[11px] text-[var(--xd-19)] flex-1 min-w-[240px]">
          The live event graph as an operator board — columns by status, category and discipline.
          Add or drop columns; click any signal to open it.
        </p>
      </header>
      <div className="flex-1 min-h-0">
        <DeckView
          selectedEventId={null}
          onEventSelect={(id) => navigate(`/event/${id}`)}
          onEventClose={() => {}}
        />
      </div>
    </div>
  );
}
