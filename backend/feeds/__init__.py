"""
Free real-time data feeds — the app's primary, real (non-mock) event source.

Each module exposes a pure ``parse()/normalize()`` (unit-testable, no I/O) plus an
async ``fetch()`` (httpx). Parsers emit a common Signal dict:

    {external_id, source, title, summary, category, lat, lng,
     importance (0-100), status, geography: [str], ts (epoch ms)}

The ingest workers run signals through ``synthesize`` (deterministic consequence
synthesis) and upsert them as real NarrativeEvents. No LLM, no mock data.
"""
