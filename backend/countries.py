"""countries — country name → ISO 3166-1 alpha-2, with the aliases real registers use.

Why this exists as a table rather than a dependency: the API container has no
country library (checked — no pycountry, babel or country_converter), and adding one
for a lookup this small trades a 250-line table for a transitive dependency in every
image. The table is data, not logic, so it cannot rot in the way code does.

Why it needs to be reasonably complete: the register audit reports
``unmapped_country`` when a country has no ISO code, and that finding means "this
site will have a blank public-holiday layer". A thin table would turn that honest
signal into noise — flagging Togo as unmapped when the truth is only that we never
typed it. So the list below is the full set of ISO 3166-1 assigned alpha-2 codes for
sovereign states and inhabited territories.

Lookup is case- and punctuation-insensitive and accepts the names people actually
put in spreadsheets: "USA", "UK", "UAE", "Korea", "Ivory Coast", "Holland". It also
accepts an ISO code passed straight through, since half of all site registers store
"IN" where the header says "Country".
"""

# One line per country: "<ISO2> <canonical name>|<alias>|<alias>…"
_TABLE = """
AD Andorra
AE United Arab Emirates|UAE|U.A.E.|Emirates
AF Afghanistan
AG Antigua and Barbuda
AI Anguilla
AL Albania
AM Armenia
AO Angola
AR Argentina
AS American Samoa
AT Austria
AU Australia
AW Aruba
AX Aland Islands
AZ Azerbaijan
BA Bosnia and Herzegovina|Bosnia
BB Barbados
BD Bangladesh
BE Belgium
BF Burkina Faso
BG Bulgaria
BH Bahrain
BI Burundi
BJ Benin
BL Saint Barthelemy
BM Bermuda
BN Brunei|Brunei Darussalam
BO Bolivia
BQ Bonaire
BR Brazil
BS Bahamas|The Bahamas
BT Bhutan
BW Botswana
BY Belarus
BZ Belize
CA Canada
CD Democratic Republic of the Congo|DR Congo|DRC|Congo-Kinshasa|Congo (Kinshasa)
CF Central African Republic
CG Republic of the Congo|Congo|Congo-Brazzaville|Congo (Brazzaville)
CH Switzerland
CI Cote d'Ivoire|Ivory Coast|Côte d'Ivoire
CK Cook Islands
CL Chile
CM Cameroon
CN China|People's Republic of China|PRC|Mainland China
CO Colombia
CR Costa Rica
CU Cuba
CV Cabo Verde|Cape Verde
CW Curacao|Curaçao
CY Cyprus
CZ Czechia|Czech Republic
DE Germany|Deutschland
DJ Djibouti
DK Denmark
DM Dominica
DO Dominican Republic
DZ Algeria
EC Ecuador
EE Estonia
EG Egypt
EH Western Sahara
ER Eritrea
ES Spain|España
ET Ethiopia
FI Finland
FJ Fiji
FK Falkland Islands
FM Micronesia
FO Faroe Islands
FR France
GA Gabon
GB United Kingdom|UK|U.K.|Great Britain|Britain|England|Scotland|Wales|Northern Ireland
GD Grenada
GE Georgia
GF French Guiana
GG Guernsey
GH Ghana
GI Gibraltar
GL Greenland
GM Gambia|The Gambia
GN Guinea
GP Guadeloupe
GQ Equatorial Guinea
GR Greece
GT Guatemala
GU Guam
GW Guinea-Bissau
GY Guyana
HK Hong Kong|Hong Kong SAR
HN Honduras
HR Croatia
HT Haiti
HU Hungary
ID Indonesia
IE Ireland|Republic of Ireland|Eire
IL Israel
IM Isle of Man
IN India|Bharat
IQ Iraq
IR Iran|Islamic Republic of Iran
IS Iceland
IT Italy
JE Jersey
JM Jamaica
JO Jordan
JP Japan
KE Kenya
KG Kyrgyzstan
KH Cambodia
KI Kiribati
KM Comoros
KN Saint Kitts and Nevis
KP North Korea|Democratic People's Republic of Korea|DPRK
KR South Korea|Korea|Republic of Korea|Korea, South
KW Kuwait
KY Cayman Islands
KZ Kazakhstan
LA Laos|Lao PDR
LB Lebanon
LC Saint Lucia
LI Liechtenstein
LK Sri Lanka
LR Liberia
LS Lesotho
LT Lithuania
LU Luxembourg
LV Latvia
LY Libya
MA Morocco
MC Monaco
MD Moldova
ME Montenegro
MF Saint Martin
MG Madagascar
MH Marshall Islands
MK North Macedonia|Macedonia
ML Mali
MM Myanmar|Burma
MN Mongolia
MO Macao|Macau
MP Northern Mariana Islands
MQ Martinique
MR Mauritania
MS Montserrat
MT Malta
MU Mauritius
MV Maldives
MW Malawi
MX Mexico
MY Malaysia
MZ Mozambique
NA Namibia
NC New Caledonia
NE Niger
NF Norfolk Island
NG Nigeria
NI Nicaragua
NL Netherlands|The Netherlands|Holland
NO Norway
NP Nepal
NR Nauru
NU Niue
NZ New Zealand
OM Oman
PA Panama
PE Peru
PF French Polynesia
PG Papua New Guinea
PH Philippines|The Philippines
PK Pakistan
PL Poland
PM Saint Pierre and Miquelon
PR Puerto Rico
PS Palestine|Palestinian Territory
PT Portugal
PW Palau
PY Paraguay
QA Qatar
RE Reunion|Réunion
RO Romania
RS Serbia
RU Russia|Russian Federation
RW Rwanda
SA Saudi Arabia|KSA|Kingdom of Saudi Arabia
SB Solomon Islands
SC Seychelles
SD Sudan
SE Sweden
SG Singapore
SH Saint Helena
SI Slovenia
SJ Svalbard and Jan Mayen
SK Slovakia
SL Sierra Leone
SM San Marino
SN Senegal
SO Somalia
SR Suriname
SS South Sudan
ST Sao Tome and Principe
SV El Salvador
SX Sint Maarten
SY Syria|Syrian Arab Republic
SZ Eswatini|Swaziland
TC Turks and Caicos Islands
TD Chad
TG Togo
TH Thailand
TJ Tajikistan
TK Tokelau
TL Timor-Leste|East Timor
TM Turkmenistan
TN Tunisia
TO Tonga
TR Turkiye|Turkey|Türkiye
TT Trinidad and Tobago
TV Tuvalu
TW Taiwan|Chinese Taipei
TZ Tanzania
UA Ukraine
UG Uganda
US United States|United States of America|USA|U.S.A.|US|U.S.|America
UY Uruguay
UZ Uzbekistan
VA Vatican City|Holy See
VC Saint Vincent and the Grenadines
VE Venezuela
VG British Virgin Islands
VI United States Virgin Islands|US Virgin Islands
VN Vietnam|Viet Nam
VU Vanuatu
WF Wallis and Futuna
WS Samoa
XK Kosovo
YE Yemen
YT Mayotte
ZA South Africa|RSA
ZM Zambia
ZW Zimbabwe
"""


