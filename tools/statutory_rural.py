"""The other half of each state's statutory speed law: outside town.

``statutory_limits.py`` holds the in-town default -- the business,
residence or urban district figure that governs an unposted street. That
figure does NOT reach a road outside the district: an unposted state route
between towns runs at the state's general rural default, usually 55. Until
2026-09-24 the street bake filled every untagged street with the district
figure wherever it was, so IA 175 beside a Love's off I-35 read 20 mph --
a number that is real in Iowa Code 321.285 and false on that road.

Per state:
  town_basis        what the in-town default keys on, and so which Census
                    boundary stands in for it (``census_boundaries.py``):
                    ``urban_area`` for a district the code defines by how
                    densely the frontage is built up, ``municipal`` for the
                    corporate limits of a city, town or village
  highway_mph       the default on an unposted non-freeway state or US route
                    outside town, None where the code sets none
  local_mph         the same for a county, township or local road
  citation          the section
  url               where it was read; "" means the same official page as
                    the state's in-town row (``statutory_limits.py``), whose
                    notes quote the rural figure from the same research
  rule_type         absolute or prima facie
  signs_required    True where the figure binds only once posted
  verified          True only where the figure was read off an official
                    source; anything else never reaches a street -- the bake
                    labels the fill ``assumed`` instead
  notes             road classes and day/night splits the bake does not
                    model, and anything a later reader needs
"""

from __future__ import annotations

from typing import Any

URBAN = "urban_area"
MUNICIPAL = "municipal"


def _row(
    highway: float | None,
    local: float | None,
    citation: str,
    rule_type: str,
    notes: str,
    *,
    url: str = "",
    basis: str = URBAN,
    verified: bool = True,
    signs_required: bool = False,
    no_default: bool = False,
) -> dict[str, Any]:
    return {
        "town_basis": basis,
        "no_rural_default": no_default,
        "highway_mph": highway,
        "local_mph": local,
        "citation": citation,
        "url": url,
        "rule_type": rule_type,
        "signs_required": signs_required,
        "verified": verified,
        "notes": notes,
    }


