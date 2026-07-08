"""Background jobs (plan §8.5). Each opens its own session and is idempotent.

- materializer  : spawn today+tomorrow's recurring instances per org
- miss_marker   : flip yesterday's still-open dated instances to 'missed'
- sweep         : deliver due+pending notifications (retry x3 with backoff)
- digest        : org-local 8 AM per-member summary (Monday = weekly recap)
- nudge_scan    : gentle overdue nudge once, ~1h after due
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timeutil import org_day_bounds
from app.models import (
    AttendanceException,
    AttendanceMark,
    ClassSubject,
    DailyReport,
    Guardian,
    HomeworkAssignment,
    LessonLog,
    Membership,
    Notification,
    Organization,
    Student,
    TaskInstance,
    TimetableSlot,
    User,
)
from app.services import events, notifications
from app.services.dispatcher import deliver
from app.services.notify_guardian import notify_guardians
from app.services.recurrence import RecurringService

logger = logging.getLogger("trackbit.jobs")

_MAX_RETRIES = 3
_BACKOFF = [60, 300, 900]  # seconds after each failed attempt


def _session() -> Session:
    return SessionLocal()


def _active_orgs(db: Session) -> list[Organization]:
    return list(db.scalars(select(Organization)))


# ---- materializer + miss-marker ---------------------------------------
def run_materializer() -> int:
    db = _session()
    try:
        total = 0
        svc = RecurringService(db)
        for org in _active_orgs(db):
            _, _, now_local = org_day_bounds(org.timezone)
            today = now_local.date()
            total += svc.materialize_org(org, [today, today + timedelta(days=1)])
        db.commit()
        logger.info("materializer created %d instances", total)
        return total
    except Exception:
        db.rollback()
        logger.exception("materializer failed")
        return 0
    finally:
        db.close()


def run_miss_marker() -> int:
    db = _session()
    try:
        marked = 0
        for org in _active_orgs(db):
            start, _, _ = org_day_bounds(org.timezone)  # today's local midnight (UTC)
            overdue = db.scalars(
                select(TaskInstance).where(
                    TaskInstance.org_id == org.id,
                    TaskInstance.status == "open",
                    TaskInstance.due_at.isnot(None),
                    TaskInstance.due_at < start,
                )
            )
            for inst in overdue:
                inst.status = "missed"
                events.append_event(db, org_id=org.id, instance_id=inst.id,
                                    event_type="missed", actor_id=None)
                marked += 1
        db.commit()
        logger.info("miss-marker flipped %d instances", marked)
        return marked
    except Exception:
        db.rollback()
        logger.exception("miss-marker failed")
        return 0
    finally:
        db.close()


# ---- notification sweep -----------------------------------------------
def run_sweep() -> dict:
    db = _session()
    try:
        now = datetime.now(UTC)
        due = db.scalars(
            select(Notification)
            .where(Notification.status == "pending", Notification.scheduled_at <= now)
            .limit(200)
        )
        sent = failed = 0
        for n in due:
            ok = deliver(db, n)
            if ok:
                sent += 1
            else:
                n.retry_count += 1
                if n.retry_count >= _MAX_RETRIES:
                    n.status = "failed"
                    failed += 1
                else:
                    n.status = "pending"
                    backoff = _BACKOFF[min(n.retry_count - 1, len(_BACKOFF) - 1)]
                    n.scheduled_at = now + timedelta(seconds=backoff)
        db.commit()
        if sent or failed:
            logger.info("sweep: sent=%d failed=%d", sent, failed)
        return {"sent": sent, "failed": failed}
    except Exception:
        db.rollback()
        logger.exception("sweep failed")
        return {"sent": 0, "failed": 0}
    finally:
        db.close()


def failed_count() -> int:
    db = _session()
    try:
        return len(list(db.scalars(select(Notification.id).where(Notification.status == "failed"))))
    finally:
        db.close()


# ---- digest + nudge ----------------------------------------------------
def run_digest() -> int:
    """Per member, at org-local 8 AM, a summary of today (skip empty days)."""
    db = _session()
    try:
        made = 0
        for org in _active_orgs(db):
            start, end, now_local = org_day_bounds(org.timezone)
            if now_local.hour != 8:
                continue
            is_monday = now_local.weekday() == 0
            members = db.execute(
                select(Membership.user_id, User).join(User, User.id == Membership.user_id)
                .where(Membership.org_id == org.id, Membership.status == "active")
            ).all()
            for uid, user in members:
                count = len(list(db.scalars(
                    select(TaskInstance.id).where(
                        TaskInstance.org_id == org.id, TaskInstance.assignee_id == uid,
                        TaskInstance.status.in_(("open", "missed")),
                        TaskInstance.due_at < end,
                    )
                )))
                if count == 0 and not is_monday:
                    continue
                subject = "Your week on TrackBit" if is_monday else "Your day on TrackBit"
                body = (
                    f"Good morning {user.name.split()[0]} — you have {count} "
                    f"{'task' if count == 1 else 'tasks'} today."
                )
                key = f"digest:{uid}:{now_local.date()}"
                n = notifications.enqueue(
                    db, org_id=org.id, user_id=uid, instance_id=None, notif_type="digest",
                    channel="email", payload={"subject": subject, "body": body},
                    dedupe_key=key,
                )
                if n:
                    made += 1
        db.commit()
        return made
    except Exception:
        db.rollback()
        logger.exception("digest failed")
        return 0
    finally:
        db.close()


def run_report_card() -> int:
    """At org-local report_card_hour, send each admin the day's close-out (F7).

    The admin's return ritual: "<Org> today: 82% · 3 still open" — calm, never
    "Anil failed." Numbers are the public-boards rollup (D7); private work never
    surfaces. Deduped once per org per day.
    """
    db = _session()
    try:
        from app.core.plans import limits_for
        from app.services.reports import ReportService

        made = 0
        for org in _active_orgs(db):
            if not limits_for(org.plan).report_card:
                continue  # EOD report card is a Pro surface (R6)
            _, _, now_local = org_day_bounds(org.timezone)
            if now_local.hour != org.report_card_hour:
                continue
            rollup = ReportService(db).org_dashboard(org.id, org.timezone, "today")
            still_open = rollup.total - rollup.done
            subject = f"{org.name} — today's wrap-up"
            if rollup.total == 0:
                body = f"{org.name}: a quiet day — nothing was scheduled. 🌙"
            else:
                open_word = "thing" if still_open == 1 else "things"
                body = (
                    f"{org.name} today: {rollup.completion_pct}% done"
                    f"{f' · {still_open} {open_word} still open' if still_open else ' · all clear ✓'}."
                )
            admins = db.execute(
                select(Membership.user_id, User).join(User, User.id == Membership.user_id)
                .where(
                    Membership.org_id == org.id,
                    Membership.status == "active",
                    Membership.org_role == "admin",
                )
            ).all()
            for uid, _user in admins:
                key = f"report_card:{org.id}:{now_local.date()}:{uid}"
                n = notifications.enqueue(
                    db, org_id=org.id, user_id=uid, instance_id=None,
                    notif_type="report_card", channel="email",
                    payload={"subject": subject, "body": body}, dedupe_key=key,
                )
                if n:
                    made += 1
        db.commit()
        logger.info("report-card queued %d notifications", made)
        return made
    except Exception:
        db.rollback()
        logger.exception("report-card failed")
        return 0
    finally:
        db.close()


def run_nudge_scan() -> int:
    """Overdue ~1h, still open, assigned → one gentle nudge."""
    db = _session()
    try:
        made = 0
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=1)
        for org in _active_orgs(db):
            overdue = db.scalars(
                select(TaskInstance).where(
                    TaskInstance.org_id == org.id, TaskInstance.status == "open",
                    TaskInstance.assignee_id.isnot(None),
                    TaskInstance.due_at.isnot(None), TaskInstance.due_at <= cutoff,
                )
            )
            for inst in overdue:
                before = db.scalar(
                    select(Notification.id).where(Notification.dedupe_key == f"overdue:{inst.id}")
                )
                if before is None:
                    notifications.enqueue_overdue_nudge(db, inst, when=now)
                    made += 1
        db.commit()
        return made
    except Exception:
        db.rollback()
        logger.exception("nudge scan failed")
        return 0
    finally:
        db.close()


def run_grace_downgrade() -> int:
    """After a failed payment we hold Pro for a grace window; once it lapses,
    drop to Free limits — non-destructively (nothing is deleted)."""
    db = _session()
    try:
        from app.services.billing import BillingService

        now = datetime.now(UTC)
        stale = db.scalars(
            select(Organization).where(
                Organization.plan_status == "grace",
                Organization.grace_until.isnot(None),
                Organization.grace_until < now,
            )
        )
        n = 0
        for org in stale:
            BillingService._downgrade(org)
            n += 1
        db.commit()
        if n:
            logger.info("grace downgrade: %d orgs", n)
        return n
    except Exception:
        db.rollback()
        logger.exception("grace downgrade failed")
        return 0
    finally:
        db.close()


# ---- V2-P4: daily report + reminders (SPRD2 §5.6, §7, §9) --------------
def run_daily_report() -> int:
    """Org-local 19:00 draft the day's report; 06:00 regenerate a draft if late data
    arrived; 08:00 notify admins yesterday's report is ready. Idempotent per (org,
    date): generate upserts one row and never overwrites a final."""
    from datetime import date as _date

    from sqlalchemy import select as _select

    from app.services.daily_report import DailyReportService

    db = _session()
    try:
        made = 0
        svc = DailyReportService(db)
        for org in _active_orgs(db):
            _, _, now_local = org_day_bounds(org.timezone)
            today: _date = now_local.date()
            yest = today - timedelta(days=1)
            if now_local.hour == 19:
                svc.generate(org, today)
            elif now_local.hour == 6:
                svc.generate(org, yest, only_if_draft=True)
            elif now_local.hour == 8:
                report = db.scalar(_select(DailyReport).where(
                    DailyReport.org_id == org.id, DailyReport.for_date == yest)) \
                    or svc.generate(org, yest)
                if report is None:
                    continue
                risks = len((report.highlights or {}).get("risks", []))
                body = (f"{org.name} — {yest}: {risks} thing(s) need attention."
                        if risks else f"{org.name} — {yest}: a calm day, nothing flagged.")
                admins = db.execute(
                    _select(Membership.user_id).where(
                        Membership.org_id == org.id, Membership.status == "active",
                        Membership.org_role == "admin")).all()
                for (uid,) in admins:
                    n = notifications.enqueue(
                        db, org_id=org.id, user_id=uid, instance_id=None,
                        notif_type="daily_report", channel="email",
                        payload={"subject": f"{org.name} daily report", "body": body},
                        dedupe_key=f"daily_report:{org.id}:{yest}:{uid}")
                    if n:
                        made += 1
        db.commit()
        logger.info("daily-report job: %d admin notifications", made)
        return made
    except Exception:
        db.rollback()
        logger.exception("daily-report job failed")
        return 0
    finally:
        db.close()


def run_teacher_reminder() -> int:
    """Org-local 16:00 — nudge each teacher about classes still unmarked/unlogged
    today (§7). One reminder per teacher per day (dedupe)."""
    from sqlalchemy import or_ as _or
    from sqlalchemy import select as _select

    db = _session()
    try:
        made = 0
        for org in _active_orgs(db):
            _, _, now_local = org_day_bounds(org.timezone)
            if now_local.hour != 16:
                continue
            d = now_local.date()
            slots = list(db.scalars(_select(TimetableSlot).where(
                TimetableSlot.org_id == org.id, TimetableSlot.weekday == d.weekday(),
                TimetableSlot.effective_from <= d,
                _or(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d))))
            if not slots:
                continue
            teacher_of = dict(db.execute(_select(
                ClassSubject.id, ClassSubject.teacher_member_id).where(
                ClassSubject.org_id == org.id)).all())
            marked = {(mk.class_id, mk.period_no) for mk in db.scalars(_select(AttendanceMark).where(
                AttendanceMark.org_id == org.id, AttendanceMark.date == d))}
            logged = set(db.scalars(_select(LessonLog.class_subject_id).where(
                LessonLog.org_id == org.id, LessonLog.date == d)))
            # tally per teacher membership
            pending: dict = {}
            for s in slots:
                tmid = teacher_of.get(s.class_subject_id)
                if tmid is None:
                    continue
                unmarked = (s.class_id, s.period_no) not in marked
                unlogged = s.class_subject_id not in logged
                if unmarked or unlogged:
                    pending[tmid] = pending.get(tmid, 0) + 1
            for tmid, count in pending.items():
                membership = db.get(Membership, tmid)
                if membership is None or membership.status != "active":
                    continue
                n = notifications.enqueue(
                    db, org_id=org.id, user_id=membership.user_id, instance_id=None,
                    notif_type="teacher_reminder", channel="push",
                    payload={"subject": "Wrap up your day",
                             "body": f"You have {count} class-period(s) not yet marked or logged."},
                    dedupe_key=f"teacher_reminder:{membership.user_id}:{d}")
                if n:
                    made += 1
        db.commit()
        logger.info("teacher-reminder job: %d notifications", made)
        return made
    except Exception:
        db.rollback()
        logger.exception("teacher-reminder job failed")
        return 0
    finally:
        db.close()


def run_saturday_summary() -> int:
    """Saturday org-local 08:00 — a light weekly note to each student's guardians:
    homework set this week + absences (§7). Guardian channel is the WhatsApp stub."""
    from sqlalchemy import func as _func
    from sqlalchemy import select as _select

    db = _session()
    try:
        sent = 0
        for org in _active_orgs(db):
            _, _, now_local = org_day_bounds(org.timezone)
            if now_local.weekday() != 5 or now_local.hour != 8:
                continue
            d = now_local.date()
            week_start = d - timedelta(days=6)
            students = list(db.scalars(_select(Student).where(
                Student.org_id == org.id, Student.status == "active",
                Student.class_id.isnot(None))))
            for st in students:
                hw = db.scalar(_select(_func.count(HomeworkAssignment.id))
                    .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
                    .where(HomeworkAssignment.org_id == org.id,
                           ClassSubject.class_id == st.class_id,
                           HomeworkAssignment.date >= week_start,
                           HomeworkAssignment.date <= d)) or 0
                absences = db.scalar(_select(_func.count(AttendanceException.id))
                    .join(AttendanceMark, AttendanceMark.id == AttendanceException.mark_id)
                    .where(AttendanceMark.org_id == org.id,
                           AttendanceException.student_id == st.id,
                           AttendanceException.status == "absent",
                           AttendanceMark.date >= week_start, AttendanceMark.date <= d)) or 0
                recipients = list(db.execute(_select(Guardian.phone, Guardian.notify_opt_out)
                    .where(Guardian.org_id == org.id, Guardian.student_id == st.id)).all())
                if not recipients:
                    continue
                msg = (f"{st.full_name} this week at {org.name}: {hw} homework set, "
                       f"{absences} day(s) absent.")
                sent += notify_guardians([(p, o) for p, o in recipients], msg)
        db.commit()
        logger.info("saturday-summary job: %d guardian messages", sent)
        return sent
    except Exception:
        db.rollback()
        logger.exception("saturday-summary job failed")
        return 0
    finally:
        db.close()


def run_hourly() -> None:
    """The hourly tick: materialize, miss-mark, digest, report card, nudge, grace,
    plus V2 daily report, teacher reminder, and Saturday guardian summary."""
    run_materializer()
    run_miss_marker()
    run_digest()
    run_report_card()
    run_nudge_scan()
    run_grace_downgrade()
    run_daily_report()
    run_teacher_reminder()
    run_saturday_summary()
