"""The canonical Indian state / UT vocabulary (V1-19).

**Why this file has to exist before a single observance row is stored.**

`organizations.state` has been free text since V1-2 — the operator's New-school
sheet renders `<Input placeholder="e.g. Telangana" />` and stores whatever is
typed. That was harmless while nothing read the column. The moment the catalogue
is scoped by state (`D-61`), free text becomes the whole feature's failure mode:
a school that typed `TN`, `Tamilnadu` or `tamil nadu ` matches no corpus row, so
its admin sees an empty suggestions feed and concludes the product has no dates
in it. Nothing errors. Nothing is logged. It simply never works, for that school,
forever.

So: one canonical spelling per state, `normalise()` on every read and write, and
a picker instead of a text box on both surfaces that set it. The aliases are not
decoration — `Orissa`, `Pondicherry` and `Uttaranchal` are the names a lot of
school paperwork still uses, and `NCT of Delhi` is what the address line says.

`normalise()` returns **None** for anything it cannot place, and callers treat
None as *"this school has no state set"* — which shows it the all-India rows and
nothing regional. Guessing would be worse: a school shown Kerala's holidays
because someone typed `K` is a product that lies about the calendar.
"""

from __future__ import annotations

import re

# The 28 states, in the Union's own order, then the 8 union territories. These
# strings are the canonical tokens: they are what goes in `observances.states`,
# what the pickers write into `organizations.state`, and what `normalise()`
# returns. Change one and you orphan every corpus row that names it.
STATES: tuple[str, ...] = (
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
)

UNION_TERRITORIES: tuple[str, ...] = (
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
)

ALL_STATES: tuple[str, ...] = STATES + UNION_TERRITORIES

# Alias → canonical. Keys are matched after `_squash()`, so case, spacing and
# punctuation are already gone; write them however reads clearest.
_ALIASES: dict[str, str] = {
    # Postal / conversational abbreviations.
    "ap": "Andhra Pradesh",
    "ar": "Arunachal Pradesh",
    "as": "Assam",
    "br": "Bihar",
    "cg": "Chhattisgarh",
    "ct": "Chhattisgarh",
    "ga": "Goa",
    "gj": "Gujarat",
    "hr": "Haryana",
    "hp": "Himachal Pradesh",
    "jh": "Jharkhand",
    "ka": "Karnataka",
    "kl": "Kerala",
    "mp": "Madhya Pradesh",
    "mh": "Maharashtra",
    "mn": "Manipur",
    "ml": "Meghalaya",
    "mz": "Mizoram",
    "nl": "Nagaland",
    "od": "Odisha",
    "or": "Odisha",
    "pb": "Punjab",
    "rj": "Rajasthan",
    "sk": "Sikkim",
    "tn": "Tamil Nadu",
    "ts": "Telangana",
    "tg": "Telangana",
    "tr": "Tripura",
    "up": "Uttar Pradesh",
    "uk": "Uttarakhand",
    "ua": "Uttarakhand",
    "wb": "West Bengal",
    "an": "Andaman and Nicobar Islands",
    "ch": "Chandigarh",
    "dl": "Delhi",
    "jk": "Jammu and Kashmir",
    "la": "Ladakh",
    "ld": "Lakshadweep",
    "py": "Puducherry",
    "pn": "Puducherry",
    "dn": "Dadra and Nagar Haveli and Daman and Diu",
    "dd": "Dadra and Nagar Haveli and Daman and Diu",
    # Former names still in daily use on school paperwork.
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "pondichery": "Puducherry",
    "uttaranchal": "Uttarakhand",
    "uttaranchalstate": "Uttarakhand",
    "nctofdelhi": "Delhi",
    "newdelhi": "Delhi",
    "delhinct": "Delhi",
    "jammukashmir": "Jammu and Kashmir",
    "jammuandkashmir": "Jammu and Kashmir",
    "jandk": "Jammu and Kashmir",
    "andamannicobar": "Andaman and Nicobar Islands",
    "andamanandnicobar": "Andaman and Nicobar Islands",
    "andaman": "Andaman and Nicobar Islands",
    "dadranagarhavelidamandiu": "Dadra and Nagar Haveli and Daman and Diu",
    "dadraandnagarhaveli": "Dadra and Nagar Haveli and Daman and Diu",
    "damananddiu": "Dadra and Nagar Haveli and Daman and Diu",
    # Common misspellings seen in real rosters.
    "tamilnadu": "Tamil Nadu",
    "tamilnad": "Tamil Nadu",
    "chattisgarh": "Chhattisgarh",
    "chhatisgarh": "Chhattisgarh",
    "odissa": "Odisha",
    "westbengal": "West Bengal",
    "himachal": "Himachal Pradesh",
    "arunachal": "Arunachal Pradesh",
    "telengana": "Telangana",
    "pondy": "Puducherry",
}


def _squash(value: str) -> str:
    """Lowercase and drop everything that is not a letter or a digit.

    `"Tamil Nadu"`, `"tamil-nadu"`, `"TAMIL NADU "` and `"Tamil  Nadu"` all
    become `"tamilnadu"`. Spelling variance in a text box is not a data problem
    worth a table; it is a normalisation problem worth eight lines.
    """
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


# Built once: canonical squashed form → canonical spelling.
_CANONICAL: dict[str, str] = {_squash(s): s for s in ALL_STATES}


def normalise(value: str | None) -> str | None:
    """Resolve free text to a canonical state token, or None.

    None means *"we do not know which state this school is in"* and is a
    perfectly good answer — the caller then shows all-India rows only. It is
    deliberately NOT a guess: partial and fuzzy matching here would silently
    hand a school in Kerala the Punjab gazette, and a wrong calendar is worse
    than a thin one.
    """
    if not value:
        return None
    squashed = _squash(value)
    if not squashed:
        return None
    if squashed in _CANONICAL:
        return _CANONICAL[squashed]
    return _ALIASES.get(squashed)


def normalise_all(values: list[str] | None) -> list[str]:
    """Normalise a list, dropping anything unresolvable, order-preserving and
    de-duplicated. Used on the write path for `observances.states` so a typo in
    a bulk import cannot create a state nothing will ever match."""
    if not values:
        return []
    out: list[str] = []
    for v in values:
        token = normalise(v)
        if token and token not in out:
            out.append(token)
    return out


def unresolved(values: list[str] | None) -> list[str]:
    """The entries `normalise_all` threw away — so an importer can REPORT what
    it could not place instead of silently shrinking the list (the syllabus
    importer's rule, V2-P11)."""
    if not values:
        return []
    return [v for v in values if normalise(v) is None]
