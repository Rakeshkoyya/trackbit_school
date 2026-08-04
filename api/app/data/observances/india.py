"""The Indian observance corpus — national, regional and state (V1-19).

**What this file is.** The dates an Indian school's year is actually shaped by,
scoped to the states that observe each one, for 2026 and 2027. It is reference
data, curated by a human from named sources, and it is the thing that was
missing when V1-7 shipped: the catalogue tables, the approval sheet, the cost
preview and the what's-on feed were all built and the table had zero rows in it,
so every school saw an empty suggestions queue.

**What it is not.** It is not a claim to be any state's gazette. Three honest
limits, stated here rather than discovered later:

  1. **Movable dates disagree by region, genuinely.** A tithi ending near
     midnight puts Vijayadashami on the 20th in Tamil Nadu and the 21st in
     Kerala — both correct, from the same astronomy. Where the sources I read
     disagreed, the row takes one date and `note` names the other. It is never
     averaged.
  2. **A state's public-holiday list is a yearly executive notification**, not a
     derivable fact. Schools also close for things no list contains (a local
     jatra, an election, a bandh). This corpus gets a school most of the way and
     the admin edits the rest — which is exactly the division `D-57`/`D-79`
     designed for: a suggestion is a prompt to pick a date, never a date.
  3. **`states` is who observes it as a public holiday**, which is not the same
     as who celebrates it. Diwali is celebrated everywhere and is a gazetted
     holiday everywhere, so it is all-India. Chhath is celebrated across the
     Hindi belt and is a *government holiday* in four places, so it names four.
     The feed's job is "will the school be shut / should we mark this", not
     ethnography.

**Extending it.** `FIXED` needs nothing — it generates for any year. Only
`MOVABLE` needs a new block, which is one afternoon with a panchang and the
state notifications, once a year, by the super-admin (`D-60`). That asymmetry is
the whole reason the two are separate structures.
"""

from __future__ import annotations

from .types import (
    ALL_INDIA,
    BENGALI_STATES,
    CHHATH_STATES,
    MAY_DAY_STATES,
    PUNJAB_HARYANA,
    TAMIL_STATES,
    UGADI_STATES,
    Entry,
    Fixed,
    Movable,
    group,
)

# ── provenance (`S-150`) ─────────────────────────────────────────────────────
SRC_NATIONAL = "Constitution of India / MHA — the three national holidays"
SRC_DOPT = "DoPT central government holiday list (gazetted), 2026"
SRC_STATE_DAY = "State Reorganisation Acts / state government — formation days"
SRC_GAZETTE = "State government public-holiday notifications 2026–27 (compiled)"
SRC_PANCHANG_2026 = "drikpanchang.com Indian calendar 2026"
SRC_PANCHANG_2027 = "drikpanchang.com Indian calendar 2027"
SRC_SCHOOL = "Government of India — national observance days (school calendar)"


# ═════════════════════════════════════════════════════════════════════════════
# FIXED — same date every year. Generated for any year, never re-researched.
# ═════════════════════════════════════════════════════════════════════════════

