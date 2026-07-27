"""Tests for taxonomy normalisation. Pure functions — no I/O, no LLM, no DB.

These exist because the mapper wrote the model's answer straight onto the row and the
model does not reliably honour the enum it is handed. Live data carried:

    current_status : "Developing" x4, "Escalating" x2 alongside the lower-case forms
    category       : "Economy", "Geopolitics|Economy", "Geopolitics/Economy"

Every one of those rows was invisible to the matching filter — an off-vocabulary value
does not match anything, and nothing on the board indicated the row had been dropped.
"""

from backend import taxonomy as t

passed = failed = 0


def ok(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {label}")
    else:
        failed += 1
        print(f"  FAIL {label}")


# ── status ───────────────────────────────────────────────────────────────────
ok("a canonical status passes through", t.normalize_status("escalating") == "escalating")
ok("the capitalisation the LLM actually emitted is folded",
   t.normalize_status("Developing") == "developing"
   and t.normalize_status("Escalating") == "escalating")
ok("surrounding whitespace is stripped", t.normalize_status("  stable  ") == "stable")
ok("an unknown status becomes the default rather than an invented value",
   t.normalize_status("kind-of-bad") == t.DEFAULT_STATUS)
ok("None/empty becomes the default",
   t.normalize_status(None) == t.DEFAULT_STATUS and t.normalize_status("") == t.DEFAULT_STATUS)
ok("every status the mapper can emit is in STATUSES",
   set(t.STATUSES) == {"developing", "escalating", "stable", "resolved"})

# ── category ─────────────────────────────────────────────────────────────────
ok("a canonical LLM category passes through", t.normalize_category("geopolitics") == "geopolitics")
ok("a canonical FEED category passes through", t.normalize_category("wildfire") == "wildfire")
ok("wrong case is folded — this is the live 'Economy' row",
   t.normalize_category("Economy") == "economy")
ok("a joined answer takes the first recognised part — the live 'Geopolitics|Economy'",
   t.normalize_category("Geopolitics|Economy") == "geopolitics")
ok("the other observed separator works too",
   t.normalize_category("Geopolitics/Economy") == "geopolitics")
ok("an unsalvageable category is None, never a guess",
   t.normalize_category("vibes") is None)
ok("None/empty stays None", t.normalize_category(None) is None and t.normalize_category("  ") is None)
# The point of returning None: the caller keeps the previous category rather than
# filing the event under something invented.
ok("a junk category does not silently become a real one",
   t.normalize_category("Geopolitics and Economy") == "geopolitics"
   and t.normalize_category("total nonsense") is None)

# Normalisation must land inside a vocabulary the filters actually query.
for c in t.LLM_CATEGORIES + t.CATEGORIES:
    assert t.normalize_category(c.upper()) == c, c
ok("every vocabulary term round-trips from upper case", True)

print(f"\ntaxonomy: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
