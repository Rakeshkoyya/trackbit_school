"""International observance days — the UN list, tiered for a school (V1-19).

Every entry here is `kind="observance"`, all-India, and **fixed** — the UN days
sit on the same date every year, so this file generates for any year and never
needs revisiting.

**Why the whole list is here and not a curated handful.** The founder asked for
international dates as well as Indian ones, and a hand-picked subset would be
one person's guess at what a school cares about — a school running a Model UN, a
green-schools programme or a disability-inclusion week needs days that would
never survive somebody else's shortlist.

**Why that does not drown the feed.** `S-125` anticipated exactly this: an
international day exists for almost everything, and a card with something on it
every single day stops being read inside a week. So the catalogue carries a tier
and the feed defaults to **major only**. About thirty-five days here are `major`
— the ones Indian schools actually hold assemblies, poster competitions and
club activities for. Everything else is `minor`: present, searchable, and
approvable by an admin who wants it, but never pushed at anybody.

Tier is the editorial judgement in this file, and it is the only one. The dates
and names are the UN's own.

⚠️ Two overlaps are deliberate, not duplicates:
  * 2 October is Gandhi Jayanti (a national holiday) **and** the International
    Day of Non-Violence. Both rows exist; they are different observances that
    share a date, and a school may well mark them differently.
  * 5 October is World Teachers' Day; India's own Teachers' Day is 5 September.
    Indian schools observe the September date. Both are here.
"""

from __future__ import annotations

from .types import ALL_INDIA, Entry, Fixed

SRC_UN = "United Nations — International Days and Weeks (un.org)"

# The days Indian schools actually build an assembly, a competition or a club
# activity around. Everything not named here ships `minor` and never reaches a
# school's feed unless an admin goes looking for it.
_MAJOR: frozenset[str] = frozenset({
    "International Day of Education",
    "International Day of Women and Girls in Science",
    "International Mother Language Day",
    "World Wildlife Day",
    "International Women's Day",
    "International Day of Forests",
    "World Poetry Day",
    "World Water Day",
    "World Autism Awareness Day",
    "World Health Day",
    "International Mother Earth Day",
    "World Book and Copyright Day",
    "World Bee Day",
    "International Day for Biological Diversity",
    "World No-Tobacco Day",
    "World Environment Day",
    "World Oceans Day",
    "International Day of Play",
    "World Day Against Child Labour",
    "International Day of Yoga",
    "International Day against Drug Abuse and Illicit Trafficking",
    "World Population Day",
    "International Day of Friendship",
    "International Youth Day",
    "International Literacy Day",
    "International Day for the Preservation of the Ozone Layer",
    "International Day of Peace",
    "International Day of Non-Violence",
    "World Teachers' Day",
    "World Mental Health Day",
    "International Day of the Girl Child",
    "World Food Day",
    "United Nations Day",
    "World Science Day for Peace and Development",
    "International Day for Tolerance",
    "World Children's Day",
    "World AIDS Day",
    "International Day of Persons with Disabilities",
    "Human Rights Day",
    "World Day of Social Justice",
    "International Day of Sign Languages",
    "World Braille Day",
})

