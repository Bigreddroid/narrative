"""Property tests for live OSINT enrichment (network stubbed).
Exercises each keyless provider's parsing with a fake httpx-like client, the
provider registry, and the public `enrich` envelope.
Run from repo root:  python -m backend.services.osint_enrich_test
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.services import osint_enrich as oe

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _Client:
    """Routes by substring of the requested URL → canned payload."""
    def __init__(self, routes):
        self.routes = routes

    async def get(self, url, headers=None):
        for frag, payload in self.routes.items():
            if frag in url:
                return _Resp(payload)
        return _Resp({})

    async def post(self, url, data=None):
        for frag, payload in self.routes.items():
            if frag in url:
                return _Resp(payload)
        return _Resp({})


def run(coro):
    return asyncio.run(coro)


def labels(facts):
    return {f["label"]: f["value"] for f in facts}


# ── ip providers ────────────────────────────────────────────────────────────────
ipf = run(oe._ip_api(_Client({"ip-api.com": {"status": "success", "country": "United States",
    "regionName": "CA", "city": "Mountain View", "as": "AS15169 Google LLC", "isp": "Google",
    "org": "Google Public DNS", "reverse": "dns.google", "proxy": False, "hosting": True}}), "8.8.8.8"))
ok("ip-api: location", "Mountain View" in labels(ipf).get("Location", ""))
ok("ip-api: ASN", "AS15169" in labels(ipf).get("ASN", ""))
ok("ip-api: non-success → []", run(oe._ip_api(_Client({"ip-api.com": {"status": "fail"}}), "x")) == [])

gn = run(oe._greynoise(_Client({"greynoise.io": {"noise": False, "classification": "benign", "name": "Google Public DNS"}}), "8.8.8.8"))
ok("greynoise: classification", "benign" in labels(gn).get("GreyNoise", ""))

iw = run(oe._ipwhois(_Client({"ipwho.is": {"success": True, "type": "IPv4",
    "connection": {"isp": "Google", "asn": 15169}}}), "8.8.8.8"))
ok("ipwho.is: connection", "AS15169" in labels(iw).get("Connection", ""))

rd = run(oe._rdap_ip(_Client({"rdap.org/ip": {"name": "GOOGLE", "country": "US"}}), "8.8.8.8"))
ok("rdap ip: netblock", labels(rd).get("Netblock") == "GOOGLE")

# ── domain providers ──────────────────────────────────────────────────────────
crt = run(oe._crtsh(_Client({"crt.sh": [{"name_value": "example.com\nmail.example.com"}, {"name_value": "*.example.com"}]}), "example.com"))
ok("crt.sh: cert count", any("Certificates" in f["label"] for f in crt))
ok("crt.sh: subdomains (wildcard skipped)", any("Subdomains" in f["label"] for f in crt))

rdd = run(oe._rdap_domain(_Client({"rdap.org/domain": {"events": [
    {"eventAction": "registration", "eventDate": "1997-09-15T00:00:00Z"}],
    "entities": [{"roles": ["registrar"], "vcardArray": [None, [["fn", {}, "text", "MarkMonitor"]]]}]}}), "example.com"))
ok("rdap domain: registrar", labels(rdd).get("Registrar") == "MarkMonitor")
ok("rdap domain: registered date", labels(rdd).get("Registered") == "1997-09-15")

doh = run(oe._doh(_Client({"cloudflare-dns.com": {"Answer": [{"type": 1, "data": "93.184.216.34"}]}}), "example.com"))
ok("doh: A records", "93.184.216.34" in labels(doh).get("A records", ""))

# ── cve providers ──────────────────────────────────────────────────────────────
nvd = run(oe._nvd(_Client({"services.nvd.nist.gov": {"vulnerabilities": [{"cve": {
    "descriptions": [{"lang": "en", "value": "A nasty bug."}],
    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}}]},
    "published": "2024-03-29T00:00:00"}}]}}), "CVE-2024-3094"))
ok("nvd: description", "nasty bug" in labels(nvd).get("Description", ""))
ok("nvd: cvss", "9.8" in labels(nvd).get("CVSS", ""))

circl = run(oe._circl_cve(_Client({"cve.circl.lu": {"cvss": 9.8, "references": ["a", "b"]}}), "CVE-2024-3094"))
ok("circl: cvss", "9.8" in labels(circl).get("CVSS (CIRCL)", ""))

# ── hash + crypto ────────────────────────────────────────────────────────────
mb = run(oe._malwarebazaar(_Client({"mb-api.abuse.ch": {"query_status": "ok", "data": [
    {"file_type": "exe", "signature": "Emotet", "first_seen": "2024-01-01 00:00:00"}]}}), "a" * 64))
ok("malwarebazaar: file type", labels(mb).get("File type") == "exe")
ok("malwarebazaar: family", labels(mb).get("Malware family") == "Emotet")

addr = "0x" + "a" * 40
bc = run(oe._blockchair(_Client({"api.blockchair.com": {"data": {addr: {"address": {"balance": 1000, "transaction_count": 5}}}}}), addr))
ok("blockchair: balance", "1000" in labels(bc).get("Balance", ""))

btc = "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
bi = run(oe._blockchain_info(_Client({"blockchain.info": {"n_tx": 3, "final_balance": 100000000}}), btc))
ok("blockchain.info: btc balance", "1.00000000 BTC" in labels(bi).get("BTC balance", ""))
ok("blockchain.info: skips eth addr", run(oe._blockchain_info(_Client({}), addr)) == [])

# ── registry + envelope ──────────────────────────────────────────────────────
ok("enrichable kinds from registry", oe.ENRICHABLE_KINDS == {"ip", "domain", "cve", "hash", "crypto"})
lhk = oe.live_host_kinds()
ok("live_host_kinds has ip-api", "ip-api.com" in lhk and "ip" in lhk["ip-api.com"])
ok("live_host_kinds has crt.sh domain", lhk.get("crt.sh") == {"domain"})
ok("multiple providers per kind (ip ≥ 3)", sum(1 for p in oe.PROVIDERS if "ip" in p.kinds) >= 3)

non = run(oe.enrich("Jane Doe", "name"))
ok("enrich: non-enrichable kind → empty", non["facts"] == [] and non["kind"] == "name")
ok("enrich: non-enrichable kind → no consequence", non["consequence"] is None)
ok("enrich: empty value → empty", run(oe.enrich("", "ip"))["facts"] == [])

# ── entity → consequence projection (pure, no network) ───────────────────────────
cve_facts = [{"label": "CVSS", "value": "9.8 (CRITICAL)", "source": "nvd.nist.gov"},
             {"label": "Description", "value": "RCE in libfoo.", "source": "nvd.nist.gov"}]
proj = oe.project_consequence("CVE-2024-3094", "cve", cve_facts)
ok("projection: cve maps to cyber category", proj and proj["category"] == "cyber")
ok("projection: cvss 9.8 → importance 98 + critical severity",
   proj["importance"] == 98 and proj["severity"] == "critical")
ok("projection: runs the CPE (direct impact present)", len(proj["map"]["direct_impact"]) >= 1)
ok("projection: CPE includes an escalation prediction", proj["map"]["prediction_score"] > 0)

hash_base = oe.project_consequence("a" * 64, "hash", [{"label": "File type", "value": "exe", "source": "x"}])
hash_fam = oe.project_consequence("a" * 64, "hash",
    [{"label": "Malware family", "value": "Emotet", "source": "x"}])
ok("projection: named malware family raises importance",
   hash_fam["importance"] > hash_base["importance"])
ok("projection: crypto maps to sanction", oe.project_consequence("0x" + "a" * 40, "crypto",
   [{"label": "Balance", "value": "1000 wei", "source": "x"}])["category"] == "sanction")
ok("projection: unmapped kind → None", oe.project_consequence("IMO 1234567", "vehicle",
   [{"label": "x", "value": "y", "source": "z"}]) is None)
ok("projection: no facts → None", oe.project_consequence("CVE-2024-3094", "cve", []) is None)

print(f"\nosint_enrich: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
