"""
Measure clustering granularity — READ-ONLY replay of the real decision logic.

Why this exists: `cluster_logic.effective_similarity` used to multiply cosine
similarity by exp(-gap/decay) and compare it against fixed bars. Because cosine
caps at 1.0 that imposed a hard age ceiling (t <= -decay*ln(bar)) past which even
an identical article could not attach. The live corpus showed mean 1.10
articles/event and 94% single-article events. Unit tests cannot prove the fix —
they run on toy numbers — so this replays BOTH formulas over the real embeddings
and reports what actually changes.

Reads only. Never writes: it builds pseudo-events in memory and touches nothing.

FINDINGS, 2026-07-26, 8,000 real articles — read this before re-tuning anything:

    OLD (sim * exp decay)        mean 1.29 arts/event  92.4% single  316 events >=2 outlets
    NEW (bounded penalty)        mean 1.44             90.1%         366   (+16%)
    NEW + min_established=1      mean 1.57             86.2%         494   (+56%)   <- SHIPPED

Lowering the similarity bars is NOT the win it looks like. Sweeping attach/strong
downward, the *percentage* of multi-outlet events keeps climbing — but the absolute
count peaks at attach=0.78 (509) and then FALLS to 252 at attach=0.66, while the
largest cluster balloons 184 -> 649. The percentage only rises because the event
count collapses underneath it. That is over-merging: distinct stories absorbed into
blobs, which manufactures corroboration that is not real. For a product whose #1
claim is source verification, a false merge is far worse than a missed one.

Conclusion: the residual ~86% single-article rate is mostly GENUINE — the corpus
really is dominated by stories only one outlet covered. Do not "fix" it by lowering
thresholds. To move it further you need more overlapping sources ingesting the same
stories, not looser matching.

    docker exec narrativev5-api-1 sh -c 'cd /app && python scripts/measure_clustering_granularity.py --limit 8000'
"""

import argparse
import asyncio
import math
import sys

import numpy as np
from sqlalchemy import select

from backend.config import get_settings
from backend.consequence_engine import cluster_logic
from backend.database import AsyncSessionLocal
from backend.models.article import Article

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

settings = get_settings()
CANDIDATE_LIMIT = 5  # mirrors clusterer.CANDIDATE_LIMIT


def old_effective_similarity(sim, age_gap_hours, decay_hours):
    """The pre-fix formula, kept here so the comparison is honest."""
    if age_gap_hours is None or decay_hours <= 0:
        return sim
    return sim * math.exp(-max(0.0, age_gap_hours) / decay_hours)


def simulate(rows, *, use_old, attach, strong, min_established, decay_hours, max_penalty, window_hours):
    """Replay clustering over `rows` (already in ingest order). Returns stats."""
    dim = len(rows[0]["vec"])
    centroids = np.zeros((len(rows), dim), dtype=np.float32)  # unit-normalised
    ev_time = np.zeros(len(rows), dtype=np.float64)           # hours since epoch-ish
    ev_members = []                                           # list[set[source_id]]
    ev_count = []                                             # list[int]
    n_events = 0

    for r in rows:
        v = r["vec"]
        norm = np.linalg.norm(v)
        vn = v / norm if norm > 0 else v
        t = r["t"]

        chosen = None
        if n_events:
            sims = centroids[:n_events] @ vn                  # cosine (both unit vectors)
            gaps = np.abs(ev_time[:n_events] - t)
            in_window = gaps <= window_hours
            if in_window.any():
                # top-K by raw similarity, exactly like the pgvector ORDER BY
                idx = np.where(in_window)[0]
                k = min(CANDIDATE_LIMIT, len(idx))
                top = idx[np.argpartition(-sims[idx], k - 1)[:k]] if len(idx) > k else idx

                best_eff, best_i = -1.0, None
                for i in top:
                    if use_old:
                        eff = old_effective_similarity(float(sims[i]), float(gaps[i]), decay_hours)
                    else:
                        eff = cluster_logic.effective_similarity(
                            float(sims[i]), float(gaps[i]), decay_hours, max_penalty
                        )
                    if eff > best_eff:
                        best_eff, best_i = eff, i
                if best_i is not None:
                    if best_eff >= strong or (best_eff >= attach and ev_count[best_i] >= min_established):
                        chosen = best_i

        if chosen is None:
            centroids[n_events] = vn
            ev_time[n_events] = t
            ev_members.append({r["src"]})
            ev_count.append(1)
            n_events += 1
        else:
            n = ev_count[chosen]
            merged = centroids[chosen] * n + vn
            mnorm = np.linalg.norm(merged)
            centroids[chosen] = merged / mnorm if mnorm > 0 else merged
            ev_time[chosen] = t
            ev_count[chosen] = n + 1
            ev_members[chosen].add(r["src"])

    counts = np.array(ev_count)
    outlets = np.array([len(s) for s in ev_members])
    return {
        "events": n_events,
        "articles": len(rows),
        "mean_arts": counts.mean(),
        "single": int((counts == 1).sum()),
        "pct_single": 100.0 * (counts == 1).sum() / n_events,
        "multi_outlet": int((outlets >= 2).sum()),
        "pct_multi_outlet": 100.0 * (outlets >= 2).sum() / n_events,
        "three_plus": int((outlets >= 3).sum()),
        "biggest": int(counts.max()),
    }


