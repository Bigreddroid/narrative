// ─────────────────────────────────────────────────────────────────────────────
//  Mock intelligence dataset — single source of truth for the offline demo.
//
//  Every event is FULLY mapped: consequence chain, predictions, direct/indirect
//  impacts, source articles, and map coordinates. This powers the feed, the world
//  map, the EventGraph side panel and the EventDetail page when the backend is
//  offline — so the entire product is demoable end-to-end without the pipeline.
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_EVENTS = [
  {
    id: "1", category: "conflict", current_status: "escalating",
    canonical_title: "Red Sea Shipping Corridor Under Sustained Attack",
    canonical_summary: "Houthi missile and drone strikes on commercial vessels have reduced Red Sea cargo transit by 40%, forcing rerouting around the Cape of Good Hope and adding 10-14 days to Asia-Europe shipping times.",
    importance_score: 91, geography: ["Yemen", "Red Sea", "Gulf of Aden", "Suez"],
    lat: 14.5, lng: 42.8,
    source_bias: { left: 22, center: 60, right: 18 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Houthi forces have launched 45+ attacks on merchant vessels since November, disrupting 12-15% of global container shipping.", evidence: "Confirmed by US CENTCOM strike logs and Lloyd's List vessel-tracking data." },
        { type: "INFERRED MECHANISM", content: "Rerouting via the Cape of Good Hope adds 10-14 days and $400-800k per voyage in bunker fuel, eroding carrier schedules.", evidence: "Drewry World Container Index shows Shanghai–Rotterdam spot rates up 248% since October." },
        { type: "INFERRED MECHANISM", content: "Just-in-time manufacturing in Europe faces parts shortages as delivery windows slip, forcing temporary line stoppages.", evidence: "Tesla Berlin and Volvo Ghent both announced multi-week production pauses citing component delays." },
        { type: "SPECULATIVE EFFECT", content: "Sustained disruption beyond Q2 could add 0.5-0.7pp to eurozone core goods inflation, complicating ECB rate-cut timing." },
      ],
      direct_impact: [
        { sector: "Shipping & Logistics", severity: "critical", description: "40% reduction in Red Sea transits; war-risk insurance premiums up 3x to ~1% of hull value.", population_affected: "Global supply chains", evidence: "Suez Canal Authority reports daily transits down from 72 to 41 vessels." },
        { sector: "Energy", severity: "high", description: "LNG carriers avoiding the strait tighten European gas balances ahead of winter restocking." },
      ],
      indirect_impact: [
        { sector: "Consumer Prices", severity: "medium", description: "6-9% increase in imported goods costs projected for EU and US retail over six months." },
        { sector: "Automotive", severity: "high", description: "European assembly plants exposed to single-source Asian components face intermittent stoppages." },
      ],
      predictions: [
        { label: "Escalation", confidence: 72 },
        { label: "Diplomatic Resolution", confidence: 18 },
        { label: "Status Quo", confidence: 10 },
      ],
      prediction_reasoning: "Naval escorts deter but cannot close the threat envelope; absent a Gaza ceasefire that removes the Houthis' stated casus belli, the most probable path is continued attrition with periodic spikes.",
      sources_analyzed: ["Reuters", "Bloomberg", "Lloyd's List", "BBC", "Al Jazeera"],
    },
    articles: [
      { source: "Reuters", title: "Houthi attacks push shipping firms to avoid Red Sea despite Navy escorts", url: "#", date: "2026-06-15" },
      { source: "Bloomberg", title: "Red Sea chaos forces a rethink of supply-chain strategy across Europe", url: "#", date: "2026-06-14" },
      { source: "BBC", title: "Why the Houthi attacks are disrupting world trade", url: "#", date: "2026-06-12" },
      { source: "Financial Times", title: "Freight rates double as carriers reroute around Africa", url: "#", date: "2026-06-13" },
    ],
  },
  {
    id: "2", category: "economics", current_status: "developing",
    canonical_title: "Fed Signals Rates Higher for Longer as Inflation Stalls at 3.4%",
    canonical_summary: "The Federal Reserve held rates at 5.25-5.5% and revised down its 2026 cut expectations from three to one. Mortgage rates remain above 7%, suppressing housing starts and consumer credit appetite.",
    importance_score: 84, geography: ["United States"],
    lat: 38.9, lng: -77.0,
    source_bias: { left: 38, center: 40, right: 22 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "FOMC held the policy rate at 5.25-5.5% and the dot plot now shows a single 2026 cut, down from three.", evidence: "June FOMC Summary of Economic Projections." },
        { type: "INFERRED MECHANISM", content: "Higher-for-longer rates keep the 30-year mortgage above 7%, freezing housing turnover and locking in the 'rate-lock' effect.", evidence: "Existing-home sales at a 30-year seasonal low per NAR." },
        { type: "INFERRED MECHANISM", content: "Refinancing costs rise across leveraged corporates with 2027 maturity walls, widening high-yield credit spreads." },
        { type: "SPECULATIVE EFFECT", content: "A prolonged plateau risks a disorderly repricing in commercial real estate, where ~$1.5T of loans mature through 2027." },
      ],
      direct_impact: [
        { sector: "Housing", severity: "high", description: "Mortgage applications down 14% YoY; new construction starts soften in rate-sensitive metros.", population_affected: "~45M US mortgage holders" },
        { sector: "Banking", severity: "medium", description: "Regional banks with CRE concentration face renewed deposit and margin pressure." },
      ],
      indirect_impact: [
        { sector: "Emerging Markets", severity: "medium", description: "A firmer dollar pressures EM currencies and raises dollar-debt servicing costs." },
      ],
      predictions: [
        { label: "One Cut in 2026", confidence: 58 },
        { label: "No Cuts", confidence: 30 },
        { label: "Two+ Cuts", confidence: 12 },
      ],
      prediction_reasoning: "Sticky shelter and services inflation give the Fed little room; a cut likely requires either a clear labour-market crack or a sustained sub-3% core print.",
      sources_analyzed: ["Reuters", "Bloomberg", "WSJ", "Financial Times"],
    },
    articles: [
      { source: "WSJ", title: "Fed holds rates, pares back rate-cut outlook for the year", url: "#", date: "2026-06-16" },
      { source: "Bloomberg", title: "Powell warns inflation progress has 'stalled'", url: "#", date: "2026-06-16" },
      { source: "Financial Times", title: "Higher-for-longer leaves housing market frozen", url: "#", date: "2026-06-15" },
    ],
  },
  {
    id: "3", category: "geopolitics", current_status: "escalating",
    canonical_title: "Taiwan Strait Military Exercises Intensify Ahead of Leadership Transition",
    canonical_summary: "PLA Eastern Theater Command conducted live-fire drills encircling Taiwan. Semiconductor supply chains at risk — TSMC accounts for 92% of advanced chips below 5nm globally.",
    importance_score: 89, geography: ["Taiwan", "China", "South China Sea"],
    lat: 23.7, lng: 120.9,
    source_bias: { left: 28, center: 50, right: 22 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "The PLA conducted its largest Taiwan-encirclement drills since 1996, involving carrier groups, missile units and electronic warfare.", evidence: "Taiwan MND released 24-hour incursion tracks; 38 PLAAF sorties crossed the median line." },
        { type: "INFERRED MECHANISM", content: "TSMC produces 92% of advanced logic below 5nm; any blockade scenario triggers immediate global allocation rationing.", evidence: "TrendForce capacity data; no near-term substitute fabs at node parity." },
        { type: "SPECULATIVE EFFECT", content: "A sustained quarantine could halt global AI-accelerator and premium-handset production within one inventory cycle (3-6 months)." },
      ],
      direct_impact: [
        { sector: "Semiconductors", severity: "critical", description: "Scenario modelling shows near-complete advanced-node stoppage within weeks of a kinetic escalation.", population_affected: "Global electronics supply", evidence: "Rhodium Group estimates a blockade would remove ~$2T of annual economic activity." },
      ],
      indirect_impact: [
        { sector: "Technology", severity: "high", description: "Apple, NVIDIA and AMD would exhaust advanced-node inventories within 4-6 months." },
        { sector: "Defence", severity: "medium", description: "Allied posture shifts; Japan and the Philippines accelerate basing and munitions stockpiling." },
      ],
      predictions: [
        { label: "Continued Drills", confidence: 52 },
        { label: "De-escalation", confidence: 33 },
        { label: "Kinetic Conflict", confidence: 15 },
      ],
      prediction_reasoning: "Coercion-without-war remains Beijing's lowest-cost option; an outright blockade carries severe economic blowback for China itself, making gray-zone pressure the modal outcome.",
      sources_analyzed: ["Reuters", "Financial Times", "Nikkei", "BBC"],
    },
    articles: [
      { source: "Reuters", title: "China's drills around Taiwan signal a new normal in strait tensions", url: "#", date: "2026-06-14" },
      { source: "Financial Times", title: "TSMC's Taiwan exposure puts the tech world on edge", url: "#", date: "2026-06-13" },
      { source: "Al Jazeera", title: "Beijing frames exercises as response to 'separatist provocations'", url: "#", date: "2026-06-13" },
    ],
  },
  {
    id: "4", category: "climate", current_status: "developing",
    canonical_title: "Amazon Basin Records Worst Drought in 45 Years",
    canonical_summary: "River levels 60% below seasonal average. Brazilian soy harvest projected down 38%. Global feed-grain prices rising — downstream pressure on meat, dairy and processed food worldwide.",
    importance_score: 76, geography: ["Brazil", "Amazon Basin", "South America"],
    lat: -3.5, lng: -60.0,
    source_bias: { left: 55, center: 32, right: 13 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Rio Negro at Manaus hit its lowest level since records began in 1902; major tributaries are non-navigable.", evidence: "Brazilian Geological Survey hydrological bulletin." },
        { type: "INFERRED MECHANISM", content: "Barge transport of soy and grain to export terminals collapses, stranding harvest inland and lifting freight differentials.", evidence: "CONAB cut its export forecast; Santos basis blew out." },
        { type: "SPECULATIVE EFFECT", content: "Sustained feed-grain tightness flows through to global meat and dairy prices over two to three quarters." },
      ],
      direct_impact: [
        { sector: "Agriculture", severity: "high", description: "Soy harvest projected down 38%; hydropower output curtailed across the basin.", population_affected: "30M+ in affected states" },
      ],
      indirect_impact: [
        { sector: "Food Prices", severity: "medium", description: "Feed-grain costs pressure protein and processed-food prices in import-dependent markets." },
        { sector: "Energy", severity: "medium", description: "Hydropower shortfall forces Brazil onto costlier thermal generation, widening fiscal subsidy needs." },
      ],
      predictions: [
        { label: "Prolonged Drought", confidence: 61 },
        { label: "Seasonal Recovery", confidence: 39 },
      ],
      prediction_reasoning: "A decaying El Niño plus deforestation-driven rainfall suppression skews the balance toward a longer dry anomaly than the historical median.",
      sources_analyzed: ["Guardian", "Reuters", "Carbon Brief"],
    },
    articles: [
      { source: "Guardian", title: "Amazon rivers fall to record lows as drought chokes the basin", url: "#", date: "2026-06-11" },
      { source: "Reuters", title: "Brazil soy export forecast cut as barges run aground", url: "#", date: "2026-06-10" },
    ],
  },
  {
    id: "5", category: "technology", current_status: "developing",
    canonical_title: "EU AI Act Enforcement Begins — Compliance Wave Hits Tech Sector",
    canonical_summary: "High-risk AI systems must meet transparency and audit requirements by August. US firms face fines up to €35M or 7% of global turnover for non-compliance.",
    importance_score: 72, geography: ["European Union", "Global"],
    lat: 50.8, lng: 4.4,
    source_bias: { left: 42, center: 44, right: 14 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "The AI Act's high-risk obligations and GPAI transparency rules enter force, with penalties up to 7% of global turnover.", evidence: "Official Journal of the EU; AI Office guidance published." },
        { type: "INFERRED MECHANISM", content: "Foundation-model providers must publish training-data summaries and conformity documentation, raising compliance overhead.", evidence: "Major labs stood up dedicated EU compliance teams." },
        { type: "SPECULATIVE EFFECT", content: "A 'Brussels effect' could make EU documentation standards the de-facto global baseline for model governance." },
      ],
      direct_impact: [
        { sector: "Technology", severity: "medium", description: "Compliance costs rise materially for high-risk deployers in hiring, credit and biometrics.", population_affected: "EU enterprise software market" },
      ],
      indirect_impact: [
        { sector: "Startups", severity: "medium", description: "Documentation burden disproportionately affects smaller European AI firms versus incumbents." },
      ],
      predictions: [
        { label: "Phased Enforcement", confidence: 64 },
        { label: "Strict Early Fines", confidence: 22 },
        { label: "Major Delay", confidence: 14 },
      ],
      prediction_reasoning: "Regulators historically open with guidance and warnings before headline fines; expect a grace-period posture through the first compliance cycle.",
      sources_analyzed: ["Reuters", "Financial Times", "Politico"],
    },
    articles: [
      { source: "Politico", title: "EU AI Act obligations kick in — what changes for Big Tech", url: "#", date: "2026-06-09" },
      { source: "Financial Times", title: "Compliance scramble as AI rulebook takes effect", url: "#", date: "2026-06-08" },
    ],
  },
  {
    id: "6", category: "health", current_status: "stable",
    canonical_title: "WHO Declares Mpox Variant PHEIC — Travel Advisories Issued",
    canonical_summary: "A new clade of mpox with higher transmissibility prompted a Public Health Emergency of International Concern. 14 countries issued travel advisories; vaccine supply constrained.",
    importance_score: 68, geography: ["DRC", "Central Africa", "Global"],
    lat: -4.3, lng: 15.3,
    source_bias: { left: 18, center: 64, right: 18 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "WHO declared a PHEIC after sustained human-to-human transmission of clade Ib across multiple provinces.", evidence: "WHO Emergency Committee statement." },
        { type: "INFERRED MECHANISM", content: "Vaccine doses are concentrated in high-income stockpiles, leaving the outbreak epicentre under-supplied.", evidence: "Gavi and Africa CDC flagged a doses gap of several million." },
        { type: "SPECULATIVE EFFECT", content: "Without rapid dose-sharing, regional spread could seed sustained transmission chains in neighbouring states." },
      ],
      direct_impact: [
        { sector: "Public Health", severity: "high", description: "Strained clinics in the DRC; contact-tracing capacity overwhelmed in affected provinces.", population_affected: "Central Africa" },
      ],
      indirect_impact: [
        { sector: "Travel", severity: "low", description: "Advisories modestly dent regional tourism and conference bookings." },
      ],
      predictions: [
        { label: "Regional Containment", confidence: 55 },
        { label: "Wider Spread", confidence: 35 },
        { label: "Rapid Control", confidence: 10 },
      ],
      prediction_reasoning: "Containment hinges on the speed of dose-sharing; historical donor lag argues for a drawn-out regional fight rather than swift control.",
      sources_analyzed: ["Reuters", "BBC", "Al Jazeera"],
    },
    articles: [
      { source: "BBC", title: "WHO declares mpox a global health emergency", url: "#", date: "2026-06-07" },
      { source: "Reuters", title: "Vaccine shortfall hampers mpox response in Central Africa", url: "#", date: "2026-06-06" },
    ],
  },
  {
    id: "7", category: "policy", current_status: "developing",
    canonical_title: "US Tariff Package on Chinese EVs and Solar Panels Takes Effect",
    canonical_summary: "100% tariffs on Chinese EVs and 50% on solar panels reshape clean-energy supply chains. Domestic US solar install costs projected to rise 18-24% over 18 months.",
    importance_score: 79, geography: ["United States", "China"],
    lat: 37.8, lng: -96.0,
    source_bias: { left: 20, center: 34, right: 46 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Section 301 tariffs of 100% on Chinese EVs and 50% on solar cells entered force.", evidence: "USTR final determination; effective date confirmed in Federal Register." },
        { type: "INFERRED MECHANISM", content: "Near-term US solar-install costs rise as Chinese cell/module pricing advantage is offset, pending domestic capacity ramp.", evidence: "Wood Mackenzie cost-curve modelling." },
        { type: "SPECULATIVE EFFECT", content: "Trade diversion through Southeast Asian assembly hubs may blunt the tariff's intended re-shoring effect." },
      ],
      direct_impact: [
        { sector: "Clean Energy", severity: "high", description: "Utility-scale solar developers face higher module costs and project-timeline risk.", population_affected: "US renewables buildout" },
      ],
      indirect_impact: [
        { sector: "Trade", severity: "medium", description: "Beijing signals retaliatory measures on US agricultural and aerospace exports." },
      ],
      predictions: [
        { label: "Trade Diversion", confidence: 50 },
        { label: "Domestic Reshoring", confidence: 32 },
        { label: "Retaliation Spiral", confidence: 18 },
      ],
      prediction_reasoning: "Tariffs reliably shift sourcing geography faster than they build domestic capacity; expect transshipment routes to absorb much of the impact within a year.",
      sources_analyzed: ["WSJ", "Reuters", "Bloomberg"],
    },
    articles: [
      { source: "WSJ", title: "US slaps 100% tariff on Chinese EVs in clean-energy push", url: "#", date: "2026-06-12" },
      { source: "Reuters", title: "Solar developers warn of cost spike from new tariffs", url: "#", date: "2026-06-11" },
    ],
  },
  {
    id: "8", category: "security", current_status: "escalating",
    canonical_title: "Critical Infrastructure Cyberattacks Surge Across NATO Members",
    canonical_summary: "Coordinated intrusions targeting power grids and water systems in Poland, Germany and the Baltics attributed to state-sponsored groups. NATO Article 5 cyber-threshold debate intensifies.",
    importance_score: 83, geography: ["NATO", "Eastern Europe", "Baltic States"],
    lat: 52.2, lng: 21.0,
    source_bias: { left: 25, center: 52, right: 23 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Multiple utilities reported coordinated OT-network intrusions; two caused temporary regional outages.", evidence: "ENISA incident bulletin; national CERT advisories in PL, DE, LT." },
        { type: "INFERRED MECHANISM", content: "Pre-positioning in operational-technology networks gives adversaries latent disruption capability ahead of any crisis.", evidence: "TTPs consistent with previously attributed state-sponsored 'living-off-the-land' tradecraft." },
        { type: "SPECULATIVE EFFECT", content: "A high-impact grid attack could force a precedent-setting test of NATO's cyber Article 5 threshold." },
      ],
      direct_impact: [
        { sector: "Energy & Utilities", severity: "high", description: "Grid operators accelerate OT segmentation and emergency-response investment.", population_affected: "Eastern European utilities" },
      ],
      indirect_impact: [
        { sector: "Insurance", severity: "medium", description: "Cyber-reinsurance pricing for critical-infrastructure operators repriced sharply higher." },
      ],
      predictions: [
        { label: "Continued Probing", confidence: 60 },
        { label: "Major Disruptive Attack", confidence: 25 },
        { label: "De-escalation", confidence: 15 },
      ],
      prediction_reasoning: "Gray-zone cyber pressure offers deniability and low cost; expect sustained intrusion campaigns short of an unambiguous Article 5 trigger.",
      sources_analyzed: ["Reuters", "BBC", "Financial Times"],
    },
    articles: [
      { source: "Reuters", title: "Coordinated cyberattacks hit European grids, officials say", url: "#", date: "2026-06-13" },
      { source: "Financial Times", title: "NATO weighs response as infrastructure intrusions mount", url: "#", date: "2026-06-12" },
    ],
  },
  {
    id: "9", category: "economics", current_status: "stable",
    canonical_title: "OPEC+ Extends Production Cuts Through Q3, Brent Holds Above $85",
    canonical_summary: "Saudi Arabia and Russia extended voluntary cuts of 1.65M barrels/day. Fuel costs remain elevated — aviation and logistics absorbing margin compression.",
    importance_score: 71, geography: ["Saudi Arabia", "Russia", "Global"],
    lat: 24.7, lng: 46.7,
    source_bias: { left: 14, center: 46, right: 40 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "OPEC+ rolled over voluntary cuts of ~1.65M b/d through Q3, keeping a tight physical balance.", evidence: "OPEC ministerial communiqué." },
        { type: "INFERRED MECHANISM", content: "Constrained supply keeps Brent above $85, sustaining elevated jet-fuel and diesel cracks.", evidence: "ICE futures curve; refining-margin data." },
        { type: "SPECULATIVE EFFECT", content: "Persistent high crude risks reviving headline inflation just as central banks contemplate easing." },
      ],
      direct_impact: [
        { sector: "Aviation & Logistics", severity: "medium", description: "Carriers face fuel-cost headwinds, pressuring fares and freight margins.", population_affected: "Global transport" },
      ],
      indirect_impact: [
        { sector: "Inflation", severity: "medium", description: "Energy stickiness complicates the disinflation narrative in import-dependent economies." },
      ],
      predictions: [
        { label: "Cuts Extended Again", confidence: 54 },
        { label: "Gradual Unwind", confidence: 34 },
        { label: "Price War", confidence: 12 },
      ],
      prediction_reasoning: "Fiscal break-evens in key producers favour defending price over volume, biasing toward continued discipline.",
      sources_analyzed: ["Reuters", "Bloomberg", "WSJ"],
    },
    articles: [
      { source: "Bloomberg", title: "OPEC+ extends output cuts, oil holds firm above $85", url: "#", date: "2026-06-10" },
      { source: "Reuters", title: "Saudi-Russia alliance keeps a tight grip on crude supply", url: "#", date: "2026-06-09" },
    ],
  },
  {
    id: "10", category: "geopolitics", current_status: "developing",
    canonical_title: "Pakistan-India Border Tensions Spike After Kashmir Incident",
    canonical_summary: "Cross-border exchange of fire following a militant attack in Jammu. Both sides recalled ambassadors. Regional escalation-risk assessment raised to elevated.",
    importance_score: 77, geography: ["Pakistan", "India", "Kashmir"],
    lat: 33.7, lng: 73.0,
    source_bias: { left: 30, center: 44, right: 26 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Militant attack in Jammu killed security personnel; both militaries reported LoC exchanges.", evidence: "Indian Army and ISPR statements." },
        { type: "INFERRED MECHANISM", content: "Diplomatic downgrade (ambassador recall, trade suspension) narrows off-ramps and raises miscalculation risk.", evidence: "Bilateral trade and visa channels suspended." },
        { type: "SPECULATIVE EFFECT", content: "Nuclear-doctrine ambiguity means even limited conventional escalation carries outsized tail risk." },
      ],
      direct_impact: [
        { sector: "Security", severity: "high", description: "Force posture raised along the Line of Control; civilian displacement in border districts.", population_affected: "Kashmir border communities" },
      ],
      indirect_impact: [
        { sector: "Markets", severity: "low", description: "Regional equity and currency volatility ticks up on escalation headlines." },
      ],
      predictions: [
        { label: "Contained Standoff", confidence: 62 },
        { label: "Limited Clashes", confidence: 28 },
        { label: "Broad Escalation", confidence: 10 },
      ],
      prediction_reasoning: "Both capitals retain strong incentives to cap escalation below the nuclear threshold; precedent favours a tense but bounded standoff.",
      sources_analyzed: ["Reuters", "BBC", "Times of India", "NDTV"],
    },
    articles: [
      { source: "Times of India", title: "Tensions flare along LoC after deadly Jammu attack", url: "#", date: "2026-06-14" },
      { source: "Reuters", title: "India, Pakistan recall envoys as Kashmir tensions rise", url: "#", date: "2026-06-13" },
      { source: "BBC", title: "What's behind the latest India-Pakistan flare-up", url: "#", date: "2026-06-13" },
    ],
  },
  {
    id: "11", category: "conflict", current_status: "escalating",
    canonical_title: "Russia-Ukraine Front Line Shifts as Summer Offensive Opens",
    canonical_summary: "Renewed assaults in the Donbas and strikes on energy infrastructure mark the opening of a summer campaign. Western air-defence resupply timing becomes decisive.",
    importance_score: 88, geography: ["Ukraine", "Russia", "Donbas"],
    lat: 49.0, lng: 32.0,
    source_bias: { left: 33, center: 47, right: 20 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Russian forces opened multi-axis assaults while mass drone/missile strikes targeted Ukraine's grid.", evidence: "ISW daily assessments; Ukrenergo outage reports." },
        { type: "INFERRED MECHANISM", content: "Interceptor depletion outpaces resupply, forcing triage of which cities and assets receive air-defence coverage.", evidence: "Reported PAC-3 and IRIS-T magazine constraints." },
        { type: "SPECULATIVE EFFECT", content: "Sustained grid damage ahead of winter could trigger a fresh wave of displacement and EU energy-aid demand." },
      ],
      direct_impact: [
        { sector: "Energy", severity: "high", description: "Repeated strikes degrade generation and transmission ahead of the heating season.", population_affected: "Ukrainian civilians" },
      ],
      indirect_impact: [
        { sector: "Defence Industrial Base", severity: "high", description: "Western munitions stockpiles drawn down, accelerating production-capacity expansion." },
        { sector: "Grain Markets", severity: "medium", description: "Black Sea corridor risk premia resurface, nudging wheat futures higher." },
      ],
      predictions: [
        { label: "Grinding Attrition", confidence: 64 },
        { label: "Significant Territory Change", confidence: 22 },
        { label: "Ceasefire Talks", confidence: 14 },
      ],
      prediction_reasoning: "Defensive depth and resupply uncertainty point to incremental, costly movement rather than decisive breakthrough on either side.",
      sources_analyzed: ["Reuters", "Financial Times", "BBC"],
    },
    articles: [
      { source: "Reuters", title: "Russia opens summer offensive as strikes pound Ukraine's grid", url: "#", date: "2026-06-15" },
      { source: "Financial Times", title: "Air-defence shortages force hard choices for Kyiv", url: "#", date: "2026-06-14" },
    ],
  },
  {
    id: "12", category: "economics", current_status: "developing",
    canonical_title: "China Property Sector Debt Crisis Enters New Phase",
    canonical_summary: "Another major developer misses offshore coupon payments. Local-government financing vehicles face refinancing strain, weighing on consumer confidence and steel demand.",
    importance_score: 80, geography: ["China", "Shanghai"],
    lat: 31.2, lng: 121.5,
    source_bias: { left: 26, center: 52, right: 22 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "A top-10 developer missed offshore coupons; new-home sales in tier-3 cities remain deeply negative YoY.", evidence: "Exchange filings; China NBS housing data." },
        { type: "INFERRED MECHANISM", content: "Falling land sales squeeze local-government revenue, cascading into LGFV refinancing stress.", evidence: "IMF and rating-agency notes on LGFV maturities." },
        { type: "SPECULATIVE EFFECT", content: "A negative wealth effect from property weakness suppresses household consumption, deepening deflationary pressure." },
      ],
      direct_impact: [
        { sector: "Construction & Steel", severity: "high", description: "Weak starts depress steel and cement demand, pressuring global iron-ore prices.", population_affected: "China property value chain" },
      ],
      indirect_impact: [
        { sector: "Commodities", severity: "medium", description: "Iron-ore and copper sentiment softens on China demand concerns." },
        { sector: "Global Growth", severity: "medium", description: "Subdued Chinese demand weighs on exporter economies from Australia to Germany." },
      ],
      predictions: [
        { label: "Managed Decline", confidence: 58 },
        { label: "Large Stimulus", confidence: 27 },
        { label: "Disorderly Default Wave", confidence: 15 },
      ],
      prediction_reasoning: "Beijing has tools to prevent systemic rupture but appears willing to tolerate a slow deleveraging rather than reflate the bubble.",
      sources_analyzed: ["Bloomberg", "Reuters", "Financial Times", "Nikkei"],
    },
    articles: [
      { source: "Bloomberg", title: "Chinese developer misses payment as property gloom deepens", url: "#", date: "2026-06-11" },
      { source: "Financial Times", title: "LGFV debt strains ripple through China's local economies", url: "#", date: "2026-06-10" },
    ],
  },
  {
    id: "13", category: "climate", current_status: "escalating",
    canonical_title: "Horn of Africa Flash Floods Displace Hundreds of Thousands",
    canonical_summary: "Intense rains following prolonged drought triggered flash floods across Somalia, Ethiopia and Kenya, destroying cropland and displacing communities already facing food insecurity.",
    importance_score: 74, geography: ["Somalia", "Ethiopia", "Kenya", "Horn of Africa"],
    lat: 9.0, lng: 42.0,
    source_bias: { left: 40, center: 48, right: 12 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Flash floods following a strong wet season displaced hundreds of thousands and inundated farmland.", evidence: "OCHA situation reports; IGAD climate bulletin." },
        { type: "INFERRED MECHANISM", content: "Whiplash from drought to flood destroys topsoil and standing crops, compounding chronic food insecurity.", evidence: "FEWS NET acute food-insecurity classification." },
        { type: "SPECULATIVE EFFECT", content: "Sustained displacement could intensify cross-border migration and strain regional aid systems." },
      ],
      direct_impact: [
        { sector: "Humanitarian", severity: "high", description: "Mass displacement and crop loss across multiple countries; cholera risk rises.", population_affected: "Millions across the Horn" },
      ],
      indirect_impact: [
        { sector: "Regional Stability", severity: "medium", description: "Resource and land pressure heightens local conflict and migration risk." },
      ],
      predictions: [
        { label: "Prolonged Humanitarian Crisis", confidence: 66 },
        { label: "Contained Recovery", confidence: 34 },
      ],
      prediction_reasoning: "Underlying vulnerability and funding shortfalls make a quick recovery unlikely; expect a sustained emergency.",
      sources_analyzed: ["Reuters", "Al Jazeera", "BBC"],
    },
    articles: [
      { source: "Al Jazeera", title: "Deadly floods sweep the Horn of Africa after years of drought", url: "#", date: "2026-06-12" },
      { source: "Reuters", title: "Hundreds of thousands displaced as floods hit East Africa", url: "#", date: "2026-06-11" },
    ],
  },
  {
    id: "14", category: "security", current_status: "developing",
    canonical_title: "Myanmar Civil Conflict Expands Toward Key Trade Corridors",
    canonical_summary: "Resistance forces and ethnic armed organisations seized additional towns along the China and Thailand borders, disrupting cross-border trade and rare-earth supply.",
    importance_score: 66, geography: ["Myanmar", "China", "Thailand"],
    lat: 19.7, lng: 96.1,
    source_bias: { left: 34, center: 50, right: 16 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Resistance coalitions captured border towns, severing key junta supply and trade routes.", evidence: "Multiple conflict-monitoring trackers; cross-border trade halts reported." },
        { type: "INFERRED MECHANISM", content: "Disruption hits heavy rare-earth flows from Myanmar mines into Chinese separation facilities.", evidence: "Adamas Intelligence supply-chain notes; China customs anomalies." },
        { type: "SPECULATIVE EFFECT", content: "Prolonged loss of Myanmar feedstock could tighten the global heavy-rare-earth market used in EV and defence magnets." },
      ],
      direct_impact: [
        { sector: "Critical Minerals", severity: "medium", description: "Heavy rare-earth (dysprosium/terbium) feedstock disruption pressures magnet supply chains.", population_affected: "Global magnet manufacturing" },
      ],
      indirect_impact: [
        { sector: "Regional Trade", severity: "medium", description: "Border-trade halts hit Thai and Chinese frontier economies." },
      ],
      predictions: [
        { label: "Continued Resistance Gains", confidence: 56 },
        { label: "Stalemate", confidence: 32 },
        { label: "Junta Counteroffensive", confidence: 12 },
      ],
      prediction_reasoning: "Momentum and terrain favour the resistance at the periphery even as the junta retains the centre; expect further fragmentation.",
      sources_analyzed: ["Reuters", "Nikkei", "Al Jazeera"],
    },
    articles: [
      { source: "Nikkei", title: "Myanmar fighting threatens rare-earth flows to China", url: "#", date: "2026-06-09" },
      { source: "Reuters", title: "Resistance forces seize border towns in Myanmar", url: "#", date: "2026-06-08" },
    ],
  },
  {
    id: "15", category: "policy", current_status: "stable",
    canonical_title: "Mexico Judicial Reform Sparks Constitutional Crisis",
    canonical_summary: "Sweeping changes to elect judges by popular vote drew investor concern over rule of law, weighing on the peso and nearshoring sentiment.",
    importance_score: 63, geography: ["Mexico", "North America"],
    lat: 19.4, lng: -99.1,
    source_bias: { left: 36, center: 46, right: 18 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Constitutional reform to popularly elect judges advanced despite court and bar-association objections.", evidence: "Congressional vote records; Supreme Court statements." },
        { type: "INFERRED MECHANISM", content: "Perceived judicial-independence risk raises the rule-of-law premium investors attach to Mexican assets.", evidence: "Peso weakness and widening sovereign CDS." },
        { type: "SPECULATIVE EFFECT", content: "Uncertainty could slow nearshoring FDI commitments at the margin, blunting a key growth tailwind." },
      ],
      direct_impact: [
        { sector: "Markets", severity: "medium", description: "Peso volatility and equity outflows on governance concerns.", population_affected: "Mexican economy" },
      ],
      indirect_impact: [
        { sector: "Nearshoring", severity: "medium", description: "Manufacturers reassess timelines for new Mexican capacity." },
      ],
      predictions: [
        { label: "Gradual Implementation", confidence: 60 },
        { label: "Partial Rollback", confidence: 25 },
        { label: "Deep Crisis", confidence: 15 },
      ],
      prediction_reasoning: "Strong electoral mandate makes reform durable, but pragmatic adjustments are likely to reassure investors over time.",
      sources_analyzed: ["Reuters", "Bloomberg", "Financial Times"],
    },
    articles: [
      { source: "Reuters", title: "Mexico's judicial overhaul rattles investors and the peso", url: "#", date: "2026-06-10" },
      { source: "Bloomberg", title: "Rule-of-law fears cloud Mexico's nearshoring boom", url: "#", date: "2026-06-09" },
    ],
  },
  {
    id: "16", category: "conflict", current_status: "escalating",
    canonical_title: "Sudan Civil War Pushes Darfur Toward Famine",
    canonical_summary: "Fighting between the army and the RSF intensified around El Fasher as aid access collapsed, with multiple regions verging on famine classification.",
    importance_score: 75, geography: ["Sudan", "Darfur", "Sahel"],
    lat: 13.6, lng: 25.3,
    source_bias: { left: 38, center: 48, right: 14 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Intense fighting around El Fasher blocked humanitarian convoys; IPC analysis flagged famine conditions.", evidence: "IPC famine review committee; UN OCHA access reports." },
        { type: "INFERRED MECHANISM", content: "Siege tactics and looting of aid prevent food delivery to encircled populations.", evidence: "WFP suspended several corridors citing security." },
        { type: "SPECULATIVE EFFECT", content: "Mass starvation and displacement could destabilise neighbouring Chad and South Sudan." },
      ],
      direct_impact: [
        { sector: "Humanitarian", severity: "critical", description: "Famine-level food insecurity for millions; collapse of health and water systems.", population_affected: "Darfur and beyond" },
      ],
      indirect_impact: [
        { sector: "Regional Stability", severity: "high", description: "Refugee flows strain Chad and the wider Sahel." },
      ],
      predictions: [
        { label: "Worsening Crisis", confidence: 68 },
        { label: "Negotiated Access", confidence: 22 },
        { label: "Ceasefire", confidence: 10 },
      ],
      prediction_reasoning: "With external backers sustaining both sides and aid access weaponised, the humanitarian trajectory is sharply negative.",
      sources_analyzed: ["Reuters", "Al Jazeera", "BBC"],
    },
    articles: [
      { source: "Al Jazeera", title: "Famine looms in Darfur as Sudan's war chokes aid", url: "#", date: "2026-06-13" },
      { source: "Reuters", title: "Aid agencies warn of catastrophe around El Fasher", url: "#", date: "2026-06-12" },
    ],
  },
  {
    id: "17", category: "economics", current_status: "developing",
    canonical_title: "Argentina's Shock Therapy Tames Inflation but Tests Patience",
    canonical_summary: "Aggressive fiscal austerity and deregulation pushed monthly inflation sharply lower, but a deep recession and rising poverty fuel social tension over the reform programme.",
    importance_score: 64, geography: ["Argentina", "South America"],
    lat: -34.6, lng: -58.4,
    source_bias: { left: 30, center: 44, right: 26 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Monthly inflation fell from double digits toward low single digits as the fiscal deficit was slashed.", evidence: "INDEC CPI series; primary-balance data." },
        { type: "INFERRED MECHANISM", content: "Subsidy cuts and a weaker peso compress real incomes, deepening recession and raising the poverty rate.", evidence: "UCA poverty estimates; activity-index contraction." },
        { type: "SPECULATIVE EFFECT", content: "If disinflation holds without social rupture, Argentina could regain capital-market access and an IMF upgrade." },
      ],
      direct_impact: [
        { sector: "Macro", severity: "high", description: "Sharp disinflation alongside a steep output contraction and rising poverty.", population_affected: "Argentine households" },
      ],
      indirect_impact: [
        { sector: "Emerging-Market Debt", severity: "medium", description: "Bond spreads tighten as investors reward fiscal credibility." },
      ],
      predictions: [
        { label: "Disinflation Holds", confidence: 52 },
        { label: "Social Backlash Forces Reversal", confidence: 30 },
        { label: "Currency Crisis", confidence: 18 },
      ],
      prediction_reasoning: "Early inflation wins buy political capital, but the durability of austerity hinges on whether real wages recover before patience runs out.",
      sources_analyzed: ["Bloomberg", "Reuters", "Financial Times"],
    },
    articles: [
      { source: "Financial Times", title: "Argentina's austerity gamble starts to bend inflation", url: "#", date: "2026-06-08" },
      { source: "Bloomberg", title: "Recession deepens as Argentina's reforms bite", url: "#", date: "2026-06-07" },
    ],
  },
  {
    id: "18", category: "security", current_status: "developing",
    canonical_title: "Sahel Coup Belt Realigns as Juntas Deepen Russia Ties",
    canonical_summary: "Mali, Burkina Faso and Niger formalised a security pact and expanded cooperation with Russian paramilitaries, accelerating Western withdrawal and reshaping uranium and gold flows.",
    importance_score: 67, geography: ["Mali", "Niger", "Burkina Faso", "Sahel"],
    lat: 13.5, lng: 2.1,
    source_bias: { left: 34, center: 50, right: 16 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "The three juntas formalised a confederation and expanded Russian security cooperation as French and US forces exited.", evidence: "Alliance of Sahel States communiqués; base-withdrawal confirmations." },
        { type: "INFERRED MECHANISM", content: "Realignment shifts control over uranium and gold export routes away from Western partners.", evidence: "Mining-concession reassignments reported." },
        { type: "SPECULATIVE EFFECT", content: "A security vacuum could let jihadist groups expand toward coastal West African states." },
      ],
      direct_impact: [
        { sector: "Critical Minerals", severity: "medium", description: "Uranium supply routes (relevant to French nuclear feedstock) face reorientation.", population_affected: "Sahel resource economies" },
      ],
      indirect_impact: [
        { sector: "Counterterrorism", severity: "high", description: "Reduced Western footprint coincides with rising jihadist activity and southward spread." },
      ],
      predictions: [
        { label: "Deeper Russia Alignment", confidence: 62 },
        { label: "Partial Western Re-engagement", confidence: 23 },
        { label: "Junta Instability", confidence: 15 },
      ],
      prediction_reasoning: "Domestic legitimacy tied to anti-colonial framing locks in the realignment; reversal would require regime change rather than diplomacy.",
      sources_analyzed: ["Reuters", "Al Jazeera", "BBC"],
    },
    articles: [
      { source: "Reuters", title: "Sahel juntas tighten alliance and Russia ties", url: "#", date: "2026-06-09" },
      { source: "Al Jazeera", title: "West loses ground in the Sahel as juntas pivot east", url: "#", date: "2026-06-08" },
    ],
  },
  {
    id: "19", category: "technology", current_status: "developing",
    canonical_title: "Global Chip Subsidy Race Intensifies as Fabs Break Ground",
    canonical_summary: "New advanced-node fabs broke ground across the US, Japan and the EU under competing subsidy regimes, raising questions about future overcapacity and skilled-labour shortages.",
    importance_score: 70, geography: ["United States", "Japan", "European Union"],
    lat: 33.4, lng: -111.9,
    source_bias: { left: 24, center: 56, right: 20 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Subsidised leading-edge fabs advanced in Arizona, Kumamoto and Dresden under CHIPS-style programmes.", evidence: "Company construction milestones; government grant disbursements." },
        { type: "INFERRED MECHANISM", content: "Parallel national buildouts risk synchronised capacity additions that could swing the cycle toward glut.", evidence: "Historical semiconductor capex-cycle patterns." },
        { type: "SPECULATIVE EFFECT", content: "A skilled-labour shortfall and yield ramp could delay output, blunting near-term supply-security gains." },
      ],
      direct_impact: [
        { sector: "Semiconductors", severity: "medium", description: "Geographic diversification of advanced capacity reduces single-point Taiwan dependence over time.", population_affected: "Global tech supply chain" },
      ],
      indirect_impact: [
        { sector: "Labour Markets", severity: "medium", description: "Competition for fab engineers and technicians tightens specialised labour markets." },
      ],
      predictions: [
        { label: "Gradual Diversification", confidence: 58 },
        { label: "Overcapacity Glut", confidence: 24 },
        { label: "Persistent Delays", confidence: 18 },
      ],
      prediction_reasoning: "Diversification is real but slow; node-leading volume remains concentrated for years, so supply-security benefits arrive gradually.",
      sources_analyzed: ["Nikkei", "Reuters", "WSJ"],
    },
    articles: [
      { source: "Nikkei", title: "Subsidised fabs race to break ground across three continents", url: "#", date: "2026-06-07" },
      { source: "WSJ", title: "Chip subsidy boom raises overcapacity questions", url: "#", date: "2026-06-06" },
    ],
  },
  {
    id: "20", category: "climate", current_status: "developing",
    canonical_title: "West Antarctic Ice Shelf Shows Accelerated Thinning",
    canonical_summary: "New satellite data revealed faster-than-expected basal melt of a key buttressing ice shelf, raising medium-term sea-level-rise projections for coastal megacities.",
    importance_score: 69, geography: ["Antarctica", "Global"],
    lat: -75.0, lng: -100.0,
    source_bias: { left: 52, center: 36, right: 12 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Satellite altimetry shows accelerated basal melt of a buttressing shelf in the Amundsen Sea sector.", evidence: "Peer-reviewed cryosphere study; ESA CryoSat data." },
        { type: "INFERRED MECHANISM", content: "Loss of buttressing speeds glacier discharge, shifting sea-level-rise projections upward at the margin.", evidence: "Ice-sheet model ensemble revisions." },
        { type: "SPECULATIVE EFFECT", content: "Higher central sea-level estimates raise long-run adaptation and insurance costs for coastal megacities." },
      ],
      direct_impact: [
        { sector: "Climate Risk", severity: "medium", description: "Upward revision to medium-term sea-level-rise central estimates.", population_affected: "Coastal populations worldwide" },
      ],
      indirect_impact: [
        { sector: "Insurance & Real Estate", severity: "medium", description: "Coastal property and reinsurance pricing incorporate higher long-run flood risk." },
      ],
      predictions: [
        { label: "Continued Acceleration", confidence: 57 },
        { label: "Stabilisation", confidence: 28 },
        { label: "Rapid Collapse Signal", confidence: 15 },
      ],
      prediction_reasoning: "Ocean-heat trends point to continued melt, though the timing of any nonlinear collapse remains deeply uncertain.",
      sources_analyzed: ["Guardian", "Carbon Brief", "Reuters"],
    },
    articles: [
      { source: "Guardian", title: "Key Antarctic ice shelf thinning faster than models predicted", url: "#", date: "2026-06-05" },
      { source: "Carbon Brief", title: "What accelerated Amundsen melt means for sea-level rise", url: "#", date: "2026-06-04" },
    ],
  },
  {
    id: "21", category: "geopolitics", current_status: "developing",
    canonical_title: "Venezuela-Guyana Essequibo Dispute Reignites Over Oil Block",
    canonical_summary: "Caracas escalated claims over the oil-rich Essequibo region following new offshore licensing by Guyana, drawing in regional mediators and oil-major operators.",
    importance_score: 65, geography: ["Venezuela", "Guyana", "South America"],
    lat: 6.8, lng: -58.2,
    source_bias: { left: 28, center: 50, right: 22 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Venezuela renewed sovereignty claims over Essequibo after Guyana auctioned new offshore blocks.", evidence: "Government statements; ICJ proceedings; licensing-round records." },
        { type: "INFERRED MECHANISM", content: "Uncertainty raises operating risk for oil majors developing Guyana's prolific offshore basin.", evidence: "Operator risk disclosures; insurance-premium commentary." },
        { type: "SPECULATIVE EFFECT", content: "A serious escalation could disrupt one of the world's fastest-growing new oil-supply sources." },
      ],
      direct_impact: [
        { sector: "Energy", severity: "medium", description: "Heightened political risk around fast-ramping Guyanese offshore output.", population_affected: "Guyana oil sector" },
      ],
      indirect_impact: [
        { sector: "Regional Diplomacy", severity: "medium", description: "Brazil and CARICOM step up mediation to prevent escalation." },
      ],
      predictions: [
        { label: "Diplomatic Containment", confidence: 64 },
        { label: "Sustained Tension", confidence: 26 },
        { label: "Military Escalation", confidence: 10 },
      ],
      prediction_reasoning: "Regional mediation and the costs of conflict favour managed tension over kinetic escalation, despite periodic rhetoric.",
      sources_analyzed: ["Reuters", "Bloomberg", "BBC"],
    },
    articles: [
      { source: "Reuters", title: "Venezuela presses Essequibo claim after Guyana oil auction", url: "#", date: "2026-06-06" },
      { source: "Bloomberg", title: "Border row clouds Guyana's offshore oil boom", url: "#", date: "2026-06-05" },
    ],
  },
  {
    id: "22", category: "economics", current_status: "stable",
    canonical_title: "Bank of Japan Exits Negative Rates, Yen Carry Trade in Focus",
    canonical_summary: "The BOJ raised rates further out of negative territory and signalled gradual normalisation, prompting scrutiny of the multi-trillion-dollar yen carry trade and global liquidity.",
    importance_score: 73, geography: ["Japan", "Global"],
    lat: 35.7, lng: 139.7,
    source_bias: { left: 22, center: 58, right: 20 },
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "The BOJ lifted its policy rate and reduced bond purchases, confirming a normalisation path.", evidence: "BOJ policy statement and outlook report." },
        { type: "INFERRED MECHANISM", content: "Higher yen funding costs threaten the carry trade, where investors borrow cheap yen to buy higher-yielding global assets.", evidence: "Estimates of carry positions running into the trillions of dollars." },
        { type: "SPECULATIVE EFFECT", content: "A rapid yen appreciation could force disorderly carry-trade unwinds and bouts of global risk-asset volatility." },
      ],
      direct_impact: [
        { sector: "FX & Rates", severity: "medium", description: "Yen strengthens; Japanese government-bond yields rise off historic lows.", population_affected: "Global macro investors" },
      ],
      indirect_impact: [
        { sector: "Global Liquidity", severity: "high", description: "Carry-trade sensitivity raises the risk of episodic cross-asset volatility spikes." },
      ],
      predictions: [
        { label: "Gradual Normalisation", confidence: 60 },
        { label: "Volatile Unwind", confidence: 28 },
        { label: "Policy Reversal", confidence: 12 },
      ],
      prediction_reasoning: "The BOJ will move cautiously to avoid market disruption, but positioning makes occasional sharp unwinds likely along the path.",
      sources_analyzed: ["Bloomberg", "Reuters", "Nikkei", "Financial Times"],
    },
    articles: [
      { source: "Nikkei", title: "BOJ raises rates again, charts course away from easy money", url: "#", date: "2026-06-15" },
      { source: "Bloomberg", title: "Yen carry trade in spotlight as BOJ normalises", url: "#", date: "2026-06-14" },
    ],
  },
];

