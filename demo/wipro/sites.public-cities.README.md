# `sites.public-cities.csv` — provenance

A minimal starter register so the deck renders against something real. **Not a customer
register.** It exists because `sites` was empty after the fixture was removed, and a blank
deck cannot be demonstrated or tested.

## What every field is, and is not

| field | source | |
|---|---|---|
| `name` / `city` / `country` | Cities where the company's presence is a matter of public record | verifiable |
| `lat` / `lng` | Published city centroids | verifiable |
| `criticality` | **Our own coarse guess** from city size/role | a judgement, not a fact |
| `external_id` | **empty** | we do not have the customer's site IDs |
| `headcount` | **empty** | we do not know these; a plausible number would be a fabrication |

Regions match the five configured in `web/src/data/customers/wipro.json`
(India, UAE, Saudi Arabia, Europe, Americas).

## Deliberately not done

- **No campus- or building-level rows.** "Site 47 · Bengaluru" style entries are inventions.
  These are *cities*, which is all we can defend.
- **No headcounts.** The removed fixture carried "plausible placeholder" headcounts; those
  flow into exposure/duty-of-care maths and would silently become fabricated risk numbers.
  An empty cell that renders as a visible gap is the correct behaviour.
- **No external IDs.** Also guards the import: keying on a repeated `external_id` previously
  merged two distinct sites into one.

## Replacing it

When the real register arrives, import the customer's CSV through the same audited endpoint
(`POST /api/v1/sites/import`, `dry_run=true` first). Rows here carry no `external_id`, so they
will not silently merge with real rows — delete them and import clean.