RURAL_LIMITS: dict[str, dict[str, Any]] = {
    "Arizona": _row(
        65,
        65,
        "Ariz. Rev. Stat. Sec. 28-701(B)(3)",
        "prima facie",
        "'Sixty-five miles per hour in other locations.'",
    ),
    "Connecticut": _row(
        55,
        55,
        "Conn. Gen. Stat. Sec. 14-219",
        "absolute",
        "No district default; where no zone is established Sec. 14-219 caps any public "
        "roadway at 55.",
    ),
    "Delaware": _row(
        50,
        50,
        "21 Del. C. Sec. 4169(a)",
        "absolute",
        "50 mph on 2-lane roadways; 55 on 4-lane and divided roadways, which the bake does "
        "not tell apart, so a 4-lane divided road reads 5 low.",
    ),
    "District of Columbia": _row(
        20,
        20,
        "18 DCMR Sec. 2200.6",
        "absolute",
        "One default 'on all streets and highways'; the District is all urban.",
    ),
    "Florida": _row(
        55,
        55,
        "Fla. Stat. Sec. 316.183(2)",
        "absolute",
        "'55 miles per hour at any time at all other locations.'",
    ),
    "Iowa": _row(
        55,
        55,
        "Iowa Code Sec. 321.285(3)",
        "absolute",
        "The general limit outside business, residence, school and suburban districts. "
        "The 45 mph suburban district is not modelled.",
    ),
    "Kansas": _row(
        65,
        55,
        "K.S.A. 8-1558(a)",
        "absolute",
        "65 mph on other highways, 55 mph on a county or township highway.",
    ),
    "Louisiana": _row(
        55, 55, "La. R.S. 32:61(A)", "absolute", "One statewide default; no district categories."
    ),
    "Maine": _row(
        45,
        45,
        "29-A M.R.S.A. Sec. 2074(1)",
        "absolute",
        "'Forty-five miles per hour on all other public ways unless otherwise posted.'",
    ),
    "Maryland": _row(
        50,
        50,
        "Md. Code Ann., Transp. Sec. 21-801.1(b)",
        "absolute",
        "50 mph on undivided highways in other locations, 55 on divided ones (not told apart).",
    ),
    "Michigan": _row(
        55,
        55,
        "Mich. Comp. Laws Sec. 257.627(9)",
        "absolute",
        "The 55 mph general speed limit on trunk line and county highways, which applies "
        "unposted. 257.627(2)(e) keys the residential 25 to land zoned residential by an "
        "incorporated city or village, so the in-town test uses corporate limits.",
        basis=MUNICIPAL,
    ),
    "Minnesota": _row(
        55,
        55,
        "Minn. Stat. Sec. 169.14, subd. 2(a)",
        "prima facie",
        "55 mph in locations not otherwise specified.",
    ),
    "Mississippi": _row(
        55,
        55,
        "Miss. Code Ann. Sec. 63-3-501",
        "absolute",
        "Two-lane state and US highways 55, read from the official DPS Driver's Manual "
        "(rev. 1.15.2025, p. 41); four-lane highways 65, not told apart.",
    ),
    "Missouri": _row(
        60,
        60,
        "Mo. Rev. Stat. Sec. 304.010.2(4)",
        "prima facie",
        "60 mph on all other roads not located in an urbanized area -- the statute's own "
        "term, so the Census Urban Area is the boundary itself here. Lettered supplementary "
        "state routes are 55, not told apart.",
    ),
    "Montana": _row(
        70,
        70,
        "Mont. Code Ann. Sec. 61-8-303(1)",
        "absolute",
        "70 mph by day and 65 by night on any other public highway; the day figure.",
    ),
    "Nebraska": _row(
        65,
        55,
        "Neb. Rev. Stat. Sec. 60-6,186",
        "absolute",
        "65 mph on the state highway system; 55 on dustless-surfaced roads off it (50 on "
        "gravel, not told apart).",
    ),
    "New Hampshire": _row(
        55,
        55,
        "N.H. Rev. Stat. Ann. Sec. 265:60, II",
        "prima facie",
        "55 mph in other locations; 35 in a rural residence district and 45 on an "
        "unimproved rural highway are not modelled.",
    ),
    "New Jersey": _row(
        50,
        50,
        "N.J. Stat. Ann. Sec. 39:4-98(c)",
        "prima facie",
        "'Fifty miles per hour in all other locations.'",
    ),
    "New York": _row(
        55,
        55,
        "N.Y. Veh. & Traf. Law Sec. 1180(b)",
        "absolute",
        "One statewide default; no district categories.",
    ),
    "North Carolina": _row(
        55,
        55,
        "N.C. Gen. Stat. Sec. 20-141(b)(2)",
        "absolute",
        "'Fifty-five miles per hour outside municipal corporate limits.'",
        basis=MUNICIPAL,
    ),
    "Oregon": _row(
        55,
        55,
        "Or. Rev. Stat. Sec. 811.111(1)(d)(F)",
        "absolute",
        "'Fifty-five miles per hour in locations not otherwise described.'",
    ),
    "Pennsylvania": _row(
        55,
        55,
        "75 Pa. Cons. Stat. Sec. 3362(a)(2)",
        "absolute",
        "'55 miles per hour in other locations', not subject to the posting rule.",
    ),
    "Rhode Island": _row(
        50,
        50,
        "R.I. Gen. Laws Sec. 31-14-2(a)",
        "prima facie",
        "50 mph elsewhere in daytime, 45 at night; the day figure.",
    ),
    "South Carolina": _row(
        55, 55, "S.C. Code Ann. Sec. 56-5-1520", "absolute", "55 mph in other locations."
    ),
    "South Dakota": _row(
        65,
        65,
        "S.D. Codified Laws Sec. 32-25-1.1",
        "absolute",
        "65 mph statewide maximum on any street or highway not otherwise set.",
    ),
    "Tennessee": _row(
        65,
        65,
        "T.C.A. Sec. 55-8-152",
        "absolute",
        "65 mph on all other public roads, as the Tennessee Highway Safety Office states "
        "the statute.",
    ),
    "Utah": _row(
        55,
        55,
        "Utah Code Ann. Sec. 41-6a-601(2)(c)",
        "prima facie",
        "'55 miles per hour in other locations.'",
    ),
    "Vermont": _row(
        50,
        50,
        "23 V.S.A. Sec. 1081(b)",
        "absolute",
        "One statewide default; no district categories.",
    ),
    "Virginia": _row(
        55,
        55,
        "Va. Code Ann. Sec. 46.2-870",
        "absolute",
        "The general 55 mph maximum unless otherwise posted.",
    ),
    "Washington": _row(
        60,
        50,
        "Wash. Rev. Code Sec. 46.61.400(2)",
        "absolute",
        "50 mph on county roads, 60 on state highways; 25 on city and town streets.",
        basis=MUNICIPAL,
    ),
    "West Virginia": _row(
        55,
        55,
        "W. Va. Code Sec. 17C-6-1(b)(3)",
        "absolute",
        "'Fifty-five miles per hour on open country highways.'",
    ),
    "Wisconsin": _row(
        55,
        55,
        "Wis. Stat. Sec. 346.57(4)(h)",
        "absolute",
        "55 mph in the absence of any other fixed limit; 35 in a semiurban district is not "
        "modelled.",
        basis=MUNICIPAL,
    ),
}

