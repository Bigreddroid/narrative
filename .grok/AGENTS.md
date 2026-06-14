# AGENTS.md — Narrative v5 (The Narrative)

> ⚠️ **SUPERSEDED DIRECTION (2026-06-15) — read `MISSION.md` + `PITCH.md` first.**
> The current direction is **consumer-mission-first, enterprise-funded**, and the
> consequence engine is the product. This **reverses** earlier instructions in this
> file to "gut the consequence_engine," go "customer-only," or avoid "enterprise
> bloat." Do **NOT** delete/disable the engine (`consequence_engine/`, mapping/
> graph/importance/evolution/outcome workers, `EventConsequenceMap` /
> `EventConnection` / `PredictionOutcome`) — re-enable it. Free for citizens
> (India-first); funds/insurers/government pay for the same foresight and fund the
> free tier. Treat the sections below as historical context only where they
> conflict with this banner.

## Project Overview
- **What it is**: Standalone customer-centric "Bloomberg-like terminal" for individuals. Real-time news, data, analytics, tools, charts, and impact/consequence lenses on world events, markets, and global stories — simplified, accessible, and delightful for solo users/retail rather than enterprise (no $2k+/mo bloat). Inspired by Bloomberg but customer end only. Crimson editorial/paper-ink aesthetic (crimson accents #C80028 on paper-like backgrounds, clean typography, globe/map + dense lists/details from mockups).
- **Current State (as of remodel start)**: Overly complex backend (FastAPI + 11 workers + heavy consequence engine) largely disconnected from mostly-mock UI. Legacy v2 bloat. Partial real-data wiring from prior work. Now fully remodeling core idea + visuals + simplification per user direction. Not beta-ready.
- **Tech Stack (simplifying)**:
  - Backend: Python/FastAPI + SQLAlchemy + Postgres (pgvector optional/simplified) + Redis. Keep core ingestion/scrapers but gut/simplify complex workers/pipeline for "Bloomberg terminal" feel (news feeds, data views, simple analytics, impact tools). AI (Claude/Voyage) for summaries, relevance, light impact analysis — not over-engineered graphs.
  - Frontend: Mobile-first (React Native/Expo) with crimson editorial style. Dense terminal-like UI: search, watchlists, alerts, charts, personalized impact "lens". Potential web later for desktop terminal feel. Match mockups (globe for world view, article/event lists, details) + build-status aesthetic.
  - Hosting: Vercel/EAS for mobile, Docker/Railway for backend.
  - Other: Simple auth/tiers as customer plans (free basic, paid pro for advanced data/tools). No Telegram or complex multi-user unless it fits customer simplicity.

**This is a standalone project — completely separate from BigRedDroid, Project Z, Phantom, etc.** No branding or integration ties.
- **Tech Stack**:
  - Backend: Python/FastAPI + SQLAlchemy (async) + Postgres (pgvector) + Redis + Alembic + Prisma? (no, SQLA).
  - Workers: Dedicated modules for scrape, embed (Voyage), cluster, graph, importance, feed, outcome, archive, alert, etc.
  - AI: Claude (Sonnet primary for mapping, Haiku for some, Opus for deep thinking) + Voyage embeddings.
  - Frontend: Mobile (React Native/Expo with D3? via webview or RN libs), some web remnants in legacy.
  - Hosting: Vercel (intended), Docker for backend.
  - Other: GitHub Actions cron, Telegram? (not in v5), Stripe for tiers (skeleton).

## New Vision for Remodel (Customer-Centric Bloomberg Terminal)
- **Core Idea**: A simplified, customer-centric "Bloomberg terminal" for individuals — professional-grade real-time news, data, analytics, tools, charts, and impact/consequence lenses on world events, markets, and global stories. Not the expensive enterprise version (Bloomberg is enterprise; this is the accessible customer end). Inspired by Bloomberg's power (news + data + analytics + comms + models) but simplified, delightful, and affordable for solo users, retail investors, enthusiasts, personal decision-makers.
- **Visual Style (full Mockups/ recheck + root refs)**: Dual light/dark. **Dark terminal primary** (rich black #0D1117, dark surfaces, high-contrast data): crimson #C80028 for brand/logo wordmark ("THE NARRATIVE"), impact CTAs, "How this affects you", Media Bias pills; cyan/teal #00D4FF (or red in variants) for globe/hotspot glows, connections, live viz. **Light editorial paper** (#F5F1EB cream bg, dark ink text): same crimson accents on light cards/surfaces. Core mock patterns: interactive world/globe with glowing dots + lines, dense story cards with photos or text + impact %, "How this affects you" sections, bias indicators, personalized "Good morning + location", regional panels. Match exact mocks for terminal density (enterprise) + paper accessibility (customer).
- **Simplify Significantly**: Gut the over-engineered 11-worker consequence/prediction/graph pipeline. Keep core ingestion for news/data, use AI lightly for summaries/impact analysis/relevance. Focus on terminal-like UX: search, watchlists, alerts, charts, personalized "lens" on stories, real-time feel. Mobile-first (RN/Expo) with potential web for desktop terminal density.
- **Standalone**: Completely separate project. No BigRedDroid branding, no ties to Project Z/Phantom/automation suite unless loosely for data sources. Customer product only.
- **Productization**: Dual tracks — simple customer plans (free tier for basics, paid for advanced data/tools/alerts), enterprise plans (team seats, advanced analytics, API access, compliance). No complex multi-tenant until needed. "Enterprise end only" per user: build towards full enterprise capabilities like Bloomberg, while making customer end accessible.
- **MVP Scope**: Core terminal experience — personalized news/data feed with impact, world map/globe view, event detail with analytics/tools, watchlists/alerts. Real data end-to-end. Crimson editorial visuals. No mocks.

## Critical Priorities for Remodel
1. **Redefine core & visuals** — Update all docs (build-status.html, AGENTS.md, LOCAL_DEV.md) to new Bloomberg-customer vision + crimson editorial style from mockups. Remove old consequence platform language.
2. **Simplify backend** — Strip complex workers/consequence_engine to essentials (news ingestion, simple relevance/impact via AI, data views). Keep FastAPI/DB/scrapers patterns but make pipeline lean.
3. **Remodel mobile UX** — Redesign for terminal feel (dense, tools, search, personalization) using crimson/paper aesthetic. Fix layout/responsiveness. Wire fully to real backend (no mocks).
4. **Clean up legacy & bloat** — Narrative v2/ is archived legacy (Firebase/Vite old version). Flag in docs/READMEs; do not use or expand. Remove dev_server mocks. Prune over-complex models/code.
5. **Real data + deploy** — Ensure end-to-end real data flow. Add proper deploy config (mobile EAS, backend Docker/Railway). Seeded data for testing.
6. **Product & stretch** — Simple customer tiers. Admin/search polish. No enterprise bloat.

## Coding Standards & Conventions (enforce these)
- **Customer-first, simplicity**: Every feature must feel accessible and useful for individuals. Cut complexity ruthlessly.
- **Visual fidelity**: Match mockups/build-status exactly — crimson (#C80028), paper backgrounds, editorial clean look. No BigRedDroid styles.
- **No mocks in prod paths**: Any mock data must be clearly dev-only.
- **Clean-code**: Concise, direct. No unnecessary comments. Prefer editing existing.
- **Type safety & patterns**: Pydantic, strict where possible. Reuse FastAPI/DB patterns but simplify.
- **Skills to follow**: using-superpowers, clean-code, systematic-debugging, subagent-driven-development, hybrid-handoff (prepare [GAIA HANDOFF] for Claude Code reviews/plans).
- **GAIA flow**: Use Plan (Claude via handoff) → Execute (Grok + subs) → Review (handoff) → Polish. Use Claude Code in terminal for planning/review if needed.
- **Standalone**: No references to BigRedDroid, Phantom, Project Z, etc. in code/docs.

## How to Work Here
1. Always start by reading this file + build-status.html + LOCAL_DEV.md.
2. Update build-status.html after changes (it is the living spec).
3. Use todo_write for multi-step work.
4. For architecture/UI/positioning: Output [GAIA HANDOFF - Grok Output] block for Claude Code.
5. Legacy v2: Do not touch — it's for deletion/archive only.
6. Visuals: Reference Mockups/ folder constantly for crimson editorial style.
7. When ready for review: Use hybrid handoff.

**Owner / Context**: Standalone customer product. Focus on simplified, legit "Bloomberg for me" experience with exact visual direction from user mockups. Make no mistakes. Use Claude Code in terminal where helpful for planning/review.

Last updated: Remodel execution started — new customer-centric Bloomberg vision locked.

## Coding Standards & Conventions (enforce these)
- **Clean-code**: Concise, direct. No unnecessary comments. Prefer editing existing over new files when possible.
- **No mocks in prod paths**: Any mock data must be clearly dev-only and behind feature flags or env checks.
- **Type safety**: Use Pydantic models, strict TS where present.
- **Workers & pipeline**: All workers must log to PipelineMetric. Handle errors gracefully, increment error counts on sources.
- **Data models**: Use existing models (NarrativeEvent, EventConsequenceMap, etc.). Add only when justified.
- **Frontend (when touching)**: Mobile first. Use the existing RN structure. Avoid new web UI until backend is wired.
- **Skills to follow**:
  - using-superpowers (always check before acting).
  - clean-code, systematic-debugging.
  - For any architecture: hybrid-handoff to Claude for plan/review.
  - subagent-driven-development for parallel tasks (e.g., one subagent for backend wiring, one for mobile fixes).
- **GAIA flow**: For any non-trivial work, use Plan (Claude) → Execute (Grok + subs) → Review (handoff) → Polish.

## Current Known Flaws (to address systematically)
- Everything UI-facing is mock (build-status confirmed).
- No end-to-end data flow from workers to feed/map.
- Mobile unusable on real devices.
- Massive bloat from Narrative v2 (delete or archive after audit).
- Incomplete routes (admin not wired, Stripe placeholders).
- No tests visible.
- Overly complex for current delivered value (11 workers for zero real output).
- Deploy story broken.

## How to Work Here
1. Always start session by reading this file + root PROJECT_MEMORY.md + build-status.html.
2. Update build-status.html or add a real README.md after changes.
3. Use todo_write for any multi-step work.
4. For fixes: Prefer small, verifiable PRs. Run `check_pipeline.sh` if relevant.
5. Legacy v2: Do not touch unless explicitly for migration/cleanup. Propose deletion after v5 is stable.
6. When ready for review: Output [GAIA HANDOFF - Grok Output] block.

**Owner / Context**: Part of larger solo lab (BigRedDroid, bioos, Phantom/Project Z, etc.). Focus on making *this* one actually shippable rather than adding more ambition.

Last updated: Session start — SuperGrok setup.