// ─── Derived map nodes ─────────────────────────────────────────────────────────
export const MOCK_NODES = MOCK_EVENTS.map((e) => ({
  id: e.id,
  category: e.category,
  current_status: e.current_status,
  importance_score: e.importance_score,
  title: e.canonical_title,
  lat: e.lat,
  lng: e.lng,
}));

// ─── Causal edges between events ───────────────────────────────────────────────
export const MOCK_EDGES = [
  { source_event_id: "1", target_event_id: "9", weight: 0.7 },   // Red Sea → oil/energy
  { source_event_id: "1", target_event_id: "2", weight: 0.55 },  // Red Sea → US inflation
  { source_event_id: "1", target_event_id: "11", weight: 0.4 },  // Red Sea ↔ wider conflict
  { source_event_id: "3", target_event_id: "12", weight: 0.8 },  // Taiwan → China economy
  { source_event_id: "3", target_event_id: "19", weight: 0.75 }, // Taiwan → chip subsidy race
  { source_event_id: "3", target_event_id: "7", weight: 0.6 },   // Taiwan ↔ US-China tariffs
  { source_event_id: "8", target_event_id: "11", weight: 0.78 }, // Cyberattacks ↔ Russia-Ukraine
  { source_event_id: "11", target_event_id: "9", weight: 0.55 }, // Ukraine → energy
  { source_event_id: "11", target_event_id: "4", weight: 0.35 }, // Ukraine grain ↔ Amazon food
  { source_event_id: "4", target_event_id: "13", weight: 0.5 },  // Amazon ↔ Horn of Africa (climate)
  { source_event_id: "13", target_event_id: "16", weight: 0.45 },// Floods ↔ Sudan famine
  { source_event_id: "2", target_event_id: "7", weight: 0.6 },   // Fed ↔ tariffs
  { source_event_id: "2", target_event_id: "22", weight: 0.5 },  // Fed ↔ BOJ
  { source_event_id: "22", target_event_id: "12", weight: 0.45 },// BOJ carry ↔ China
  { source_event_id: "12", target_event_id: "9", weight: 0.5 },  // China demand ↔ commodities
  { source_event_id: "14", target_event_id: "19", weight: 0.5 }, // Myanmar rare-earths ↔ chips
  { source_event_id: "18", target_event_id: "16", weight: 0.4 }, // Sahel ↔ Sudan instability
  { source_event_id: "7", target_event_id: "19", weight: 0.55 }, // Tariffs ↔ chip/clean-energy
  { source_event_id: "21", target_event_id: "9", weight: 0.4 },  // Essequibo oil ↔ energy
  { source_event_id: "5", target_event_id: "19", weight: 0.4 },  // AI Act ↔ chip race
];

