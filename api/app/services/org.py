"""Org settings + usage (S9). Billing lives in services/billing.py."""

import re
from zoneinfo import ZoneInfo, available_timezones

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ValidationError
from app.core.plans import limits_for
from app.core.work_types import ALLOWED_COLORS, DEFAULT_WORK_TYPE, org_categories
from app.models import Board, Membership
from app.schemas.org import (
    OrgSettingsOut,
    OrgSettingsUpdate,
    OrgUsageOut,
    PlanLimitsOut,
    WorkCategoryOut,
)


def _slug_key(label: str) -> str:
    """A stable key for a school-added category, made once from its first label
    and never regenerated on rename (D-19 rule 1)."""
    key = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return key[:40] or "category"


class OrgService:
    def __init__(self, db: Session):
        self.db = db

    def _usage(self, org_id) -> OrgUsageOut:
        boards = self.db.scalar(
            select(func.count()).select_from(Board).where(
                Board.org_id == org_id, Board.archived_at.is_(None)
            )
        )
        members = self.db.scalar(
            select(func.count()).select_from(Membership).where(
                Membership.org_id == org_id, Membership.status == "active"
            )
        )
        return OrgUsageOut(boards=boards or 0, members=members or 0)

    def settings(self, member: CurrentMember) -> OrgSettingsOut:
        org = member.org
        lim = limits_for(org.plan)
        return OrgSettingsOut(
            id=org.id,
            name=org.name,
            timezone=org.timezone,
            report_card_hour=org.report_card_hour,
            plan=org.plan,
            plan_status=org.plan_status,
            plan_renews_at=org.plan_renews_at,
            school_code=org.school_code,
            address=org.address,
            state=org.state,
            board=org.board,
            phone=org.phone,
            attendance_mode=org.attendance_mode,
            min_attendance_pct=org.min_attendance_pct,
            homework_gap_days=org.homework_gap_days,
            agent_access=org.agent_access,
            training_data_opt_in=org.training_data_opt_in,
            work_categories=[WorkCategoryOut(**c) for c in org_categories(org)],
            limits=PlanLimitsOut(
                boards=lim.boards, members=lim.members, report_days=lim.report_days,
                report_card=lim.report_card, attachments=lim.attachments, critical=lim.critical,
            ),
            usage=self._usage(org.id),
        )

    def update(self, admin: CurrentMember, req: OrgSettingsUpdate) -> OrgSettingsOut:
        org = admin.org
        if req.name is not None:
            org.name = req.name
        if req.timezone is not None:
            if req.timezone not in available_timezones():
                raise ValidationError("Unknown timezone.", code="bad_timezone")
            ZoneInfo(req.timezone)  # belt-and-suspenders
            org.timezone = req.timezone
        if req.report_card_hour is not None:
            org.report_card_hour = req.report_card_hour
        for field in ("address", "state", "board", "phone", "attendance_mode",
                      "min_attendance_pct", "homework_gap_days", "agent_access",
                      "training_data_opt_in"):
            value = getattr(req, field)
            if value is not None:
                setattr(org, field, value)
        if req.work_categories is not None:
            org.work_categories = self._merge_categories(org, req.work_categories)
        self.db.flush()
        return self.settings(admin)

    def _merge_categories(self, org, incoming) -> list[dict]:
        """D-19/S-69 — the four rules, applied server-side so no client can
        break them: stable keys (a rename keeps its key; a new label mints one,
        once) · retire never delete (a key missing from the payload is kept,
        retired) · `other` always present and active."""
        current = {c["key"]: c for c in org_categories(org)}
        out: list[dict] = []
        seen: set[str] = set()
        for entry in incoming:
            key = (entry.key or "").strip() or _slug_key(entry.label)
            base = key
            n = 2
            while key in seen:  # two new categories with the same label
                key = f"{base}_{n}"
                n += 1
            seen.add(key)
            # V1-16: an unknown colour is refused rather than stored. Silently
            # dropping it would leave the admin looking at a swatch they picked
            # and a grid that ignored it.
            if entry.color is not None and entry.color not in ALLOWED_COLORS:
                raise ValidationError(
                    "Pick one of the board colours — a colour typed by hand has not "
                    "been checked for colour-blind readers.", code="bad_category_color")
            color = entry.color or current.get(key, {}).get("color")
            out.append({"key": key, "label": entry.label.strip() or key,
                        "active": entry.active,
                        **({"color": color} if color else {})})
        # Rule 2: anything the payload dropped is retired, not deleted — its
        # historical rows keep rendering under its last label.
        for key, cat in current.items():
            if key not in seen:
                out.append({**cat, "active": False})
        # Rule 4: `other` survives everything.
        for row in out:
            if row["key"] == DEFAULT_WORK_TYPE:
                row["active"] = True
                break
        else:
            out.append({"key": DEFAULT_WORK_TYPE, "label": "Other", "active": True})
        if sum(1 for r in out if r["active"]) > 12:
            raise ValidationError(
                "Keep the visible list under 12 — a long picker stops getting filled in. "
                "Retire what you don't use.", code="too_many_categories")
        return out
