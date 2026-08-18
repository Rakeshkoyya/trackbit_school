"""The shape of a school day — what a period *is*, and what it asks for (TT-2).

Two vocabularies live here, and nothing else in the codebase may re-derive either.

1. **Entry kinds** — what a row of the bell schedule is. `period` is teachable time
   and takes a number; everything else is a gap. The numbering rule that the whole
   app depends on is stated once, in `school_clock`, and it reads `PERIOD_KIND`
   from here.

2. **Block kinds** — what a non-subject period is, and therefore *what the teacher
   is asked to capture in it*. Before TT-2 this was three strings on
   `sessions.kind` with the capture surface chosen by `if kind == "..."` in two
   services and one React component. A sports period and a homework class differ
   in exactly one thing — the set of things worth recording — so that set is the
   data, and every surface reads it from `CAPTURE`.

The pairing matters: a slot's kind decides the teacher's My Day row, the capture
screen she lands on, and which writes the API will accept for that meeting. Three
answers derived from one table cannot disagree.

`web/src/lib/day-shape.ts` mirrors this file. Changing one means changing both.
"""

from __future__ import annotations

from typing import NamedTuple

#: A bell-schedule entry that is teachable time. Anything else is a break and
#: consumes no period number — see `services/school_clock.py`.
PERIOD_KIND = "period"

#: Break kinds the timings editor offers by name. Free text is still accepted —
#: `periods_before_lunch` looks for "lunch" in the kind, and an unknown kind is a
#: perfectly good break — so this is a convenience list, never a whitelist.
SUGGESTED_BREAK_KINDS: tuple[str, ...] = ("break", "lunch", "assembly", "games", "prayer")


class Capture(NamedTuple):
    """What a block of this kind asks the teacher for.

    Every flag is a *permission to record*, never an obligation: P1v2 means a
    block with `roll=True` still opens on a confirmed norm, and one with
    `class_log=True` saves fine with an empty log. The flags decide what the
    screen offers and what the API accepts — not what it demands.
    """

    label: str
    #: Short line under the block's name on My Day, before anything is captured.
    hint: str
    #: Attendance for the block's own roster. This is a second roll, never the
    #: school-day register — a child marked present at 08:20 can still miss the
    #: 18:00 game, and overwriting the morning to say so would be a lie (D-91).
    roll: bool
    #: A single note for the whole block — "what we covered today".
    class_log: bool
    #: Per-student sections, like the class deep log.
    student_logs: bool
    #: Photos and videos on the meeting (and, where allowed, on a student).
    memories: bool
    #: The class → subject → check-the-books flow (TT-2 §3).
    homework_check: bool
    #: The roll taken here IS the school-day register, for every class standing
    #: in the room (`TT-6`, founder 2026-08-18). Deliberately NOT `roll`: that one
    #: is the block's own second roll against its own roster and never touches
    #: attendance (`D-91`). This one is the opposite claim — the whole school is
    #: in front of one person at 08:20, so the register she takes there is the
    #: day's, and it is filed to each class's own `class_periods` row rather than
    #: to the meeting. A kind may sensibly have neither; no kind has both, and a
    #: kind that did would be asking a school to answer "who is here" twice.
    school_roll: bool = False


#: kind → what it captures. The `sessions.kind` CHECK constraint is generated
#: from these keys, so adding a kind here and in one migration is the whole job.
CAPTURE: dict[str, Capture] = {
    "study": Capture(
        label="Study / prep",
        hint="Evening prep",
        roll=True, class_log=False, student_logs=True, memories=True,
        homework_check=False,
    ),
    "homework": Capture(
        label="Homework class",
        hint="Check tonight's homework",
        roll=True, class_log=False, student_logs=True, memories=True,
        homework_check=True,
    ),
    "sports": Capture(
        label="Sports",
        hint="Games and practice",
        roll=True, class_log=False, student_logs=False, memories=True,
        homework_check=False,
    ),
    "activity": Capture(
        label="Activity",
        hint="Club or activity",
        roll=True, class_log=True, student_logs=False, memories=True,
        homework_check=False,
    ),
    "course": Capture(
        label="Extra course",
        hint="Extra course",
        roll=True, class_log=True, student_logs=True, memories=True,
        homework_check=False,
    ),
    "assembly": Capture(
        label="Assembly / yoga",
        # Whole-school time — and the one moment in the day when every child is
        # standing in one place in front of one person. `TT-6` (founder,
        # 2026-08-18): *"I want to take attendance of that whole school that are
        # in assembly and it should reflect in each class."* So this block takes
        # the school-day REGISTER (`school_roll`), not a roll of its own — one
        # sheet, filed to every class in the hall.
        #
        # It stays capture-by-exception, which is the only reason it fits inside
        # P1v2: nobody is entered one by one. The absentees are tapped off a
        # sheet that opens on "everyone is here", exactly as a class register
        # does, and the school of 400 costs the taps of the children who are
        # away rather than 400 taps.
        hint="Take the school register",
        roll=False, class_log=False, student_logs=False, memories=True,
        homework_check=False, school_roll=True,
    ),
}

#: Ordered for the admin's picker — the two an Indian school sets up first, then
#: the rest. Deterministic, so the dropdown never reshuffles between renders.
BLOCK_KINDS: tuple[str, ...] = (
    "homework", "study", "sports", "activity", "course", "assembly")

DEFAULT_BLOCK_KIND = "study"

#: What a timetable cell holds. The flavour of a `block` is `sessions.kind`;
#: there is deliberately no second copy of it on the slot.
SLOT_TYPES: tuple[str, ...] = ("subject", "block")
DEFAULT_SLOT_TYPE = "subject"


def is_block_kind(kind: str | None) -> bool:
    return kind in CAPTURE


def capture_for(kind: str | None) -> Capture:
    """What this kind captures.

    An unrecognised kind degrades to `study` rather than raising: a row written
    by a future version of the app must still render on an older client, and the
    safe reading of an unknown block is "somebody supervised some children".
    """
    return CAPTURE.get(kind or "", CAPTURE[DEFAULT_BLOCK_KIND])


def label_for(kind: str | None) -> str:
    return capture_for(kind).label


def kinds_sql_list() -> str:
    """The CHECK-constraint fragment, so the DB and this module cannot drift."""
    return ", ".join(f"'{k}'" for k in sorted(CAPTURE))
