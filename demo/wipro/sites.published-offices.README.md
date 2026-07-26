# `sites.published-offices.csv` — provenance

Every office Wipro publishes on <https://www.wipro.com/locations/> — **121 rows across 43
countries**, transcribed from that page on 2026-07-27. **Not a customer register.** It exists
because `sites` was empty after the 214-row fixture was removed, and a blank deck cannot be
demonstrated or tested.

It replaces an earlier 13-row city list. That list was defensible but thin: it carried five
countries and no site identity, so the board showed thirteen dots where the company publishes
a hundred and twenty-one addresses.

## What every field is, and is not

| field | source | |
|---|---|---|
| `name` | The site designation and street/locality **as published** (`SJP2`, `KDC3`, `Wave by Skanska`) | verifiable |
| `city` / `country` | The published address | verifiable |
| `lat` / `lng` | **Locality centroid**, not the building — see below | approximate, deliberately |
| `type` | Read off the published address (see below) | inferred, but from the source text |
| `criticality` | **Our own coarse guess** | a judgement, not a fact |
| `external_id` | **empty** | we do not have the customer's site IDs |
| `headcount` | **empty** | we do not know these; a plausible number would be a fabrication |

### Coordinates are locality centroids

The published addresses are street addresses; we have no geocoder in the stack and will not
hand-type 121 rooftop coordinates we cannot check. So each row carries the centroid of the
smallest locality its address actually names — `Electronics City Phase 1` rather than
Bengaluru, `Salt Lake Sector V` rather than Kolkata, `Zhangjiang` rather than Shanghai —
and the city centroid where the address names nothing finer.

**Sites published at one address share one coordinate.** SJP1/SJP2, EC4/EC5 and KDC1/2/3 are
separate buildings on one plot; nudging them apart would invent a precision we do not have.
This is correct for what the coordinate is used for — proximity of a site to a geolocated
event, at 25–150 km radii — and wrong for anything that needs a building.

### `type` is read off the address, not assumed

- `campus` — the address names a Wipro-owned campus (`Wipro Campus` Dalian, `Edificio Wipro`
  Maia, Doddakannelli/Sarjapur Road, Electronics City, Kodathi, Metagalli, Hinjewadi).
- `delivery` — the address names an SEZ, development centre or tech park (CDC, KDC, PDC,
  Infopark, ELCOT, IDCO, Candor Tech Space, Kensington SEZ).
- `office` — everything else, including the rows whose address states a serviced provider
  (Regus, Spaces, Westhive, CONNEXT).

### `criticality` is the one guess

Tier-1 is the published corporate office alone. Tier-2 is the owned campuses, the India
delivery centres and the offices in Wipro's larger markets; tier-3 is the rest, weighted
toward the serviced-office rows. This is a judgement and nothing more — it is display and
filter only (`ExecDeck.jsx`), never an input to exposure or duty-of-care maths, which is the
only reason it is acceptable to ship a guess in this column at all.

## Deliberately not done

- **No headcounts.** The removed fixture carried "plausible placeholder" headcounts; those
  flow into exposure/duty-of-care maths and would silently become fabricated risk numbers.
  An empty cell that renders as a visible gap is the correct behaviour. The audit reports
  all 121 rows as `missing_headcount` — that finding is the honest state of this register,
  not a defect to be quieted.
- **No external IDs.** Also guards the import: keying on a repeated `external_id` previously
  merged two distinct sites into one. With the column empty, the import is idempotent on
  `name`+`city`, which is why every `name` here is unique within its city.
- **No sites Wipro does not publish.** Wipro states a presence in 65+ countries; this page
  lists 43. The difference is real and we are not filling it in from inference — an office
  we cannot cite is an office we would be inventing.
- **Vienna and Warsaw appear once each.** The locations page lists each of those addresses
  twice, identically. Carrying both would have manufactured a `duplicate_location` finding
  out of a listing artefact.

## Verification

```
GET /api/v1/sites  ->  121 rows, 43 countries
audit              ->  0 critical, 121 warnings (all missing_headcount), 0 unmapped_country
re-import          ->  0 created / 121 unchanged   (idempotent on name+city)
```

## Replacing it

When the real register arrives, import the customer's CSV through the same audited endpoint
(`POST /api/v1/sites/import`, `dry_run=true` first). Rows here carry no `external_id`, so they
will not silently merge with real rows — delete them and import clean.