# Read for this table on 2026-09-24. JUSTIA marks a figure read from the
# Justia full-text mirror because the official code sits behind LexisNexis
# or a bot check; every other url is the legislature's own site.
JUSTIA = " Read from the Justia mirror; the official code is behind LexisNexis or a bot check."
RURAL_LIMITS.update(
    {
        "Alabama": _row(
            55,
            45,
            "Ala. Code Sec. 32-5A-171(2), (3)",
            "absolute",
            "55 mph on highways other than interstates or 4+ lane highways (65 there, not "
            "told apart); 45 on a paved county-maintained road in an unincorporated area, "
            "35 unpaved.",
            url="https://alison.legislature.state.al.us/code-of-alabama?section=32-5A-171",
        ),
        "Arkansas": _row(
            50,
            50,
            "Ark. Code Ann. Sec. 27-51-201(c)(2)",
            "absolute",
            "'Fifty miles per hour for trucks of one-and-one-half-ton capacity or more in "
            "other locations' -- the TRUCK figure, and the only rural default the code has "
            "kept since the 2019 act dropped the 65 for other vehicles. The game drives a "
            "truck, so it applies." + JUSTIA,
            url="https://law.justia.com/codes/arkansas/title-27/subtitle-4/chapter-51/subchapter-2/section-27-51-201/",
        ),
        "California": _row(
            55,
            55,
            "Cal. Veh. Code Sec. 22349(b); Sec. 22406",
            "absolute",
            "55 mph on a two-lane undivided highway unless posted higher, and 55 for a "
            "truck of three or more axles on any highway (22406), so 55 either way.",
            url="https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=VEH&sectionNum=22349",
        ),
        "Colorado": _row(
            55,
            55,
            "Colo. Rev. Stat. Sec. 42-4-1101(2)(f)",
            "prima facie",
            "55 mph on other open highways off the interstate that are not four-lane "
            "freeways or expressways; 40 on open mountain highways, not told apart." + JUSTIA,
            url="https://law.justia.com/codes/colorado/title-42/regulation-of-vehicles-and-traffic/article-4/part-11/section-42-4-1101/",
        ),
        "Georgia": _row(
            55,
            55,
            "O.C.G.A. Sec. 40-6-181(b)(5)",
            "absolute",
            "'Fifty-five miles per hour in other locations'; 35 on an unpaved county road, "
            "not told apart; the 65 and 70 tiers bind only when signed." + JUSTIA,
            url="https://law.justia.com/codes/georgia/title-40/chapter-6/article-9/section-40-6-181/",
        ),
        "Idaho": _row(
            65,
            55,
            "Idaho Code Sec. 49-654(2)(a)(iii), (iv)",
            "absolute",
            "65 mph on state highways (US routes included), 55 in other locations.",
            url="https://legislature.idaho.gov/statutesrules/idstat/title49/t49ch6/sect49-654/",
        ),
        "Illinois": _row(
            55,
            55,
            "625 ILCS 5/11-601(d-1)(3)",
            "absolute",
            "55 mph outside an urban district on all other highways, roads and streets.",
            url="https://www.ilga.gov/legislation/ilcs/fulltext.asp?DocName=062500050K11-601",
        ),
        "Indiana": _row(
            55,
            55,
            "Ind. Code Sec. 9-21-5-2(a)(2)",
            "absolute",
            "55 mph except as otherwise provided; 60 on non-interstate 4+ lane divided "
            "highways outside large urbanized areas, not told apart." + JUSTIA,
            url="https://law.justia.com/codes/indiana/title-9/article-21/chapter-5/section-9-21-5-2/",
        ),
        "Kentucky": _row(
            55,
            None,
            "KRS 189.390(3)(b)",
            "absolute",
            "55 mph on all other state highways. The section covers state highways only; "
            "county roads have limits only by local ordinance, so a local road takes the "
            "table's assumed median.",
            url="https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=52569",
        ),
        "Massachusetts": _row(
            40,
            40,
            "Mass. Gen. Laws ch. 90, Sec. 17",
            "prima facie",
            "40 mph on any other way outside a thickly settled or business district, 50 on "
            "a divided highway outside one (not told apart).",
            url="https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXIV/Chapter90/Section17",
        ),
        "Nevada": _row(
            None,
            None,
            "Nev. Rev. Stat. Sec. 484B.600(1)(e)",
            "absolute",
            "No rural default: only the posted limit, the basic rule and an 80 mph cap. "
            "Streets outside town take the table's assumed median.",
            url="https://www.leg.state.nv.us/nrs/NRS-484B.html#NRS484BSec600",
            no_default=True,
        ),
        "New Mexico": _row(
            None,
            55,
            "NMSA 1978, Sec. 66-7-301(A)(3), (4)",
            "absolute",
            "55 mph on a county road without a posted limit; no figure for an unposted "
            "state or US highway beyond the 75 mph cap, so a numbered highway takes the "
            "table's assumed median." + JUSTIA,
            url="https://law.justia.com/codes/new-mexico/chapter-66/article-7/part-4/section-66-7-301/",
        ),
        "North Dakota": _row(
            None,
            55,
            "N.D. Cent. Code Sec. 39-09-02(1)(f), (g)",
            "prima facie",
            "55 mph on paved two-lane county and township highways and loose-surface roads "
            "if unposted; the 65 on two-lane state highways binds only if posted, so an "
            "unposted numbered highway takes the table's assumed median.",
            url="https://ndlegis.gov/cencode/t39c09.pdf",
        ),
        "Ohio": _row(
            55,
            55,
            "Ohio Rev. Code Sec. 4511.21(B)(5), (D)",
            "absolute",
            "55 mph on highways outside municipal corporations; 60 on two-lane state routes "
            "only where set and posted.",
            url="https://codes.ohio.gov/ohio-revised-code/section-4511.21",
            basis=MUNICIPAL,
        ),
        "Oklahoma": _row(
            None,
            55,
            "47 Okla. Stat. Sec. 11-801(B)(1), (F)(1)",
            "absolute",
            "55 mph on a county road unless posted; a state highway's limit is whatever "
            "ODOT sets, with no figure, so a numbered highway takes the table's assumed "
            "median." + JUSTIA,
            url="https://law.justia.com/codes/oklahoma/title-47/section-47-11-801/",
        ),
        "Texas": _row(
            70,
            60,
            "Tex. Transp. Code Ann. Sec. 545.352(b)(2), (3)",
            "prima facie",
            "70 mph on a highway numbered by the state or US outside an urban district "
            "(farm-to-market and ranch-to-market roads included), 60 on other highways "
            "outside one.",
            url="https://statutes.capitol.texas.gov/Docs/TN/htm/TN.545.htm#545.352",
        ),
        "Wyoming": _row(
            70,
            65,
            "Wyo. Stat. Ann. Sec. 31-5-301(b)(iv), (vii)",
            "absolute",
            "70 mph on state highways that are not interstates; 65 in all other locations "
            "where paved, 55 unpaved (not told apart)." + JUSTIA,
            url="https://law.justia.com/codes/wyoming/title-31/chapter-5/article-3/section-31-5-301/",
        ),
    }
)
RURAL_LIMITS["District of Columbia"]["town_basis"] = MUNICIPAL


def validate(rows: dict[str, dict[str, Any]]) -> list[str]:
    problems = []
    for state, row in sorted(rows.items()):
        if row["town_basis"] not in (URBAN, MUNICIPAL):
            problems.append(f"{state}: town_basis {row['town_basis']!r}")
        for key in ("highway_mph", "local_mph"):
            value = row[key]
            if value is not None and not 15 <= float(value) <= 75:
                problems.append(f"{state}: rural {key} {value} is implausible")
        if row["verified"] and not row["citation"]:
            problems.append(f"{state}: rural figure verified with no citation")
        if (
            row["verified"]
            and row["highway_mph"] is None
            and row["local_mph"] is None
            and not row["no_rural_default"]
        ):
            problems.append(f"{state}: verified rural row with no figure")
        if row["rule_type"] not in ("absolute", "prima facie"):
            problems.append(f"{state}: rural rule_type {row['rule_type']!r}")
        if not row["notes"]:
            problems.append(f"{state}: rural row without notes")
    return problems
