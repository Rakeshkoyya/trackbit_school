"""Bootstrap a PRODUCTION database: the platform operator account, nothing else.

This is deliberately NOT `scripts.seed` — that one builds the whole fake demo
school (students, timetable, attendance, fees, a generated daily report) and
wipes/recreates it by name. Running it against production would fill a real
database with invented data. This script creates only what is needed to log in
as the super-admin and create the first real school through /platform.

What it creates:
  1. the operator User with is_super_admin=True
  2. a home Organization for that user, because `AuthService.login` refuses any
     account with no active membership ("This account is not active in any
     organization") — the operator needs one org to anchor their first session.
     Real schools are created afterwards from /platform, and the operator
     auto-joins each as admin, so login lands them in whichever they touched last.
  3. the starter "General" board that every org gets on registration

Idempotent: re-running updates the operator's password and leaves everything else
alone. Safe to run against a database that already has schools in it.

Usage (PowerShell), from api/:
    $env:SUPER_ADMIN_EMAIL = 'you@yourdomain.com'      # optional
    $env:SUPER_ADMIN_PASSWORD = 'choose-a-strong-one'  # optional; generated if unset
    uv run python -m scripts.seed_platform
"""

import os
import secrets
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Board, BoardMember, Membership, Organization, User

EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "super@trackbit.app")
NAME = os.environ.get("SUPER_ADMIN_NAME", "TrackBit Ops")
ORG_NAME = os.environ.get("PLATFORM_ORG_NAME", "TrackBit Platform")
TIMEZONE = os.environ.get("PLATFORM_TIMEZONE", "Asia/Kolkata")


def main() -> int:
    # No password in the repo and none in the shell history unless you chose one.
    password = os.environ.get("SUPER_ADMIN_PASSWORD")
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(12)

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == EMAIL))
        if user is None:
            user = User(name=NAME, email=EMAIL,
                        password_hash=hash_password(password),
                        is_super_admin=True, must_set_password=False)
            db.add(user)
            db.flush()
            print(f"user {EMAIL}: created")
        else:
            user.password_hash = hash_password(password)
            user.is_super_admin = True
            user.must_set_password = False
            db.flush()
            print(f"user {EMAIL}: existed -> password reset, super-admin ensured")

        org = db.scalar(select(Organization).where(Organization.name == ORG_NAME))
        if org is None:
            org = Organization(name=ORG_NAME, timezone=TIMEZONE)
            db.add(org)
            db.flush()
            print(f"org '{ORG_NAME}': created")
        else:
            print(f"org '{ORG_NAME}': existed")

        membership = db.scalar(select(Membership).where(
            Membership.org_id == org.id, Membership.user_id == user.id))
        if membership is None:
            db.add(Membership(org_id=org.id, user_id=user.id, org_role="admin",
                              last_active_at=datetime.now(UTC)))
            print("membership: created (admin)")
        else:
            membership.status = "active"
            membership.org_role = "admin"
            print("membership: existed -> ensured active admin")
        db.flush()

        board = db.scalar(select(Board).where(
            Board.org_id == org.id, Board.name == "General"))
        if board is None:
            board = Board(org_id=org.id, name="General", visibility="public",
                          category="tasks", created_by=user.id, owner_id=user.id)
            db.add(board)
            db.flush()
            db.add(BoardMember(board_id=board.id, user_id=user.id))
            print("board 'General': created")

        db.commit()
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("  Log in at your frontend with:")
    print(f"    email:    {EMAIL}")
    if generated:
        print(f"    password: {password}")
        print("\n  Generated — it is not stored anywhere. Save it now.")
    else:
        print("    password: (the SUPER_ADMIN_PASSWORD you supplied)")
    print("=" * 60)
    print("\n  You land on /platform. Use 'New school' there to create the first")
    print("  real school; you auto-join it as admin and can run its setup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
