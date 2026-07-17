import { useMemo } from "react";
import { useUser } from "./useUser.js";

// ─── The lens (R2) — one source of truth ─────────────────────────────────────
// Every profile-scoped screen (Exposure, Feed, Deck, World heat, Analyst) reads
// the user's chosen lens through this hook, so switching EU-logistics ↔ Gulf-energy
// re-renders a *different app* on the same events. The shape is intentionally flat:
//   sectors  — industries the user is exposed to        (spending_categories)
//   regions  — named routes/chokepoints + home geo       (regions, country, city)
//   assets   — free-text watched suppliers/ports/firms   (watched_assets)
//   purpose  — WHY they watch (protect supply/people/…)  (purpose)
// `active` is true once the user has picked a meaningful lens, which is what gates
// the "For You"/Lens affordances — we never pretend a blank profile is personalised.

// Sensible fallback so a never-onboarded user still sees *something* coherent
// rather than an empty lens. Matches ExposurePanel's historical default.
export const DEFAULT_PROFILE = {
  sectors: ["Technology", "Energy", "Shipping & Logistics"],
  regions: ["United States"],
  assets: [],
  purpose: [],
};

export function buildProfile(user) {
  const sectors = user?.spending_categories?.length ? user.spending_categories : DEFAULT_PROFILE.sectors;
  // Named regions/routes/chokepoints picked at onboarding take precedence, then
  // home country/city. This is what makes an EU-logistics profile (Rotterdam, Suez)
  // and a Gulf-energy profile (Hormuz, Persian Gulf) resolve differently.
  const r = [...(user?.regions || []), user?.country, user?.city].filter(Boolean);
  const regions = r.length ? r : DEFAULT_PROFILE.regions;
  const assets = user?.watched_assets || [];
  const purpose = user?.purpose || [];
  // INT-discipline axis (Phase 2d): disciplines the lens favours. Optional refinement
  // on top of sectors/regions/assets — an empty list means "no discipline bias".
  const disciplines = user?.disciplines || [];
  // "active" = the user actually chose a lens (not just the defaults). Any of a
  // custom sector list, named regions, watched assets, or favoured disciplines counts.
  const active = Boolean(
    user?.spending_categories?.length || user?.regions?.length || user?.country
      || assets.length || disciplines.length,
  );
  const label = user?.regions?.length
    ? user.regions.slice(0, 2).join(" · ")
    : user?.country || (active ? "Custom lens" : "Default lens");
  return { sectors, regions, assets, purpose, disciplines, active, label };
}

export function useProfile() {
  const { user } = useUser();
  return useMemo(() => buildProfile(user), [user]);
}
