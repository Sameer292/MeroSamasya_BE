from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app.models.models import KycSubmission
from app.schemas.admin_kyc import KycSort


def submission_day_filters(day: date | None):
    if day is None:
        return []
    start = datetime.combine(day, time.min, tzinfo=ZoneInfo("Asia/Kathmandu"))
    filters = []
    if day != date.min:
        filters.append(KycSubmission.created_at >= start.astimezone(UTC))
    if day != date.max:
        filters.append(KycSubmission.created_at < (start + timedelta(days=1)).astimezone(UTC))
    return filters


def submission_order(sort: KycSort):
    created = KycSubmission.created_at
    record_id = KycSubmission.id
    name = func.lower(KycSubmission.full_name)
    newest = (created.desc().nulls_last(), record_id.desc())
    if sort == "oldest":
        return created.asc().nulls_last(), record_id.asc()
    if sort == "name_asc":
        return name.asc(), *newest
    if sort == "name_desc":
        return name.desc(), *newest
    return newest
