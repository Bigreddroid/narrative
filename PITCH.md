# The Narrative — Pitch & Business Model

**We tell you how the world's next shock will hit your life — before it does, with the evidence.**

> The powerful pay **$30,000 a seat** to see what's coming. We give everyone else that foresight — **for free.**

Consumer-mission first. Enterprise-funded. One engine, two audiences. (North star: `MISSION.md`.)

---

## 1. The problem (in human terms)

Ordinary people live downstream of events they never see coming. A conflict abroad, a policy shift, a shipping disruption — weeks later it lands as a higher gas bill, a job at risk, a food-price spike. People get **headlines, not "what this means for me,"** and are blindsided by consequences that were predictable. The people who *can* afford to see it coming — funds, governments, big corporates — pay analysts a fortune to do exactly this, by hand.

## 2. Why now

LLMs made automated consequence-mapping tractable for the first time. Pre-2023, linking an event to its non-obvious downstream effects with evidence required armies of analysts. The engine that does it is already built (`backend/consequence_engine/`).

## 3. How it works (what makes it real, not vibes)

A 6-stage pipeline: **scrape** many sources → **embed** → **cluster** articles covering the same event → **score importance** (cost gate) → **map consequences with Claude** → **feed + alert**. The mapping step is the crown jewel: it separates consensus from dispute across sources, builds a causal chain to citizen-level impact, and **labels every node VERIFIED FACT / INFERRED MECHANISM / SPECULATIVE EFFECT with the exact evidence sentence.** Specific, not hand-wavy: *"LPG up 12–18% within 6 weeks based on reduced tanker throughput."* It also logs predictions and tracks whether they come true.

## 4. Who we serve first — India

1.4B people, mobile-first, acutely exposed to global price shocks (fuel, food, fertiliser), underserved by Western tools — and the engine is already India-flavored. Fastest traction, strongest mission fit. Then expand outward.

## 5. How we're different from Bloomberg (different, not "better")

We don't out-Bloomberg Bloomberg on data — that's unwinnable and beside the point. We compete on a **different axis**, for a **different person**, and add the layer Bloomberg doesn't have.

| | Bloomberg Terminal | The Narrative |
|---|---|---|
| **Who** | Financial professionals, institutions | Everyone — citizens first (free); enterprises fund it |
| **Price** | ~$30,000 / seat / yr | Free for citizens; enterprise pays |
| **Answers** | "What's happening in markets, right now" | "What happens *next* — to you" |
| **Output** | Data, feeds, charts, trading | Evidence-grounded causal chains → real-life impact, predictions, public track record |
| **Axis** | Access + speed of information | Interpretation + foresight of consequences |

Bloomberg is the **terminal for the few**; The Narrative is the **foresight layer for everyone** — and the enterprise version is *complementary* to Bloomberg, not a replacement. The contrast is the pitch: the foresight the powerful pay for, handed to the people who need it most.

## 6. The moat — "the engine is the moat"

Two compounding advantages competitors can't copy retroactively:
- **The prediction-outcome ledger.** Every event mapped + outcome logged builds an auditable accuracy record. Time-in-market = a widening trust moat, and the proof that sells enterprise.
- **Evidence discipline.** The anti-hallucination design (evidence per node, fact-type labels, "never invent a causal step") is hard to replicate and is what makes the output trustworthy enough to act on.

## 7. How we make money

**Free for citizens; enterprises pay for the same foresight and fund the free tier.** Same engine, two audiences.

| Tier | Who | Price | Role |
|---|---|---|---|
| **Free** | Every citizen | ₹0 | "How this affects you" + alerts. The mission + the growth engine. |
| **Pro** | Power users, prosumers, traders | ~₹299–499 / mo (~$5–8) | History, deeper chains, custom watchlists, more alerts. Volume revenue. |
| **Enterprise** | Hedge funds, corporate risk/strategy, insurers, government | $30k–150k / yr | Seats + API + SSO + compliance/audit + support. **The funding base.** |
| **Data / API license** | Quant funds, platforms | $50k+ / yr | Consequence graph + prediction signals as a feed. Highest margin. |

**Why this works:** the free consumer tier is cheap to serve per user and drives massive reach + the prediction track record *in public*; a handful of enterprise/government contracts (high willingness to pay to not be surprised) cover the cost and turn a profit. The mission funds itself.

## 8. Traction plan — getting to numbers fast

1. **Viral consumer hook in India:** a free, shareable "how today's news affects *your* wallet" — fuel, food, EMIs. Built for WhatsApp/mobile sharing. This is the growth flywheel and builds the public track record.
2. **Pro conversions** from engaged free users wanting history + depth.
3. **Enterprise in parallel:** land 3–5 design-partner funds / a government or insurance pilot at a discounted annual for logos, feedback, and the first ledger entries.
4. **Sell the track record, not the demo:** "here's what we flagged, and here's what happened."

## 9. Why me (founder-market fit)

Mithra Varun / BigRedDroid — solo deep-tech builder who designed and shipped the full engine (ingestion → embedding → clustering → evidence-grounded consequence-mapping → prediction tracking) alone. The 30u30 case: **mission-driven enough to give ordinary people the foresight the powerful pay for — proven enough to build it solo.**

---

## 10. The 30u30 narrative (one paragraph)

The world runs on first-order headlines and second-order surprise — and the people hurt most by that surprise are the ones who can least afford to see it coming. The powerful pay $30,000 a seat for terminals that hint at what's next; The Narrative reads the world's news and maps, with evidence at every step, how a distant event will land on an ordinary person's life: their gas bill, their job, their food — and gives it away for free, funded by the funds, insurers, and governments that pay for the same foresight. Built solo, starting in India, it turns the analyst-heavy, unauditable craft of consequence forecasting into compounding software — and keeps a public score of what it got right.