// ─── Detail lookup ─────────────────────────────────────────────────────────────
const BY_ID = Object.fromEntries(MOCK_EVENTS.map((e) => [e.id, e]));

export function getMockEventDetail(eventId) {
  const event = BY_ID[String(eventId)];
  if (event) return event;

  // Unknown id — graceful placeholder so the UI never breaks.
  return {
    id: eventId, category: "geopolitics", current_status: "developing",
    canonical_title: "Intelligence Signal Under Analysis",
    canonical_summary: "Consequence-chain analysis in progress. Connect the backend for live AI-generated intelligence.",
    geography: ["Global"], importance_score: 70,
    consequence_map: {
      consequence_chain: [
        { type: "VERIFIED FACT", content: "Primary signal confirmed across multiple independent source clusters." },
        { type: "INFERRED MECHANISM", content: "Second-order effects propagating through interconnected systems." },
        { type: "SPECULATIVE EFFECT", content: "Long-term consequence trajectory requires further monitoring." },
      ],
      direct_impact: [{ sector: "Analysis Pending", severity: "medium", description: "Live AI consequence chain requires a backend connection." }],
      indirect_impact: [],
      predictions: [{ label: "Developing", confidence: 65 }, { label: "Stable", confidence: 35 }],
    },
    articles: [],
  };
}
