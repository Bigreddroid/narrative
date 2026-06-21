// Historical analog dataset — past events + their realised outcomes. Powers the
// "this resembles X, which led to Y" pattern-match signal (temporal.findAnalogs).
// The compounding version of this is proprietary: more outcomes → sharper analogs.
export const HISTORICAL_ANALOGS = [
  { id: "h-suez-2021", date: "Mar 2021", category: "conflict", title: "Ever Given blocks the Suez Canal",
    geography: ["Suez", "Red Sea", "Egypt"], sectors: ["Shipping & Logistics", "Energy", "Consumer Prices"],
    outcome: "materialized", result: "6-day blockage halted ~$9B/day of trade; months of schedule disruption." },
  { id: "h-rus-ukr-2022", date: "Feb 2022", category: "conflict", title: "Russia invades Ukraine",
    geography: ["Ukraine", "Russia", "Europe"], sectors: ["Energy", "Grain", "Defense"],
    outcome: "materialized", result: "Energy + grain price shock, sweeping sanctions, lasting supply realignment." },
  { id: "h-covid-2020", date: "Mar 2020", category: "health", title: "COVID-19 declared a pandemic",
    geography: ["Global"], sectors: ["Healthcare", "Supply Chain", "Travel"],
    outcome: "materialized", result: "Global supply-chain seizure; demand collapse then rebound inflation." },
  { id: "h-svb-2023", date: "Mar 2023", category: "economics", title: "Silicon Valley Bank collapse",
    geography: ["United States"], sectors: ["Banking", "Technology"],
    outcome: "partial", result: "Regional-bank contagion fears, contained by a federal backstop." },
  { id: "h-taiwan-2022", date: "Aug 2022", category: "geopolitics", title: "PLA drills encircle Taiwan",
    geography: ["Taiwan", "China", "South China Sea"], sectors: ["Semiconductors", "Technology", "Shipping & Logistics"],
    outcome: "partial", result: "Brief shipping/air rerouting; no kinetic conflict; a new normal of drills." },
  { id: "h-opec-2023", date: "Apr 2023", category: "economics", title: "Surprise OPEC+ output cut",
    geography: ["Saudi Arabia", "Global"], sectors: ["Energy", "Aviation"],
    outcome: "materialized", result: "Brent spiked ~6%; fuel-cost pass-through to logistics and airlines." },
];
