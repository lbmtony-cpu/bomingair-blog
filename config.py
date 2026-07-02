# BOMING Air blog — business + site constants (single source of truth)

BIZ_NAME   = "BOMING Air Conditioning & Heating"
BIZ_SHORT  = "BOMING Air"
PHONE      = "657-275-5855"
PHONE_TEL  = "+16572755855"
EMAIL      = "service@bomingair.com"
MAIN_SITE  = "https://bomingair.com"
BLOG_URL   = "https://blog.bomingair.com"          # GitHub Pages custom domain
CITY_BASE  = "Chino Hills"
REGION     = "Southern California"
STATE      = "CA"
ZIP        = "91709"

# Brand
BRAND_BLUE   = "#0A5CB8"
BRAND_DARK   = "#0b2340"
BRAND_ACCENT = "#f5a623"

# Service-area cities. Weight = SEO winnability (smaller/closer = easier to rank).
# Higher weight -> picked more often. Big competitive cities kept but low weight.
CITIES_WEIGHTED = [
    ("Chino Hills", 5), ("Chino", 5), ("Diamond Bar", 5), ("Walnut", 4),
    ("Rowland Heights", 4), ("Norco", 4), ("Eastvale", 4), ("Yorba Linda", 3),
    ("Brea", 3), ("Montclair", 3), ("Pomona", 3), ("Ontario", 3),
    ("Upland", 2), ("Anaheim Hills", 2), ("Corona", 2), ("Rancho Cucamonga", 2),
    ("Fontana", 1), ("Riverside", 1),
]
CITIES = [c for c, _ in CITIES_WEIGHTED]

# HIGH-INTENT service/problem topics — the easiest to rank + best for leads.
# "{city}" is filled in; these become the page's primary keyword.
SERVICE_TEMPLATES = [
    "AC repair in {city}: signs you need it and what to expect",
    "Emergency AC repair in {city} during a heat wave",
    "AC not cooling in {city}? Common causes and fixes",
    "AC installation and replacement in {city}: a homeowner's guide",
    "Furnace and heating repair in {city} before winter",
    "AC maintenance and tune-ups in {city}: why they pay off",
    "AC blowing warm air in {city}: what it means",
    "Choosing an HVAC contractor in {city}: what to look for",
    "Commercial HVAC service in {city} for local businesses",
    "Ductless mini-split installation in {city}: is it right for you",
]

# Evergreen + seasonal HVAC topic seeds (customer-intent, not industry news)
TOPICS = [
    "Why your AC is running but not cooling — common causes and fixes",
    "AC repair vs. replacement: how to decide when your system fails",
    "How often should you service your AC in the Southern California climate",
    "Pre-summer AC tune-up checklist for SoCal homeowners",
    "How to lower your summer electric bill with a more efficient AC",
    "Signs your furnace needs repair before winter",
    "Improving indoor air quality and reducing allergens at home",
    "Leaky or dirty ductwork: how it wastes cooling and raises bills",
    "Heat pump vs. traditional AC: which is right for a SoCal home",
    "Smart thermostats: are they worth it for cutting cooling costs",
    "How to choose the right size AC system for your home",
    "SEER2 explained: what the new efficiency ratings mean for buyers",
    "The R-410A to R-454B refrigerant change and what it means for you",
    "Commercial HVAC maintenance: keeping your business cool and open",
    "SCE and SoCalGas rebates and financing options for a new HVAC system",
    "Emergency no-cool during a heat wave: what to check before you call",
    "Why your AC freezes up (ice on the unit) and how to stop it",
    "Extending the life of an older AC unit with regular maintenance",
]
