"""Daily report endpoints (V2-M6, SPRD2 §5.6).

Admin-only — the report includes a fees section (§3.3) and leads the Dashboard.
GET generates-if-absent so the report exists on demand; the scheduler also
generates it at 19:00 / regenerates at 06:00 / notifies admins at 08:00."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.schemas.reports_daily import DailyReportOut
from app.services.daily_report import DailyReportService

router = APIRouter()


@router.get("/daily", response_model=DailyReportOut)
def daily_report(on_date: date | None = None, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    return DailyReportService(db).get_or_create(m, on_date)


@router.post("/daily/regenerate", response_model=DailyReportOut)
def regenerate(on_date: date | None = None, m: CurrentMember = Depends(require_admin),
               db: Session = Depends(get_db)):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    d = on_date or datetime.now(ZoneInfo(m.org.timezone)).date()
    DailyReportService(db).generate(m.org, d, include_fees=m.is_admin)
    return DailyReportService(db).get_or_create(m, d)
