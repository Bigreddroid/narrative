# Narrative — Positioning (authoritative)

> This is the **single source of truth** for who Narrative is for and how it wins.
> It supersedes the *"all segments / full TAM"* decision in
> `The-Narrative-Strategy.pdf` (§4, §12). That PDF stays as history; **this file
> is now authoritative.** See also [`CAPABILITY-MAP.md`](./CAPABILITY-MAP.md) and
> the root [`STATUS.md`](../STATUS.md).

## The one line

**Narrative is corporate security intelligence that carries a signal to its
consequence — for your people and your sites — with graded, official-source-
verified confidence the incumbents can't offer.**

Identity is unchanged from the strategy PDF: **OSINT-led, Signal → Consequence,
calibration as the moat.** What changes is that we *aim* it at one buyer instead
of five.

## The full vision vs. v1 (read this first)

**The engine is domain-blind.** Signal → consequence chain → graded probability
does not care whether the "you" at the end of the chain is a security team, a
shipping line, a police service, an army, or a government ministry. Point it at
different feeds and different "assets," and it serves any of them. **That breadth
is real and it is the long game — it is not being given up here.**

What we are choosing is only **which door we walk in through first.** One product,
one story, one buyer for v1 — because a product aimed at everyone lands with no
one. Every market below expands off the *same* engine once the beachhead proves
out (see "Later markets"). Narrowing v1 protects the vision; it does not shrink it.

- **v1 (now):** corporate Global Security / GSOC / duty-of-care.
- **Later, same engine:** military / defense, shipping & supply chain, police &
  public safety, government / situational awareness, finance, insurers.

## Why we narrowed (the honest reason)

The project felt like "too much and not clear." The cause wasn't the code — it
was the strategy's own locked decision to serve **all** segments at once (SOC,
enterprise risk, finance, gov/defense, insurers). A product aimed at five
audiences reads as built for none. We pick **one beachhead** and let the other
four become "later," not "also now."

## The beachhead buyer

**The corporate Global Security / GSOC / duty-of-care team.** Their job: keep
employees and facilities safe in risky regions, and brief leadership on what
world events mean for the company's exposure.

This is grounded in real intel — three transcripts of our target customer
(**Wipro**) on QBR calls with its *current* intelligence vendors. The buying
group is concrete: **security leads** (×2), the **intel/analyst function**
(GSEC intel-security), and **procurement**. They run 7 seats and 212 monitored
assets today.

> Individuals are referred to by role rather than by name. Git history retains
> the earlier revision, so this limits future exposure rather than erasing it —
> and no third-party names should be added back.

## The real competition (not who we assumed)

Our competitors are **physical / geopolitical security-intel vendors**, not
Palantir and not "generic OSINT."

> **Evidence basis.** This section was originally written from three QBR transcripts —
> i.e. from what the customer *said* about their vendors. It has since been corrected
> against **first-hand observation of the incumbent stack in production use**. That
> capture contains third-party confidential material and named individuals; it is held
> **outside this repository and is git-ignored**. Nothing from it is reproduced here.
> Two corrections came out of it and are folded in below: the MitKat naming, and the
> fact that **Crisis24** — the deepest of the four — was missing from this table entirely.

**Four tools run side by side on one analyst's screen.** No tool reconciles the others;
the analyst is the integration layer. That gap — not any single product's weakness —
is the opening.

| Incumbent | What they sell | Their gap = our wedge |
|---|---|---|
| **MitKat** — *Datasurfr* (`mitkatrisktracker.com`) | Per-asset risk monitoring over the customer's own site list; severity taxonomy (Notification / Warning / Crucial); branded advisories, mass-comms | Pushes alerts off **media reports**; the customer explicitly won't brief the C-suite without official-source follow-up. Severity inflates: routine conditions can drive a named site's headline grade. No consequence reasoning. |
| **Max Security** — *Intel Portal* | Country & city risk levels, tiered alert feed, global risk map, events calendar, AI assistant, assessments + recommendations | Ratings are **analyst judgement** with no auditable chain. It *does* carry a source-strength field — but it is a bare adjective, and can sit alongside consumer-social sourcing in the same report. **No accuracy track record.** |
| **Crisis24** — *Horizon* | Deepest of the four: numeric 0–5 across six domains → overall band, sites, people, location intelligence, advice library, comms, reporting | Depth without adoption — the reporting layer can sit unconfigured and empty. Site registers carry **data-quality breaks** (duplicate identifiers, wrong or missing country), and every downstream per-site number inherits them. |
| **International SOS** — *Travel Security Online* | Location headlines, risk ratings, city guides, world calendar, regional forecasts | Travel-risk reference material, not exposure reasoning. Static advisory posture; nothing ties a signal to a specific consequence for a specific site. |
| **Seerist / World Monitor / Recorded Future** (strategy PDF §5) | AI risk feeds, map monitoring, data plumbing, brand | Surface events/risk, not downstream **consequence to your assets**; opaque scoring; expensive, cloud-only. |

