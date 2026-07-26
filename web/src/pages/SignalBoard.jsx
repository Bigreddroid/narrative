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
import { useNavigate, Link } from "react-router-dom";
import DeckView from "../components/DeckView.jsx";

export default function SignalBoard() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col h-[calc(100vh-var(--app-header-h,0px))] min-h-[600px] bg-[#0B0E13]">
      <header className="px-5 py-3 border-b border-[rgba(240,237,232,0.07)] flex flex-wrap items-baseline gap-x-4 gap-y-1 flex-shrink-0">
        <h1 className="font-display text-[1.4rem] leading-none text-[#E8E4DC]">SIGNAL DECK</h1>
        <p className="text-[11px] text-[rgba(232,228,220,0.5)] flex-1 min-w-[240px]">
          The live event graph as an operator board — columns by status, category and discipline.
          Add or drop columns; click any signal to open it.
        </p>
        <Link to="/wipro/exec" className="font-mono text-[10px] tracking-[0.14em] uppercase text-[#C80028] hover:underline">
          ← executive deck
        </Link>
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
