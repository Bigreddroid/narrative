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
(**Wipro**) on QBR calls with its *current* intelligence vendors. The buyer is
concrete and named: security leads (Rohit, Abhishek), the intel/analyst function
(Praveesha / GSEC intel-security), and procurement (Gautam). They run 7 seats and
212 monitored assets today.

## The real competition (not who we assumed)

Our competitors are **physical / geopolitical security-intel vendors**, not
Palantir and not "generic OSINT." From the transcripts:

| Incumbent | What they sell | Their gap = our wedge |
|---|---|---|
| **MidCat** (Data Surfer Pro, SAM AI, Next Alert) | Travel-risk + duty-of-care platform: geofenced asset monitoring, branded advisories, mass-comms, external cyber threat watch | Pushes alerts off **media reports**; the customer explicitly won't brief the C-suite without official-source follow-up. No consequence reasoning. No self-grading. |
| **Max Security ("Team Max")** | Country risk ratings, ask-the-analysts, GSOC, evac support, Canvas risk-appetite override | Risk ratings are **analyst gut** ("we update the country page"); no auditable causal chain; **no accuracy track record.** |
| **Seerist / World Monitor / DataSurfr / Recorded Future** (strategy PDF §5) | AI risk feeds, map monitoring, data plumbing, brand | Surface events/risk, not downstream **consequence to your assets**; opaque scoring; expensive, cloud-only. |

## The wedge — three things, in order

1. **Official-source grading + corroboration.** The customer's #1 pain, stated
   three times across the calls: *"we won't publish to leadership on media reports
   alone."* We already grade every source (NATO-Admiralty) and gate promotion on
   ≥2 independent sources. **This is the lead, because it's the exact unmet ask.**
2. **Consequence to *your* people and sites** — not an event feed. The engine
   traces a world event to the company's specific exposure with evidence at every
   node.
3. **Self-graded, published calibration.** No incumbent grades its own accuracy;
   trust today is faith-based. We publish a checkable track record. (Engine skill
   is honestly *withheld* until enough graded outcomes accrue — see STATUS.md.)

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