**What none of the four do:** publish any measure of their own accuracy. Not one shows a
resolved-outcome history, an error bar, or a hit rate. Trust in this category is
faith-based across the board.

## Wedge vs moat — do not confuse these

An earlier version of this file listed three "wedges" ranked in order. That was wrong,
and the error was costly: it ranked an **unvalidated** claim alongside a triple-cited
one, and we then led with the unvalidated one.

The distinction that matters:

- **The wedge** is what gets the meeting and what the buyer *feels*. It is validated by
  what customers actually said and by what their screens actually show.
- **The moat** is what stops a funded competitor cloning us in two quarters. It sells
  nothing on day one and is the reason we still exist in year three.

### The wedge (validated — lead with these)

1. **Official-source grading + corroboration.** The customer's #1 pain, stated
   three times across the calls: *"we won't publish to leadership on media reports
   alone."* We grade every source (NATO-Admiralty) and gate promotion on ≥2
   independent sources. **This is the lead, because it's the exact unmet ask.**
2. **Volume collapse with a visible reason.** The buyer's day is thousands of vendor
   alerts and a triage queue that has gone unused. We show what we escalated *and what
   we held, with the reason for each*. No incumbent shows the second half — they only
   ever display what they escalated, which is how routine conditions end up driving a
   named site's headline grade.
3. **Consequence to *your* people and sites** — not an event feed. The engine traces a
   world event to the company's specific exposure with evidence at every node, and
   counts in **people**, because duty-of-care liability attaches to people.

### The moat (unvalidated as a *sales* claim — never open with it)

**Self-graded, published calibration.** No incumbent publishes any accuracy measure,
and — this is the uncomfortable part — **no customer has ever asked us for one.** There
is no transcript quote demanding it. Buyers in this category renew vendors whose grades
are visibly wrong, so accuracy is not the purchase criterion.

Keep it anyway, for four reasons that are about defensibility rather than demand:

1. It is the **licence to send fewer alerts.** Once we filter, "what did you miss?" is
   the fair question, and a measured track record is the only honest answer. Without it,
   "we filter better" is unfalsifiable — the same claim the incumbents already make.
2. **Cheap now, impossible later.** A track record cannot be created retroactively.
3. It wins a **bake-off**, where every vendor asserts the same things and only a measured
   number discriminates.
4. It is the one thing a better-funded competitor cannot copy quickly.

Its executive-facing expression is the **suppression log**, not a score. Engine skill
stays honestly *withheld* until enough graded outcomes accrue (see STATUS.md) — and that
withholding is itself the proof of posture. Put it one click from "are we OK?", as the
answer to *"prove it"* — the last question an executive asks, not the first.

## Later markets (sequence, not simultaneous)

Same core engine; only the feeds, the "assets," and the packaging change per
market. This is the land-and-expand path — each door opens off the beachhead
proof, one at a time:

1. **Beachhead — enterprise security / GSOC / duty-of-care** ← we are here.
2. **SOC / threat-intel / DFIR** — the native OSINT crowd.
3. **Shipping & supply chain** — chokepoints, port closures, disruption to lanes
   (maritime AIS + chokepoint feeds already wired).
4. **Police & public safety** — event-to-local-impact for a jurisdiction.
5. **Military / defense & government** — situational awareness, on-prem / privacy
   (highest margin; our structural edge is that we run local / air-gappable).
6. **Finance** — macro / commodities desks.
7. **Insurers.**

The order is a hypothesis, not a commitment — but the rule holds: **prove one
door before opening the next.**

## What this does NOT change
- The consequence engine, taxonomy, feeds, workers, tech posture (strategy §10).
- The `$0` / local-first, on-prem-capable, closed-source posture.
- The calibration flywheel as the moat.