FIXED: list[Fixed] = [
    # ── the three national holidays. Observed in every state without exception,
    # and the only three in the country of which that is true.
    Fixed(1, 26, Entry(
        key="republic-day", name="Republic Day", kind="holiday", prep_days=21,
        states=ALL_INDIA, source=SRC_NATIONAL,
        note="National holiday. Most schools hold a flag hoisting and a parade "
             "rehearsal in the preceding weeks — hence the long lead time.")),
    Fixed(8, 15, Entry(
        key="independence-day", name="Independence Day", kind="holiday", prep_days=21,
        states=ALL_INDIA, source=SRC_NATIONAL,
        note="National holiday. Flag hoisting is usually held on the day even "
             "though the school is otherwise closed.")),
    Fixed(10, 2, Entry(
        key="gandhi-jayanti", name="Gandhi Jayanti", kind="holiday", prep_days=10,
        states=ALL_INDIA, source=SRC_NATIONAL,
        note="National holiday. Also the UN International Day of Non-Violence.")),

    # ── pan-India, fixed-date, gazetted or near-universal
    Fixed(1, 1, Entry(
        key="new-year-day", name="New Year's Day", kind="holiday", prep_days=3,
        states=ALL_INDIA, source=SRC_GAZETTE,
        note="A public holiday in many states and a working day in others; "
             "most schools are on winter break regardless.")),
    Fixed(4, 14, Entry(
        key="ambedkar-jayanti", name="Dr B. R. Ambedkar Jayanti", kind="holiday",
        prep_days=10, states=ALL_INDIA, source=SRC_GAZETTE,
        note="A public holiday in the large majority of states and a central "
             "government holiday since 2015.")),
    Fixed(12, 25, Entry(
        key="christmas", name="Christmas", kind="holiday", prep_days=21,
        states=ALL_INDIA, tradition="Christian", source=SRC_DOPT,
        note="Gazetted holiday nationwide. Many schools also run a celebration "
             "on the last working day before the break — approve that "
             "separately, on its own date (D-79).")),
    Fixed(5, 1, Entry(
        key="may-day", name="May Day / Labour Day", kind="holiday", prep_days=5,
        states=MAY_DAY_STATES, source=SRC_GAZETTE,
        note="A public holiday in these states; a normal working day in much of "
             "the north.")),

    # ── the school observance calendar. These are the dates a school MARKS
    # rather than closes for, and they are the ones the product is best placed
    # to remind anybody about — nobody publishes a school a list of them.
    Fixed(11, 14, Entry(
        key="childrens-day", name="Children's Day (Nehru Jayanti)", kind="observance",
        prep_days=14, states=ALL_INDIA, source=SRC_SCHOOL,
        note="School open. Almost universally marked with a programme.")),
    Fixed(9, 5, Entry(
        key="teachers-day", name="Teachers' Day (Radhakrishnan Jayanti)",
        kind="observance", prep_days=14, states=ALL_INDIA, source=SRC_SCHOOL,
        note="School open. Usually a student-run programme.")),
    Fixed(2, 28, Entry(
        key="national-science-day", name="National Science Day", kind="observance",
        prep_days=21, states=ALL_INDIA, source=SRC_SCHOOL,
        note="Science exhibitions are typically planned three weeks out.")),
    Fixed(9, 14, Entry(
        key="hindi-diwas", name="Hindi Diwas", kind="observance", prep_days=10,
        states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(1, 12, Entry(
        key="national-youth-day", name="National Youth Day (Vivekananda Jayanti)",
        kind="observance", prep_days=10, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(1, 23, Entry(
        key="netaji-jayanti", name="Netaji Subhas Chandra Bose Jayanti",
        kind="observance", prep_days=10,
        states=group("West Bengal", "Odisha", "Assam", "Tripura", "Jharkhand"),
        source=SRC_GAZETTE,
        note="Marked nationwide as Parakram Diwas; a public holiday in these "
             "states.")),
    Fixed(1, 30, Entry(
        key="martyrs-day", name="Martyrs' Day (Gandhi Punyatithi)", kind="observance",
        prep_days=5, states=ALL_INDIA, source=SRC_SCHOOL,
        note="Two minutes' silence at 11:00 is the usual observance.")),
    Fixed(10, 31, Entry(
        key="national-unity-day", name="National Unity Day (Sardar Patel Jayanti)",
        kind="observance", prep_days=10, states=ALL_INDIA, source=SRC_SCHOOL,
        note="A public holiday in Gujarat; an observance elsewhere.")),
    Fixed(11, 26, Entry(
        key="constitution-day", name="Constitution Day", kind="observance",
        prep_days=10, states=ALL_INDIA, source=SRC_SCHOOL,
        note="Schools read the Preamble collectively.")),
    Fixed(8, 29, Entry(
        key="national-sports-day", name="National Sports Day (Dhyan Chand Jayanti)",
        kind="observance", prep_days=21, states=ALL_INDIA, source=SRC_SCHOOL,
        note="Often the anchor for the school's annual sports meet.")),
    Fixed(11, 11, Entry(
        key="national-education-day", name="National Education Day",
        kind="observance", prep_days=10, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(12, 22, Entry(
        key="national-mathematics-day", name="National Mathematics Day (Ramanujan)",
        kind="observance", prep_days=14, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(1, 24, Entry(
        key="national-girl-child-day", name="National Girl Child Day",
        kind="observance", tier="minor", prep_days=7, states=ALL_INDIA,
        source=SRC_SCHOOL)),
    Fixed(6, 19, Entry(
        key="national-reading-day", name="National Reading Day", kind="observance",
        tier="minor", prep_days=10, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(9, 15, Entry(
        key="engineers-day", name="Engineer's Day (Visvesvaraya Jayanti)",
        kind="observance", tier="minor", prep_days=7, states=ALL_INDIA,
        source=SRC_SCHOOL)),
    Fixed(5, 11, Entry(
        key="national-technology-day", name="National Technology Day",
        kind="observance", tier="minor", prep_days=7, states=ALL_INDIA,
        source=SRC_SCHOOL)),
    Fixed(1, 15, Entry(
        key="army-day", name="Army Day", kind="observance", tier="minor",
        prep_days=7, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(10, 8, Entry(
        key="air-force-day", name="Indian Air Force Day", kind="observance",
        tier="minor", prep_days=7, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(12, 4, Entry(
        key="navy-day", name="Indian Navy Day", kind="observance", tier="minor",
        prep_days=7, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(7, 26, Entry(
        key="kargil-vijay-diwas", name="Kargil Vijay Diwas", kind="observance",
        tier="minor", prep_days=7, states=ALL_INDIA, source=SRC_SCHOOL)),
    Fixed(1, 10, Entry(
        key="world-hindi-day", name="World Hindi Day", kind="observance",
        tier="minor", prep_days=7, states=ALL_INDIA, source=SRC_SCHOOL)),

    # ── state formation days. All fixed, all sourced from the reorganisation
    # acts, and the single most reliable block in this file.
    Fixed(11, 1, Entry(
        key="karnataka-rajyotsava", name="Karnataka Rajyotsava", kind="holiday",
        prep_days=14, states=group("Karnataka"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="kerala-piravi", name="Kerala Piravi", kind="holiday", prep_days=14,
        states=group("Kerala"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="andhra-pradesh-formation-day", name="Andhra Pradesh Formation Day",
        kind="holiday", prep_days=14, states=group("Andhra Pradesh"),
        source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="haryana-day", name="Haryana Day", kind="holiday", prep_days=14,
        states=group("Haryana"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="punjab-day", name="Punjab Day", kind="holiday", prep_days=14,
        states=group("Punjab"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="madhya-pradesh-day", name="Madhya Pradesh Foundation Day",
        kind="holiday", prep_days=14, states=group("Madhya Pradesh"),
        source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="chhattisgarh-rajyotsava", name="Chhattisgarh Rajyotsava", kind="holiday",
        prep_days=14, states=group("Chhattisgarh"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="uttar-pradesh-day", name="Uttar Pradesh Diwas", kind="observance",
        prep_days=14, states=group("Uttar Pradesh"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="delhi-formation-day", name="Delhi Formation Day", kind="observance",
        tier="minor", prep_days=7, states=group("Delhi"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="puducherry-liberation-day", name="Puducherry Liberation Day",
        kind="holiday", prep_days=10, states=group("Puducherry"),
        source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="andaman-nicobar-day", name="Andaman and Nicobar Day", kind="observance",
        tier="minor", prep_days=7, states=group("Andaman and Nicobar Islands"),
        source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="chandigarh-day", name="Chandigarh Day", kind="observance", tier="minor",
        prep_days=7, states=group("Chandigarh"), source=SRC_STATE_DAY)),
    Fixed(11, 1, Entry(
        key="lakshadweep-day", name="Lakshadweep Day", kind="observance",
        tier="minor", prep_days=7, states=group("Lakshadweep"),
        source=SRC_STATE_DAY)),
    Fixed(11, 9, Entry(
        key="uttarakhand-day", name="Uttarakhand Foundation Day", kind="holiday",
        prep_days=14, states=group("Uttarakhand"), source=SRC_STATE_DAY)),
    Fixed(11, 15, Entry(
        key="jharkhand-formation-day", name="Jharkhand Formation Day / Birsa Munda Jayanti",
        kind="holiday", prep_days=14,
        states=group("Jharkhand", "West Bengal", "Odisha", "Chhattisgarh",
                     "Madhya Pradesh"),
        source=SRC_STATE_DAY,
        note="Jharkhand's formation day and Birsa Munda's birth anniversary are "
             "the same date; several neighbouring states mark the latter.")),
    Fixed(12, 1, Entry(
        key="nagaland-state-day", name="Nagaland Statehood Day", kind="holiday",
        prep_days=14, states=group("Nagaland"), source=SRC_STATE_DAY)),
    Fixed(12, 2, Entry(
        key="asom-divas", name="Asom Divas (Su-Ka-Pha Divas)", kind="holiday",
        prep_days=14, states=group("Assam"), source=SRC_STATE_DAY)),
    Fixed(12, 19, Entry(
        key="goa-liberation-day", name="Goa Liberation Day", kind="holiday",
        prep_days=14, states=group("Goa"), source=SRC_STATE_DAY)),
    Fixed(5, 30, Entry(
        key="goa-statehood-day", name="Goa Statehood Day", kind="observance",
        tier="minor", prep_days=7, states=group("Goa"), source=SRC_STATE_DAY)),
    Fixed(1, 25, Entry(
        key="himachal-day-statehood", name="Himachal Pradesh Statehood Day",
        kind="observance", tier="minor", prep_days=7,
        states=group("Himachal Pradesh"), source=SRC_STATE_DAY,
        note="Full statehood was granted on 25 January 1971. Himachal Day, the "
             "state's public holiday, is 15 April.")),
    Fixed(4, 15, Entry(
        key="himachal-day", name="Himachal Day", kind="holiday", prep_days=10,
        states=group("Himachal Pradesh"), source=SRC_GAZETTE)),
    Fixed(1, 21, Entry(
        key="manipur-statehood-day", name="Manipur Statehood Day", kind="holiday",
        prep_days=14, states=group("Manipur"), source=SRC_STATE_DAY)),
    Fixed(1, 21, Entry(
        key="meghalaya-statehood-day", name="Meghalaya Statehood Day", kind="holiday",
        prep_days=14, states=group("Meghalaya"), source=SRC_STATE_DAY)),
    Fixed(1, 21, Entry(
        key="tripura-statehood-day", name="Tripura Statehood Day", kind="holiday",
        prep_days=14, states=group("Tripura"), source=SRC_STATE_DAY)),
    Fixed(2, 20, Entry(
        key="arunachal-statehood-day", name="Arunachal Pradesh Statehood Day",
        kind="holiday", prep_days=14, states=group("Arunachal Pradesh"),
        source=SRC_STATE_DAY)),
    Fixed(2, 20, Entry(
        key="mizoram-statehood-day", name="Mizoram Statehood Day", kind="holiday",
        prep_days=14, states=group("Mizoram"), source=SRC_STATE_DAY)),
    Fixed(3, 22, Entry(
        key="bihar-diwas", name="Bihar Diwas", kind="holiday", prep_days=14,
        states=group("Bihar"), source=SRC_STATE_DAY)),
    Fixed(3, 30, Entry(
        key="rajasthan-diwas", name="Rajasthan Diwas", kind="holiday", prep_days=14,
        states=group("Rajasthan"), source=SRC_STATE_DAY)),
    Fixed(4, 1, Entry(
        key="utkal-divas", name="Utkal Divas (Odisha Day)", kind="holiday",
        prep_days=14, states=group("Odisha"), source=SRC_STATE_DAY)),
    Fixed(5, 1, Entry(
        key="maharashtra-din", name="Maharashtra Din", kind="holiday", prep_days=14,
        states=group("Maharashtra"), source=SRC_STATE_DAY)),
    Fixed(5, 1, Entry(
        key="gujarat-din", name="Gujarat Sthapana Din", kind="holiday", prep_days=14,
        states=group("Gujarat"), source=SRC_STATE_DAY)),
    Fixed(5, 16, Entry(
        key="sikkim-statehood-day", name="Sikkim Statehood Day", kind="holiday",
        prep_days=14, states=group("Sikkim"), source=SRC_STATE_DAY)),
    Fixed(6, 2, Entry(
        key="telangana-formation-day", name="Telangana Formation Day", kind="holiday",
        prep_days=14, states=group("Telangana"), source=SRC_STATE_DAY)),
    Fixed(6, 20, Entry(
        key="west-bengal-day", name="Paschim Banga Diwas", kind="observance",
        tier="minor", prep_days=7, states=group("West Bengal"),
        source=SRC_STATE_DAY,
        note="Politically contested and not universally observed — kept at "
             "minor tier so it does not lead a school's feed.")),
    Fixed(7, 18, Entry(
        key="tamil-nadu-day", name="Tamil Nadu Day", kind="observance", tier="minor",
        prep_days=7, states=group("Tamil Nadu"), source=SRC_STATE_DAY)),
    Fixed(10, 26, Entry(
        key="jk-accession-day", name="Accession Day", kind="holiday", prep_days=10,
        states=group("Jammu and Kashmir"), source=SRC_STATE_DAY)),
    Fixed(10, 31, Entry(
        key="ladakh-day", name="Ladakh Day", kind="observance", tier="minor",
        prep_days=7, states=group("Ladakh"), source=SRC_STATE_DAY)),
    Fixed(8, 16, Entry(
        key="puducherry-de-jure-day", name="De Jure Transfer Day", kind="observance",
        tier="minor", prep_days=7, states=group("Puducherry"),
        source=SRC_STATE_DAY)),
    Fixed(1, 26, Entry(
        key="dnh-dd-formation-day", name="Dadra and Nagar Haveli and Daman and Diu Formation Day",
        kind="observance", tier="minor", prep_days=7,
        states=group("Dadra and Nagar Haveli and Daman and Diu"),
        source=SRC_STATE_DAY,
        note="The merged UT was formed on 26 January 2020, so its formation day "
             "shares the date with Republic Day. Both rows exist; the school is "
             "closed for the national holiday either way.")),

    # ── state figures and days on a fixed date
    Fixed(2, 19, Entry(
        key="shivaji-jayanti", name="Chhatrapati Shivaji Maharaj Jayanti",
        kind="holiday", prep_days=14, states=group("Maharashtra"),
        source=SRC_GAZETTE,
        note="Maharashtra observes the Gregorian date; the tithi-based date "
             "falls separately in March and is a second, minor observance.")),
    Fixed(3, 23, Entry(
        key="shaheed-diwas-bhagat-singh", name="Shaheed Diwas (Bhagat Singh)",
        kind="holiday", prep_days=10, states=PUNJAB_HARYANA, source=SRC_GAZETTE)),
    Fixed(4, 11, Entry(
        key="jyotiba-phule-jayanti", name="Mahatma Jyotiba Phule Jayanti",
        kind="holiday", tier="minor", prep_days=7,
        states=group("Maharashtra", "Rajasthan"), source=SRC_GAZETTE)),
    Fixed(4, 5, Entry(
        key="jagjivan-ram-jayanti", name="Babu Jagjivan Ram Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("Telangana", "Andhra Pradesh"),
        source=SRC_GAZETTE)),
    Fixed(4, 21, Entry(
        key="sati-sadhani-divas", name="Sati Sadhani Divas", kind="holiday",
        tier="minor", prep_days=7, states=group("Assam"), source=SRC_GAZETTE)),
    Fixed(4, 23, Entry(
        key="kunwar-singh-jayanti", name="Veer Kunwar Singh Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("Bihar"), source=SRC_GAZETTE)),
    Fixed(1, 2, Entry(
        key="mannam-jayanti", name="Mannam Jayanti", kind="holiday", tier="minor",
        prep_days=7, states=group("Kerala"), source=SRC_GAZETTE)),
    Fixed(1, 31, Entry(
        key="me-dam-me-phi", name="Me-Dam-Me-Phi", kind="holiday", tier="minor",
        prep_days=7, states=group("Assam"), source=SRC_GAZETTE)),
    Fixed(2, 21, Entry(
        key="bir-chilarai-divas", name="Bir Chilarai Divas", kind="holiday",
        tier="minor", prep_days=7, states=group("Assam"), source=SRC_GAZETTE)),
    Fixed(11, 16, Entry(
        key="kartar-singh-sarabha", name="Shaheedi Divas — Kartar Singh Sarabha",
        kind="holiday", tier="minor", prep_days=7, states=group("Punjab"),
        source=SRC_GAZETTE)),
    Fixed(9, 17, Entry(
        key="vishwakarma-puja", name="Vishwakarma Puja", kind="holiday", prep_days=7,
        states=group("West Bengal", "Odisha", "Bihar", "Jharkhand", "Assam"),
        tradition="Hindu", source=SRC_GAZETTE,
        note="Solar-reckoned, so it sits on 17 September in most years — unlike "
             "the lunar festivals in this file.")),
    Fixed(7, 1, Entry(
        key="doctors-day", name="Doctors' Day", kind="holiday", tier="minor",
        prep_days=7, states=group("West Bengal"), source=SRC_GAZETTE)),
    Fixed(12, 26, Entry(
        key="boxing-day", name="Boxing Day", kind="holiday", tier="minor",
        prep_days=5, states=group("Telangana"), tradition="Christian",
        source=SRC_GAZETTE)),
]


# ═════════════════════════════════════════════════════════════════════════════
# MOVABLE — looked up per year. THIS is the block a human extends each year.
# ═════════════════════════════════════════════════════════════════════════════

MOVABLE: dict[int, list[Movable]] = {}

MOVABLE[2026] = [
    # ── January
    Movable("2026-01-13", Entry(
        key="lohri", name="Lohri", prep_days=7, states=PUNJAB_HARYANA,
        tradition="Sikh/Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-01-14", Entry(
        key="makar-sankranti", name="Makar Sankranti / Uttarayan", kind="holiday",
        prep_days=10,
        states=group("Gujarat", "Maharashtra", "Rajasthan", "Madhya Pradesh",
                     "Uttar Pradesh", "Bihar", "Jharkhand", "Odisha", "Telangana",
                     "Andhra Pradesh", "Karnataka"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-01-14", Entry(
        key="pongal", name="Pongal / Thai Pongal", kind="holiday", prep_days=14,
        span_days=4, states=TAMIL_STATES, tradition="Hindu",
        source=SRC_PANCHANG_2026,
        note="Tamil Nadu closes for the four Pongal days; the first is Bhogi.")),
    Movable("2026-01-23", Entry(
        key="vasant-panchami", name="Vasant Panchami / Saraswati Puja", kind="holiday",
        prep_days=10, states=BENGALI_STATES, tradition="Hindu",
        source=SRC_PANCHANG_2026,
        note="A school holiday across the east; marked but not closed elsewhere.")),
    # ── February
    Movable("2026-02-01", Entry(
        key="guru-ravidas-jayanti", name="Guru Ravidas Jayanti", kind="holiday",
        prep_days=7, states=group("Punjab", "Haryana", "Himachal Pradesh",
                                  "Chandigarh", "Uttar Pradesh"),
        tradition="Sikh/Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-02-15", Entry(
        key="maha-shivaratri", name="Maha Shivaratri", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2026)),
    # ── March
    Movable("2026-03-03", Entry(
        key="holika-dahan", name="Holika Dahan / Chhoti Holi", prep_days=7,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-03-04", Entry(
        key="holi", name="Holi", kind="holiday", prep_days=14, states=ALL_INDIA,
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-03-19", Entry(
        key="ugadi", name="Ugadi / Gudi Padwa", kind="holiday", prep_days=14,
        states=UGADI_STATES + ("Maharashtra", "Goa"), tradition="Hindu",
        source=SRC_PANCHANG_2026,
        note="Ugadi in Karnataka, Andhra Pradesh and Telangana; Gudi Padwa in "
             "Maharashtra and Goa. One date, two names.")),
    Movable("2026-03-20", Entry(
        key="cheti-chand", name="Cheti Chand / Jhulelal Jayanti", tier="minor",
        prep_days=7, states=group("Gujarat", "Rajasthan", "Maharashtra"),
        tradition="Hindu (Sindhi)", source=SRC_PANCHANG_2026)),
    Movable("2026-03-20", Entry(
        key="eid-ul-fitr", name="Eid-ul-Fitr / Ramzan Id", kind="holiday",
        prep_days=14, states=ALL_INDIA, tradition="Muslim",
        source=SRC_PANCHANG_2026,
        note="Moon-sighting dependent — several state calendars list 21 March "
             "instead. Confirm locally before locking the date.")),
    Movable("2026-03-26", Entry(
        key="rama-navami", name="Rama Navami", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-03-31", Entry(
        key="mahavir-jayanti", name="Mahavir Jayanti", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Jain", source=SRC_PANCHANG_2026)),
    # ── April
    Movable("2026-04-03", Entry(
        key="good-friday", name="Good Friday", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Christian", source=SRC_PANCHANG_2026)),
    Movable("2026-04-02", Entry(
        key="maundy-thursday", name="Maundy Thursday", kind="holiday", tier="minor",
        prep_days=7, states=group("Kerala", "Goa"), tradition="Christian",
        source=SRC_PANCHANG_2026)),
    Movable("2026-04-05", Entry(
        key="easter", name="Easter Sunday", tier="minor", prep_days=7,
        states=ALL_INDIA, tradition="Christian", source=SRC_PANCHANG_2026)),
    Movable("2026-04-14", Entry(
        key="baisakhi", name="Baisakhi / Vaisakhi", kind="holiday", prep_days=14,
        states=PUNJAB_HARYANA, tradition="Sikh", source=SRC_PANCHANG_2026)),
    Movable("2026-04-14", Entry(
        key="tamil-new-year", name="Puthandu (Tamil New Year)", kind="holiday",
        prep_days=10, states=TAMIL_STATES, tradition="Hindu",
        source=SRC_PANCHANG_2026)),
    Movable("2026-04-14", Entry(
        key="vishu", name="Vishu", kind="holiday", prep_days=10,
        states=group("Kerala"), tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-04-14", Entry(
        key="pohela-boishakh", name="Pohela Boishakh (Bengali New Year)",
        kind="holiday", prep_days=10, states=group("West Bengal", "Tripura"),
        tradition="Hindu", source=SRC_PANCHANG_2026,
        note="Some years fall on 15 April; the Bengali solar reckoning moves.")),
    Movable("2026-04-14", Entry(
        key="bohag-bihu", name="Bohag Bihu (Rongali Bihu)", kind="holiday",
        prep_days=14, span_days=3, states=group("Assam"), tradition="Hindu",
        source=SRC_PANCHANG_2026,
        note="Assam closes for roughly three days.")),
    Movable("2026-04-14", Entry(
        key="maha-vishuva-sankranti", name="Maha Vishuva Sankranti (Pana Sankranti)",
        kind="holiday", tier="minor", prep_days=7, states=group("Odisha"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    # ── May / June
    Movable("2026-05-01", Entry(
        key="buddha-purnima", name="Buddha Purnima", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Buddhist", source=SRC_PANCHANG_2026)),
    Movable("2026-05-27", Entry(
        key="eid-ul-adha", name="Eid-ul-Adha / Bakrid", kind="holiday", prep_days=14,
        states=ALL_INDIA, tradition="Muslim", source=SRC_PANCHANG_2026,
        note="Moon-sighting dependent; may move by a day.")),
    Movable("2026-06-17", Entry(
        key="islamic-new-year", name="Muharram (Islamic New Year)", tier="minor",
        prep_days=7, states=ALL_INDIA, tradition="Muslim",
        source=SRC_PANCHANG_2026)),
    Movable("2026-06-17", Entry(
        key="maharana-pratap-jayanti", name="Maharana Pratap Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("Rajasthan", "Haryana"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-06-26", Entry(
        key="muharram-ashura", name="Muharram (Ashura)", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Muslim", source=SRC_PANCHANG_2026)),
    Movable("2026-06-29", Entry(
        key="kabir-jayanti", name="Sant Kabir Jayanti", kind="holiday", tier="minor",
        prep_days=7, states=group("Punjab", "Haryana", "Bihar", "Uttar Pradesh",
                                  "Chandigarh"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    # ── July / August
    Movable("2026-07-16", Entry(
        key="rath-yatra", name="Jagannath Rath Yatra", kind="holiday", prep_days=14,
        states=group("Odisha", "West Bengal"), tradition="Hindu",
        source=SRC_PANCHANG_2026)),
    Movable("2026-07-29", Entry(
        key="guru-purnima", name="Guru Purnima", kind="observance", prep_days=7,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2026,
        note="Widely marked in schools as a teacher-honouring day.")),
    Movable("2026-08-10", Entry(
        key="bonalu", name="Bonalu", kind="holiday", tier="minor", prep_days=7,
        states=group("Telangana"), tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-08-15", Entry(
        key="parsi-new-year", name="Parsi New Year (Pateti / Navroz)", kind="holiday",
        tier="minor", prep_days=7, states=group("Gujarat", "Maharashtra"),
        tradition="Parsi", source=SRC_GAZETTE,
        note="The Shahenshahi reckoning, which is what the Gujarat and "
             "Maharashtra gazettes use. The Fasli Navroz falls at the March "
             "equinox and is a different observance.")),
    Movable("2026-08-25", Entry(
        key="onam", name="Onam (Thiruvonam)", kind="holiday", prep_days=21,
        span_days=4, states=group("Kerala", "Lakshadweep"), tradition="Hindu",
        source=SRC_GAZETTE,
        note="Kerala closes for four days — First Onam 25 Aug, Thiruvonam "
             "26 Aug, then two more.")),
    Movable("2026-08-26", Entry(
        key="milad-un-nabi", name="Milad-un-Nabi (Eid-e-Milad)", kind="holiday",
        prep_days=10, states=ALL_INDIA, tradition="Muslim",
        source=SRC_PANCHANG_2026)),
    Movable("2026-08-28", Entry(
        key="raksha-bandhan", name="Raksha Bandhan", kind="holiday", prep_days=10,
        states=group("Gujarat", "Rajasthan", "Madhya Pradesh", "Uttar Pradesh",
                     "West Bengal", "Maharashtra", "Haryana", "Delhi"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-08-28", Entry(
        key="narayana-guru-jayanti", name="Sree Narayana Guru Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("Kerala"), tradition="Hindu",
        source=SRC_GAZETTE)),
    # ── September
    Movable("2026-09-04", Entry(
        key="janmashtami", name="Krishna Janmashtami", kind="holiday", prep_days=14,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-09-14", Entry(
        key="ganesh-chaturthi", name="Ganesh Chaturthi / Vinayaka Chavithi",
        kind="holiday", prep_days=21, span_days=2,
        states=group("Maharashtra", "Goa", "Karnataka", "Telangana",
                     "Andhra Pradesh", "Tamil Nadu", "Gujarat"),
        tradition="Hindu", source=SRC_PANCHANG_2026,
        note="Maharashtra and Goa close for longer than the gazetted day.")),
    Movable("2026-09-15", Entry(
        key="nuakhai", name="Nuakhai", kind="holiday", tier="minor", prep_days=10,
        states=group("Odisha"), tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-09-21", Entry(
        key="shankardeva-janmotsav", name="Janmotsav of Srimanta Shankardeva",
        kind="holiday", tier="minor", prep_days=7, states=group("Assam"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-09-22", Entry(
        key="karam-puja", name="Karam Puja", kind="holiday", tier="minor",
        prep_days=7, states=group("Jharkhand", "Odisha", "West Bengal", "Assam",
                                  "Chhattisgarh"),
        tradition="Hindu (tribal)", source=SRC_GAZETTE)),
    # ── October
    Movable("2026-10-10", Entry(
        key="mahalaya", name="Mahalaya", kind="holiday", tier="minor", prep_days=10,
        states=group("West Bengal", "Odisha", "Assam", "Tripura"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-10-17", Entry(
        key="durga-puja", name="Durga Puja", kind="holiday", prep_days=21,
        span_days=5, states=BENGALI_STATES, tradition="Hindu", source=SRC_GAZETTE,
        note="West Bengal closes for around ten days; the gazetted core is "
             "Saptami to Dashami. Set the school's own span at approval.")),
    Movable("2026-10-19", Entry(
        key="durga-ashtami", name="Durga Ashtami / Maha Navami", kind="holiday",
        prep_days=14, states=ALL_INDIA, tradition="Hindu",
        source=SRC_PANCHANG_2026)),
    Movable("2026-10-19", Entry(
        key="ayudha-puja", name="Ayudha Puja / Saraswati Puja", kind="holiday",
        prep_days=10, states=group("Tamil Nadu", "Karnataka", "Kerala",
                                   "Andhra Pradesh", "Telangana", "Puducherry"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-10-18", Entry(
        key="bathukamma", name="Saddula Bathukamma", kind="holiday", tier="minor",
        prep_days=10, states=group("Telangana"), tradition="Hindu",
        source=SRC_GAZETTE)),
    Movable("2026-10-18", Entry(
        key="kati-bihu", name="Kati Bihu", kind="holiday", tier="minor", prep_days=7,
        states=group("Assam"), tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-10-20", Entry(
        key="dussehra", name="Dussehra / Vijayadashami", kind="holiday", prep_days=21,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2026,
        note="Kerala, Karnataka and Assam gazette Vijayadashami on 21 October — "
             "the tithi spans both days. Confirm against your state's list.")),
    Movable("2026-10-25", Entry(
        key="lakshmi-puja", name="Lakshmi Puja / Kumar Purnima", kind="holiday",
        tier="minor", prep_days=7,
        states=group("West Bengal", "Odisha", "Assam", "Tripura"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-10-26", Entry(
        key="valmiki-jayanti", name="Maharishi Valmiki Jayanti", kind="holiday",
        tier="minor", prep_days=7,
        states=group("Punjab", "Haryana", "Himachal Pradesh", "Karnataka",
                     "Delhi", "Chandigarh"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-10-29", Entry(
        key="karwa-chauth", name="Karwa Chauth", kind="observance", tier="minor",
        prep_days=7, states=PUNJAB_HARYANA + ("Uttar Pradesh", "Rajasthan"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    # ── November / December
    Movable("2026-11-08", Entry(
        key="diwali", name="Diwali / Deepavali", kind="holiday", prep_days=21,
        span_days=2, states=ALL_INDIA, tradition="Hindu",
        source=SRC_PANCHANG_2026,
        note="Most schools close for several days around it; the gazetted "
             "holiday is one. Kali Puja is the same night in the east.")),
    Movable("2026-11-08", Entry(
        key="kali-puja", name="Kali Puja", kind="holiday", tier="minor", prep_days=10,
        states=group("West Bengal", "Assam", "Tripura", "Odisha"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-11-10", Entry(
        key="govardhan-puja", name="Govardhan Puja / Bali Pratipada", kind="holiday",
        tier="minor", prep_days=7,
        states=group("Gujarat", "Maharashtra", "Rajasthan", "Uttar Pradesh",
                     "Karnataka", "Madhya Pradesh"),
        tradition="Hindu", source=SRC_PANCHANG_2026,
        note="Gujarat keeps this day as the Vikram Samvat New Year.")),
    Movable("2026-11-11", Entry(
        key="bhai-dooj", name="Bhai Dooj / Bhatri Dwitiya", kind="holiday",
        tier="minor", prep_days=7,
        states=group("Gujarat", "Maharashtra", "Rajasthan", "West Bengal",
                     "Bihar", "Uttar Pradesh", "Assam"),
        tradition="Hindu", source=SRC_PANCHANG_2026)),
    Movable("2026-11-15", Entry(
        key="chhath-puja", name="Chhath Puja", kind="holiday", prep_days=14,
        span_days=2, states=CHHATH_STATES, tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2026-11-24", Entry(
        key="guru-nanak-jayanti", name="Guru Nanak Jayanti", kind="holiday",
        prep_days=14, states=ALL_INDIA, tradition="Sikh",
        source=SRC_PANCHANG_2026)),
    Movable("2026-11-24", Entry(
        key="lachit-divas", name="Lachit Divas", kind="holiday", tier="minor",
        prep_days=7, states=group("Assam"), source=SRC_GAZETTE)),
    Movable("2026-11-27", Entry(
        key="kanakadasa-jayanti", name="Kanakadasa Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("Karnataka"), tradition="Hindu",
        source=SRC_GAZETTE)),
    Movable("2026-12-14", Entry(
        key="guru-teg-bahadur-martyrdom", name="Martyrdom of Guru Tegh Bahadur",
        kind="holiday", tier="minor", prep_days=7, states=group("Punjab"),
        tradition="Sikh", source=SRC_GAZETTE)),
    Movable("2026-12-28", Entry(
        key="shaheedi-sabha", name="Shaheedi Sabha, Fatehgarh Sahib", kind="holiday",
        tier="minor", prep_days=7, states=group("Punjab"), tradition="Sikh",
        source=SRC_GAZETTE)),
]

MOVABLE[2027] = [
    # ── January
    Movable("2027-01-14", Entry(
        key="lohri", name="Lohri", prep_days=7, states=PUNJAB_HARYANA,
        tradition="Sikh/Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-01-14", Entry(
        key="makar-sankranti", name="Makar Sankranti / Uttarayan", kind="holiday",
        prep_days=10,
        states=group("Gujarat", "Maharashtra", "Rajasthan", "Madhya Pradesh",
                     "Uttar Pradesh", "Bihar", "Jharkhand", "Odisha", "Telangana",
                     "Andhra Pradesh", "Karnataka"),
        tradition="Hindu", source=SRC_GAZETTE,
        note="The Gujarat, Odisha and Telangana notifications give 14 January; "
             "drikpanchang computes the sankranti moment on the 15th. The "
             "gazettes are what schools follow.")),
    Movable("2027-01-15", Entry(
        key="pongal", name="Pongal / Thai Pongal", kind="holiday", prep_days=14,
        span_days=3, states=TAMIL_STATES, tradition="Hindu", source=SRC_GAZETTE,
        note="Tamil Nadu gazettes Pongal on 15 January and Uzhavar Thirunal on "
             "the 16th.")),
    Movable("2027-01-15", Entry(
        key="thiruvalluvar-day", name="Thiruvalluvar Day", kind="holiday",
        tier="minor", prep_days=7, states=TAMIL_STATES, source=SRC_GAZETTE)),
    Movable("2027-01-16", Entry(
        key="uzhavar-thirunal", name="Uzhavar Thirunal", kind="holiday", tier="minor",
        prep_days=7, states=TAMIL_STATES, source=SRC_GAZETTE)),
    Movable("2027-01-15", Entry(
        key="guru-gobind-singh-jayanti", name="Guru Gobind Singh Jayanti",
        kind="holiday", prep_days=10,
        states=PUNJAB_HARYANA + ("Rajasthan", "Uttar Pradesh"),
        tradition="Sikh", source=SRC_GAZETTE)),
    Movable("2027-01-23", Entry(
        key="thaipoosam", name="Thaipoosam", kind="holiday", tier="minor",
        prep_days=7, states=TAMIL_STATES, tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-01-24", Entry(
        key="shab-e-barat", name="Shab-e-Barat", kind="holiday", tier="minor",
        prep_days=7, states=group("West Bengal", "Bihar", "Jharkhand"),
        tradition="Muslim", source=SRC_GAZETTE)),
    # ── February / March
    Movable("2027-02-11", Entry(
        key="vasant-panchami", name="Vasant Panchami / Saraswati Puja", kind="holiday",
        prep_days=10, states=BENGALI_STATES, tradition="Hindu",
        source=SRC_PANCHANG_2027)),
    Movable("2027-02-20", Entry(
        key="guru-ravidas-jayanti", name="Guru Ravidas Jayanti", kind="holiday",
        prep_days=7, states=group("Punjab", "Haryana", "Himachal Pradesh",
                                  "Chandigarh", "Uttar Pradesh", "Bihar"),
        tradition="Sikh/Hindu", source=SRC_GAZETTE)),
    Movable("2027-03-06", Entry(
        key="maha-shivaratri", name="Maha Shivaratri", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-03-10", Entry(
        key="eid-ul-fitr", name="Eid-ul-Fitr / Ramzan Id", kind="holiday",
        prep_days=14, states=ALL_INDIA, tradition="Muslim", source=SRC_GAZETTE,
        note="Every state notification read for 2027 gives 10 March. Still "
             "moon-sighting dependent in practice.")),
    Movable("2027-03-21", Entry(
        key="holika-dahan", name="Holika Dahan / Chhoti Holi", prep_days=7,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2027,
        note="Rajasthan's notification places Holika Dahan on 22 March.")),
    Movable("2027-03-22", Entry(
        key="holi", name="Holi", kind="holiday", prep_days=14, states=ALL_INDIA,
        tradition="Hindu", source=SRC_PANCHANG_2027,
        note="West Bengal (Doljatra), Telangana and Bihar gazette 22 March; "
             "Gujarat, Maharashtra, Rajasthan, Punjab and Odisha close on the "
             "23rd for the second day (Dhuleti / Dhulandi), listed separately.")),
    Movable("2027-03-23", Entry(
        key="dhulandi", name="Dhulandi / Dhuleti (second day of Holi)",
        kind="holiday", tier="minor", prep_days=7,
        states=group("Gujarat", "Rajasthan", "Maharashtra", "Punjab", "Odisha",
                     "Haryana", "Bihar"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-03-25", Entry(
        key="maundy-thursday", name="Maundy Thursday", kind="holiday", tier="minor",
        prep_days=7, states=group("Kerala", "Goa"), tradition="Christian",
        source=SRC_GAZETTE)),
    Movable("2027-03-26", Entry(
        key="good-friday", name="Good Friday", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Christian", source=SRC_PANCHANG_2027)),
    Movable("2027-03-28", Entry(
        key="easter", name="Easter Sunday", tier="minor", prep_days=7,
        states=ALL_INDIA, tradition="Christian", source=SRC_PANCHANG_2027)),
    # ── April
    Movable("2027-04-07", Entry(
        key="ugadi", name="Ugadi / Gudi Padwa", kind="holiday", prep_days=14,
        states=UGADI_STATES + ("Maharashtra", "Goa"), tradition="Hindu",
        source=SRC_GAZETTE,
        note="Confirmed against the Karnataka, Maharashtra and Telangana "
             "notifications, which all give 7 April.")),
    Movable("2027-04-07", Entry(
        key="cheti-chand", name="Cheti Chand / Jhulelal Jayanti", tier="minor",
        prep_days=7, states=group("Gujarat", "Rajasthan", "Maharashtra"),
        tradition="Hindu (Sindhi)", source=SRC_GAZETTE)),
    Movable("2027-04-14", Entry(
        key="baisakhi", name="Baisakhi / Vaisakhi", kind="holiday", prep_days=14,
        states=PUNJAB_HARYANA, tradition="Sikh", source=SRC_GAZETTE)),
    Movable("2027-04-14", Entry(
        key="tamil-new-year", name="Puthandu (Tamil New Year)", kind="holiday",
        prep_days=10, states=TAMIL_STATES, tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-04-14", Entry(
        key="bohag-bihu", name="Bohag Bihu (Rongali Bihu)", kind="holiday",
        prep_days=14, span_days=3, states=group("Assam"), tradition="Hindu",
        source=SRC_GAZETTE)),
    Movable("2027-04-14", Entry(
        key="maha-vishuva-sankranti", name="Maha Vishuva Sankranti (Pana Sankranti)",
        kind="holiday", tier="minor", prep_days=7, states=group("Odisha"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-04-15", Entry(
        key="vishu", name="Vishu", kind="holiday", prep_days=10,
        states=group("Kerala"), tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-04-15", Entry(
        key="pohela-boishakh", name="Pohela Boishakh (Bengali New Year)",
        kind="holiday", prep_days=10, states=group("West Bengal", "Tripura"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-04-15", Entry(
        key="rama-navami", name="Rama Navami", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-04-19", Entry(
        key="mahavir-jayanti", name="Mahavir Jayanti", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Jain", source=SRC_PANCHANG_2027)),
    # ── May / June
    Movable("2027-05-08", Entry(
        key="parshuram-jayanti", name="Parshuram Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("Gujarat", "Punjab", "Rajasthan",
                                                "Haryana"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-05-09", Entry(
        key="basava-jayanti", name="Basava Jayanti / Akshaya Tritiya", kind="holiday",
        prep_days=10, states=group("Karnataka"), tradition="Hindu",
        source=SRC_GAZETTE)),
    Movable("2027-05-09", Entry(
        key="tagore-jayanti", name="Rabindranath Tagore Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("West Bengal", "Tripura"),
        source=SRC_GAZETTE,
        note="The West Bengal notification gives 9 May; the tithi-based "
             "reckoning falls on 7 May.")),
    Movable("2027-05-14", Entry(
        key="janaki-navami", name="Janaki Navami", kind="holiday", tier="minor",
        prep_days=7, states=group("Bihar"), tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-05-17", Entry(
        key="eid-ul-adha", name="Eid-ul-Adha / Bakrid", kind="holiday", prep_days=14,
        states=ALL_INDIA, tradition="Muslim", source=SRC_GAZETTE)),
    Movable("2027-05-20", Entry(
        key="buddha-purnima", name="Buddha Purnima", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Buddhist", source=SRC_PANCHANG_2027)),
    Movable("2027-06-04", Entry(
        key="sabitri-amabasya", name="Sabitri Amabasya", kind="holiday", tier="minor",
        prep_days=7, states=group("Odisha"), tradition="Hindu",
        source=SRC_GAZETTE)),
    Movable("2027-06-06", Entry(
        key="islamic-new-year", name="Muharram (Islamic New Year)", tier="minor",
        prep_days=7, states=ALL_INDIA, tradition="Muslim",
        source=SRC_PANCHANG_2027)),
    Movable("2027-06-07", Entry(
        key="maharana-pratap-jayanti", name="Maharana Pratap Jayanti", kind="holiday",
        tier="minor", prep_days=7, states=group("Rajasthan", "Haryana"),
        tradition="Hindu", source=SRC_GAZETTE)),
    Movable("2027-06-08", Entry(
        key="guru-arjan-dev-martyrdom", name="Martyrdom of Guru Arjan Dev",
        kind="holiday", tier="minor", prep_days=7, states=group("Punjab"),
        tradition="Sikh", source=SRC_GAZETTE)),
    Movable("2027-06-15", Entry(
        key="raja-parba", name="Raja Parba", kind="holiday", tier="minor",
        prep_days=10, span_days=2, states=group("Odisha"), tradition="Hindu",
        source=SRC_GAZETTE)),
    Movable("2027-06-16", Entry(
        key="muharram-ashura", name="Muharram (Ashura)", kind="holiday", prep_days=10,
        states=ALL_INDIA, tradition="Muslim", source=SRC_GAZETTE,
        note="Every 2027 state notification read gives 16 June; drikpanchang "
             "computes Ashura on the 15th.")),
    Movable("2027-06-18", Entry(
        key="kabir-jayanti", name="Sant Kabir Jayanti", kind="holiday", tier="minor",
        prep_days=7, states=group("Punjab", "Haryana", "Bihar", "Uttar Pradesh",
                                  "Chandigarh"),
        tradition="Hindu", source=SRC_GAZETTE)),
    # ── July / August
    Movable("2027-07-05", Entry(
        key="rath-yatra", name="Jagannath Rath Yatra", kind="holiday", prep_days=14,
        states=group("Odisha", "West Bengal"), tradition="Hindu",
        source=SRC_GAZETTE)),
    Movable("2027-07-18", Entry(
        key="guru-purnima", name="Guru Purnima", kind="observance", prep_days=7,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-08-15", Entry(
        key="milad-un-nabi", name="Milad-un-Nabi (Eid-e-Milad)", kind="holiday",
        prep_days=10, states=ALL_INDIA, tradition="Muslim",
        source=SRC_PANCHANG_2027,
        note="Falls on Independence Day in 2027; some calendars list 16 August. "
             "Worth confirming, since the school is closed either way.")),
    Movable("2027-08-17", Entry(
        key="raksha-bandhan", name="Raksha Bandhan", kind="holiday", prep_days=10,
        states=group("Gujarat", "Rajasthan", "Madhya Pradesh", "Uttar Pradesh",
                     "West Bengal", "Maharashtra", "Haryana", "Delhi"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-08-25", Entry(
        key="janmashtami", name="Krishna Janmashtami", kind="holiday", prep_days=14,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2027)),
    # ── September
    Movable("2027-09-04", Entry(
        key="ganesh-chaturthi", name="Ganesh Chaturthi / Vinayaka Chavithi",
        kind="holiday", prep_days=21, span_days=2,
        states=group("Maharashtra", "Goa", "Karnataka", "Telangana",
                     "Andhra Pradesh", "Tamil Nadu", "Gujarat"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-09-12", Entry(
        key="onam", name="Onam (Thiruvonam)", kind="holiday", prep_days=21,
        span_days=4, states=group("Kerala", "Lakshadweep"), tradition="Hindu",
        source=SRC_PANCHANG_2027,
        note="Some calendars give 11 September for Thiruvonam. Kerala's own "
             "notification is the one to confirm against.")),
    # ── October
    Movable("2027-10-07", Entry(
        key="durga-puja", name="Durga Puja", kind="holiday", prep_days=21,
        span_days=4, states=BENGALI_STATES, tradition="Hindu",
        source=SRC_PANCHANG_2027)),
    Movable("2027-10-07", Entry(
        key="durga-ashtami", name="Durga Ashtami / Maha Navami", kind="holiday",
        prep_days=14, span_days=2, states=ALL_INDIA, tradition="Hindu",
        source=SRC_PANCHANG_2027)),
    Movable("2027-10-08", Entry(
        key="ayudha-puja", name="Ayudha Puja / Saraswati Puja", kind="holiday",
        prep_days=10, states=group("Tamil Nadu", "Karnataka", "Kerala",
                                   "Andhra Pradesh", "Telangana", "Puducherry"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-10-09", Entry(
        key="dussehra", name="Dussehra / Vijayadashami", kind="holiday", prep_days=21,
        states=ALL_INDIA, tradition="Hindu", source=SRC_PANCHANG_2027,
        note="Some calendars give 10 October; the tithi spans both days and "
             "state notifications differ.")),
    Movable("2027-10-15", Entry(
        key="valmiki-jayanti", name="Maharishi Valmiki Jayanti", kind="holiday",
        tier="minor", prep_days=7,
        states=group("Punjab", "Haryana", "Himachal Pradesh", "Karnataka",
                     "Delhi", "Chandigarh"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-10-18", Entry(
        key="karwa-chauth", name="Karwa Chauth", kind="observance", tier="minor",
        prep_days=7, states=PUNJAB_HARYANA + ("Uttar Pradesh", "Rajasthan"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-10-29", Entry(
        key="diwali", name="Diwali / Deepavali", kind="holiday", prep_days=21,
        span_days=2, states=ALL_INDIA, tradition="Hindu",
        source=SRC_PANCHANG_2027)),
    Movable("2027-10-29", Entry(
        key="kali-puja", name="Kali Puja", kind="holiday", tier="minor", prep_days=10,
        states=group("West Bengal", "Assam", "Tripura", "Odisha"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-10-30", Entry(
        key="govardhan-puja", name="Govardhan Puja / Bali Pratipada", kind="holiday",
        tier="minor", prep_days=7,
        states=group("Gujarat", "Maharashtra", "Rajasthan", "Uttar Pradesh",
                     "Karnataka", "Madhya Pradesh"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    Movable("2027-10-31", Entry(
        key="bhai-dooj", name="Bhai Dooj / Bhatri Dwitiya", kind="holiday",
        tier="minor", prep_days=7,
        states=group("Gujarat", "Maharashtra", "Rajasthan", "West Bengal",
                     "Bihar", "Uttar Pradesh", "Assam"),
        tradition="Hindu", source=SRC_PANCHANG_2027)),
    # ── November / December
    Movable("2027-11-04", Entry(
        key="chhath-puja", name="Chhath Puja", kind="holiday", prep_days=14,
        span_days=2, states=CHHATH_STATES, tradition="Hindu",
        source=SRC_PANCHANG_2027)),
    Movable("2027-11-14", Entry(
        key="guru-nanak-jayanti", name="Guru Nanak Jayanti", kind="holiday",
        prep_days=14, states=ALL_INDIA, tradition="Sikh",
        source=SRC_PANCHANG_2027,
        note="Falls on Children's Day in 2027 — both are in the feed and both "
             "are real.")),
    Movable("2027-12-12", Entry(
        key="hazrat-ali-birthday", name="Hazrat Ali's Birthday", tier="minor",
        prep_days=7, states=ALL_INDIA, tradition="Muslim",
        source=SRC_PANCHANG_2027)),
]

__all__ = ["FIXED", "MOVABLE"]