# (month, day, name). The UN's list, in date order.
_DAYS: tuple[tuple[int, int, str], ...] = (
    (1, 4, "World Braille Day"),
    (1, 24, "International Day of Education"),
    (1, 26, "International Day of Clean Energy"),
    (1, 27, "International Day of Commemoration in Memory of the Victims of the Holocaust"),
    (1, 28, "International Day of Peaceful Coexistence"),
    (2, 1, "World Interfaith Harmony Week"),
    (2, 2, "World Wetlands Day"),
    (2, 4, "International Day of Human Fraternity"),
    (2, 6, "International Day of Zero Tolerance to Female Genital Mutilation"),
    (2, 10, "World Pulses Day"),
    (2, 11, "International Day of Women and Girls in Science"),
    (2, 12, "International Day for the Prevention of Violent Extremism"),
    (2, 13, "World Radio Day"),
    (2, 17, "Global Tourism Resilience Day"),
    (2, 20, "World Day of Social Justice"),
    (2, 21, "International Mother Language Day"),
    (3, 1, "Zero Discrimination Day"),
    (3, 1, "World Seagrass Day"),
    (3, 3, "World Wildlife Day"),
    (3, 5, "International Day for Disarmament and Non-Proliferation Awareness"),
    (3, 8, "International Women's Day"),
    (3, 10, "International Day of Women Judges"),
    (3, 15, "International Day to Combat Islamophobia"),
    (3, 20, "International Day of Happiness"),
    (3, 21, "World Day for Glaciers"),
    (3, 21, "International Day of Forests"),
    (3, 21, "International Day for the Elimination of Racial Discrimination"),
    (3, 21, "World Poetry Day"),
    (3, 21, "International Day of Nowruz"),
    (3, 21, "World Down Syndrome Day"),
    (3, 22, "World Water Day"),
    (3, 23, "World Meteorological Day"),
    (3, 24, "World Tuberculosis Day"),
    (3, 25, "International Day of Remembrance of the Victims of Slavery"),
    (3, 30, "International Day of Zero Waste"),
    (4, 2, "World Autism Awareness Day"),
    (4, 4, "International Day for Mine Awareness and Assistance in Mine Action"),
    (4, 5, "International Day of Conscience"),
    (4, 6, "International Day of Sport for Development and Peace"),
    (4, 7, "World Health Day"),
    (4, 12, "International Day of Human Space Flight"),
    (4, 15, "International Wellness Day"),
    (4, 20, "Chinese Language Day"),
    (4, 21, "World Creativity and Innovation Day"),
    (4, 22, "International Mother Earth Day"),
    (4, 23, "International Girls in ICT Day"),
    (4, 23, "World Book and Copyright Day"),
    (4, 23, "English Language Day"),
    (4, 23, "Spanish Language Day"),
    (4, 24, "World Immunization Week"),
    (4, 25, "World Malaria Day"),
    (4, 26, "International Chernobyl Disaster Remembrance Day"),
    (4, 26, "World Intellectual Property Day"),
    (4, 28, "World Day for Safety and Health at Work"),
    (4, 30, "International Jazz Day"),
    (5, 2, "World Tuna Day"),
    (5, 3, "World Press Freedom Day"),
    (5, 5, "World Portuguese Language Day"),
    (5, 9, "World Migratory Bird Day"),
    (5, 12, "International Day of Plant Health"),
    (5, 15, "International Day of Families"),
    (5, 16, "International Day of Living Together in Peace"),
    (5, 16, "International Day of Light"),
    (5, 17, "World Telecommunication and Information Society Day"),
    (5, 19, "World Fair Play Day"),
    (5, 20, "World Bee Day"),
    (5, 21, "International Tea Day"),
    (5, 21, "World Day for Cultural Diversity for Dialogue and Development"),
    (5, 22, "International Day for Biological Diversity"),
    (5, 25, "World Football Day"),
    (5, 29, "International Day of UN Peacekeepers"),
    (5, 30, "International Day of Potato"),
    (5, 31, "World No-Tobacco Day"),
    (6, 1, "Global Day of Parents"),
    (6, 3, "World Bicycle Day"),
    (6, 4, "International Day of Innocent Children Victims of Aggression"),
    (6, 5, "World Environment Day"),
    (6, 6, "Russian Language Day"),
    (6, 7, "World Food Safety Day"),
    (6, 8, "World Oceans Day"),
    (6, 10, "International Day for Dialogue among Civilizations"),
    (6, 11, "International Day of Play"),
    (6, 12, "World Day Against Child Labour"),
    (6, 13, "International Albinism Awareness Day"),
    (6, 14, "World Blood Donor Day"),
    (6, 15, "World Elder Abuse Awareness Day"),
    (6, 17, "World Day to Combat Desertification and Drought"),
    (6, 18, "Sustainable Gastronomy Day"),
    (6, 18, "International Day for Countering Hate Speech"),
    (6, 20, "World Refugee Day"),
    (6, 21, "International Day of Yoga"),
    (6, 23, "United Nations Public Service Day"),
    (6, 25, "Day of the Seafarer"),
    (6, 26, "International Day against Drug Abuse and Illicit Trafficking"),
    (6, 27, "Micro-, Small and Medium-sized Enterprises Day"),
    (6, 29, "International Day of the Tropics"),
    (6, 30, "International Asteroid Day"),
    (6, 30, "International Day of Parliamentarism"),
    (7, 5, "International Day of Cooperatives"),
    (7, 6, "World Rural Development Day"),
    (7, 7, "World Kiswahili Language Day"),
    (7, 11, "World Population Day"),
    (7, 11, "World Horse Day"),
    (7, 12, "International Day of Hope"),
    (7, 15, "World Youth Skills Day"),
    (7, 18, "Nelson Mandela International Day"),
    (7, 20, "World Chess Day"),
    (7, 20, "International Moon Day"),
    (7, 25, "World Drowning Prevention Day"),
    (7, 28, "World Hepatitis Day"),
    (7, 30, "International Day of Friendship"),
    (7, 30, "World Day against Trafficking in Persons"),
    (8, 1, "World Breastfeeding Week"),
    (8, 9, "International Day of the World's Indigenous Peoples"),
    (8, 11, "World Steelpan Day"),
    (8, 12, "International Youth Day"),
    (8, 19, "World Humanitarian Day"),
    (8, 21, "International Day of Remembrance and Tribute to the Victims of Terrorism"),
    (8, 23, "International Day for the Remembrance of the Slave Trade and Its Abolition"),
    (8, 27, "World Lake Day"),
    (8, 29, "International Day against Nuclear Tests"),
    (8, 30, "International Day of the Victims of Enforced Disappearances"),
    (8, 31, "International Day for People of African Descent"),
    (9, 5, "International Day of Charity"),
    (9, 7, "International Day of Clean Air for Blue Skies"),
    (9, 8, "International Literacy Day"),
    (9, 9, "International Day to Protect Education from Attack"),
    (9, 12, "United Nations Day for South-South Cooperation"),
    (9, 15, "International Day of Democracy"),
    (9, 16, "International Day for the Preservation of the Ozone Layer"),
    (9, 17, "World Patient Safety Day"),
    (9, 18, "International Equal Pay Day"),
    (9, 20, "World Cleanup Day"),
    (9, 21, "International Day of Peace"),
    (9, 23, "International Day of Sign Languages"),
    (9, 24, "World Maritime Day"),
    (9, 26, "International Day for the Total Elimination of Nuclear Weapons"),
    (9, 27, "World Tourism Day"),
    (9, 28, "International Day for Universal Access to Information"),
    (9, 29, "International Day of Awareness of Food Loss and Waste"),
    (9, 30, "International Translation Day"),
    (10, 1, "International Coffee Day"),
    (10, 1, "International Day of Older Persons"),
    (10, 2, "International Day of Non-Violence"),
    (10, 4, "World Space Week"),
    (10, 5, "World Teachers' Day"),
    (10, 6, "World Habitat Day"),
    (10, 7, "World Cotton Day"),
    (10, 9, "World Post Day"),
    (10, 10, "World Mental Health Day"),
    (10, 11, "International Day of the Girl Child"),
    (10, 13, "International Day for Disaster Risk Reduction"),
    (10, 15, "International Day of Rural Women"),
    (10, 16, "World Food Day"),
    (10, 23, "International Day of the Snow Leopard"),
    (10, 24, "United Nations Day"),
    (10, 24, "World Development Information Day"),
    (10, 27, "World Day for Audiovisual Heritage"),
    (10, 29, "International Day of Care and Support"),
    (10, 31, "World Cities Day"),
    (11, 2, "International Day to End Impunity for Crimes against Journalists"),
    (11, 5, "World Tsunami Awareness Day"),
    (11, 6, "International Day for Preventing the Exploitation of the Environment in War"),
    (11, 9, "International Week of Science and Peace"),
    (11, 10, "World Science Day for Peace and Development"),
    (11, 14, "World Diabetes Day"),
    (11, 16, "International Day for Tolerance"),
    (11, 17, "World Day of Remembrance for Road Traffic Victims"),
    (11, 19, "World Toilet Day"),
    (11, 20, "World Philosophy Day"),
    (11, 20, "Africa Industrialization Day"),
    (11, 20, "World Children's Day"),
    (11, 21, "World Television Day"),
    (11, 25, "International Day for the Elimination of Violence against Women"),
    (11, 26, "World Sustainable Transport Day"),
    (11, 29, "International Day of Solidarity with the Palestinian People"),
    (12, 1, "World AIDS Day"),
    (12, 2, "International Day for the Abolition of Slavery"),
    (12, 3, "International Day of Persons with Disabilities"),
    (12, 4, "International Day of Banks"),
    (12, 5, "International Volunteer Day for Economic and Social Development"),
    (12, 5, "World Soil Day"),
    (12, 7, "International Civil Aviation Day"),
    (12, 9, "International Anti-Corruption Day"),
    (12, 10, "Human Rights Day"),
    (12, 11, "International Mountain Day"),
    (12, 12, "International Universal Health Coverage Day"),
    (12, 18, "International Migrants Day"),
    (12, 18, "Arabic Language Day"),
    (12, 20, "International Human Solidarity Day"),
    (12, 21, "World Meditation Day"),
    (12, 21, "World Basketball Day"),
    (12, 27, "International Day of Epidemic Preparedness"),
)


def _slug(name: str) -> str:
    """Stable key for an international day. Derived from the name, never the
    date (`S-148`) — a dismissal has to survive into next year's rows."""
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


FIXED_INTERNATIONAL: list[Fixed] = [
    Fixed(month, day, Entry(
        key=_slug(name),
        name=name,
        kind="observance",
        tier="major" if name in _MAJOR else "minor",
        # A school assembly needs a fortnight; a day nobody is going to mark
        # needs no lead time at all and should not appear early in a queue.
        prep_days=14 if name in _MAJOR else 3,
        states=ALL_INDIA,
        source=SRC_UN,
    ))
    for month, day, name in _DAYS
]

__all__ = ["FIXED_INTERNATIONAL"]