def show(label, s):
    print(
        f"  {label:<34} events={s['events']:>6}  mean_arts={s['mean_arts']:.2f}  "
        f"single={s['pct_single']:5.1f}%  >=2 outlets={s['multi_outlet']:>5} "
        f"({s['pct_multi_outlet']:4.1f}%)  >=3={s['three_plus']:>4}  biggest={s['biggest']}"
    )


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8000, help="most recent N articles to replay")
    ap.add_argument("--sweep", action="store_true", help="also sweep the similarity bars")
    args = ap.parse_args()

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Article.id, Article.embedding, Article.published_at, Article.scraped_at, Article.source_id)
            .where(Article.embedding.isnot(None))
            .order_by(Article.scraped_at.desc())
            .limit(args.limit)
        )
        raw = res.all()

    rows = []
    for _id, emb, pub, scr, src in raw:
        ts = pub or scr
        if emb is None or ts is None:
            continue
        rows.append({
            "vec": np.asarray(emb, dtype=np.float32),
            "t": ts.timestamp() / 3600.0,
            "src": src,
        })
    rows.reverse()  # ingest order: oldest first, like cluster_unprocessed_articles

    if not rows:
        print("No embedded articles with timestamps — nothing to measure.")
        return

    decay_hours = settings.cluster_time_decay_days * 24
    window_hours = settings.cluster_time_window_days * 24
    attach = settings.cluster_attach_threshold
    strong = settings.cluster_strong_threshold
    min_est = settings.cluster_min_established
    pen = settings.cluster_max_time_penalty

    print(f"\nReplaying {len(rows)} articles (read-only).")
    print(f"attach={attach} strong={strong} min_established={min_est} "
          f"decay={decay_hours:.0f}h window={window_hours:.0f}h max_penalty={pen}\n")

    ceiling_strong = -decay_hours * math.log(strong)
    ceiling_attach = -decay_hours * math.log(attach)
    print(f"  OLD formula hard ceilings: strong bar unreachable past {ceiling_strong:.1f}h, "
          f"attach bar past {ceiling_attach:.1f}h (even at sim=1.0)\n")

    base = simulate(rows, use_old=True, attach=attach, strong=strong, min_established=min_est,
                    decay_hours=decay_hours, max_penalty=pen, window_hours=window_hours)
    show("OLD (multiplicative decay)", base)

    new = simulate(rows, use_old=False, attach=attach, strong=strong, min_established=min_est,
                   decay_hours=decay_hours, max_penalty=pen, window_hours=window_hours)
    show("NEW (bounded penalty)", new)

    # min_established=1 lets a 1-member event accept its second member at the attach
    # bar instead of demanding the strong bar. Reported so the tuning decision is
    # driven by a number rather than a guess.
    new1 = simulate(rows, use_old=False, attach=attach, strong=strong, min_established=1,
                    decay_hours=decay_hours, max_penalty=pen, window_hours=window_hours)
    show("NEW + min_established=1", new1)

    print(f"\n  articles/event: {base['mean_arts']:.2f} -> {new['mean_arts']:.2f} "
          f"(min_est=1: {new1['mean_arts']:.2f})")
    print(f"  >=2 outlets:    {base['pct_multi_outlet']:.1f}% -> {new['pct_multi_outlet']:.1f}% "
          f"(min_est=1: {new1['pct_multi_outlet']:.1f}%)\n")

    if args.sweep:
        # The decay fix alone leaves ~90% of events single-article, so the bars
        # themselves are the binding constraint. Sweep them — but watch `biggest`:
        # over-merging distinct stories would manufacture corroboration that isn't
        # real, which is a worse failure than under-clustering for this product.
        print("  Threshold sweep (min_established=1, bounded penalty):")
        print("  NOTE: watch `biggest` — a runaway max cluster means distinct stories")
        print("        are being absorbed, i.e. FAKE corroboration. Prefer under-merge.\n")
        for a, s in [(0.80, 0.84), (0.78, 0.82), (0.76, 0.80), (0.74, 0.78),
                     (0.72, 0.76), (0.70, 0.74), (0.66, 0.70)]:
            r = simulate(rows, use_old=False, attach=a, strong=s, min_established=1,
                         decay_hours=decay_hours, max_penalty=pen, window_hours=window_hours)
            show(f"attach={a:.2f} strong={s:.2f}", r)
        print()


if __name__ == "__main__":
    asyncio.run(main())