def _key(s) -> str:
    """Fold a country string to a comparison key: lowercase, alphanumerics only.

    Punctuation is dropped rather than normalised so "U.A.E.", "UAE" and "U A E"
    all land on the same key — spreadsheets are inconsistent in exactly that way.
    """
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _build() -> tuple[dict[str, str], dict[str, str]]:
    to_iso: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for line in _TABLE.strip().splitlines():
        iso, _, names = line.partition(" ")
        parts = [p.strip() for p in names.split("|") if p.strip()]
        canonical[iso] = parts[0]
        to_iso[_key(iso)] = iso
        for name in parts:
            to_iso.setdefault(_key(name), iso)
    return to_iso, canonical


_TO_ISO, CANONICAL_NAME = _build()

# country name (as the customer wrote it) → ISO2, for every name and alias we know.
# Exposed in this shape because the register audit takes a plain mapping, exactly as
# its JavaScript twin takes SAMPLE_COUNTRY_CODES.
ISO_BY_NAME: dict[str, str] = {}
for _line in _TABLE.strip().splitlines():
    _iso, _, _names = _line.partition(" ")
    for _n in _names.split("|"):
        ISO_BY_NAME.setdefault(_n.strip(), _iso)


def to_iso2(country) -> str | None:
    """ISO 3166-1 alpha-2 for a country name, alias or code. None if unrecognised.

    Returns None rather than guessing. A wrong country code silently attaches the
    wrong national holiday calendar to a site, which is worse than no calendar at
    all because nothing on screen says it is wrong.
    """
    return _TO_ISO.get(_key(country))


def audit_country_codes() -> dict[str, str]:
    """The name→ISO mapping in the shape ``registry_audit.audit_register`` expects."""
    return ISO_BY_NAME
