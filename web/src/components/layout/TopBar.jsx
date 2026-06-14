export default function TopBar() {
  return (
    <header className="h-10 flex items-center px-5 border-b border-border bg-bg-surface flex-shrink-0 gap-3">
      <span className="text-2xs font-mono font-bold uppercase tracking-[0.3em] text-crimson">
        THE NARRATIVE
      </span>
      <span className="text-border-mid text-2xs">|</span>
      <span className="text-2xs font-mono text-text-muted tracking-wide uppercase">
        Consequences, not headlines.
      </span>
    </header>
  );
}
