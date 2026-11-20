import math
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.models.models import Category, Issue, IssueMedia, Upvote
from app.models.issue_moderation import IssueModerationEvent
from app.schemas.enum import IssueStatusEnum
from app.schemas.schema import (
    CitizenIssueQuery, IssueCreate, IssueUpdate, IssueData, IssueDetailData,
)
from app.services.image_upload import read_image_upload
from app.services.notification_service import notify
from app.services.photo_storage import PhotoChanges, change_photos
from app.services.report_area_service import report_feed_area_ids, validate_report_area

MAX_IMAGES = 3


def validate_image_files(images: list[UploadFile]):
    if len(images) > MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can upload a maximum of {MAX_IMAGES} images.",
        )


async def upload_issue_photos(photos: PhotoChanges, images: list[UploadFile]) -> list[str]:
    urls = []
    for index, image in enumerate(images):
        data, content_type = await read_image_upload(image, "images", index)
        urls.append(await photos.upload(data, "issues", content_type))
    return urls


def attach_votes(issues: list, current_user_id: str | None):
    for issue in issues:
        issue.upvote_count = len(issue.upvotes)
        issue.has_upvoted = (
            any(v.user_id == current_user_id for v in issue.upvotes)
            if current_user_id
            else False
        )
    return issues


async def create_issue(
    data: IssueCreate,
    citizen_id: str,
    db: AsyncSession,
    images: list[UploadFile],
):
    submission_id = str(data.submission_id)
    submission = (
        select(Issue)
        .where(Issue.citizen_id == citizen_id, Issue.submission_id == submission_id)
        .options(
            selectinload(Issue.media),
            selectinload(Issue.category),
            selectinload(Issue.upvotes),
        )
        .execution_options(populate_existing=True)
    )

    try:
        issue = await db.scalar(submission)
        if issue is None:
            category = await db.scalar(
                select(Category).where(Category.id == data.category_id, Category.deleted_at.is_(None))
            )
            if category is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
            if not images:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload at least 1 image."
                )
            validate_image_files(images)

            try:
                async with change_photos(db) as photos:
                    local_level_id = await validate_report_area(
                        db, data.local_level_id, data.latitude, data.longitude
                    )
                    urls = await upload_issue_photos(photos, images)
                    db.add(Issue(
                        citizen_id=citizen_id,
                        submission_id=submission_id,
                        category_id=data.category_id,
                        title=data.title,
                        description=data.description,
                        latitude=data.latitude,
                        longitude=data.longitude,
                        address=data.address,
                        local_level_id=local_level_id,
                        media=[IssueMedia(url=url) for url in urls],
                    ))
            except IntegrityError:
                # change_photos rolls back the losing insert and cleans up its uploads.
                issue = await db.scalar(submission)
                if issue is None:
                    raise
            else:
                issue = (await db.execute(submission)).scalar_one()
        attach_votes([issue], citizen_id)
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issue. Please try again.",
        )

    return {
        "message": "Issue created successfully",
        "data": issue,
    }


async def get_my_issues(citizen_id: str, query: CitizenIssueQuery, db: AsyncSession):
    return await list_issues(query, db, citizen_id, Issue.citizen_id == citizen_id)


async def get_issue_by_id(
    issue_id: str,
    db: AsyncSession,
    current_user_id: str | None = None,
    *,
    for_update: bool = False,
):
    try:
        statement = (
            select(Issue)
            .where(Issue.id == issue_id, Issue.deleted_at.is_(None))
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
                selectinload(Issue.upvotes),
            )
        )
        if for_update:
            if db.get_bind().dialect.name == "sqlite":
                # SQLite ignores SELECT FOR UPDATE. Take its write lock before reading media.
                await db.execute(update(Issue.__table__).where(Issue.id == issue_id)
                                 .values(updated_at=Issue.updated_at))
            statement = statement.with_for_update().execution_options(populate_existing=True)
        issue = await db.scalar(statement)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issue.",
        )

    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found.",
        )

    attach_votes([issue], current_user_id)

    return {
        "message": "Issue fetched successfully",
        "data": issue,
    }


async def get_issue_detail(issue_id: str, db: AsyncSession, current_user_id: str):
    response = await get_issue_by_id(issue_id, db, current_user_id)
    issue = response["data"]
    events = await db.scalars(
        select(IssueModerationEvent)
        .where(IssueModerationEvent.issue_id == issue_id)
        .order_by(IssueModerationEvent.created_at, IssueModerationEvent.id)
    )
    # SQLite returns naive UTC timestamps; include the zone for citizen devices.
    updates = [{
        "status": IssueStatusEnum.open,
        "created_at": issue.created_at.replace(tzinfo=issue.created_at.tzinfo or timezone.utc),
    }]
    updates.extend(
        {
            "status": change["current"],
            "created_at": event.created_at.replace(tzinfo=event.created_at.tzinfo or timezone.utc),
        }
        for event in events
        for change in event.changes
        if change["field"] == "status"
    )
    return {
        "message": response["message"],
        "data": IssueDetailData.model_validate({
            **IssueData.model_validate(issue).model_dump(),
            "status_updates": updates,
        }),
    }


async def delete_issue(
    issue_id: str, citizen_id: str, delete_reason: str | None, db: AsyncSession
):
    issue_response = await get_issue_by_id(issue_id, db, citizen_id, for_update=True)
    issue = issue_response["data"]

    if issue.citizen_id != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this issue.",
        )

    if issue.status != IssueStatusEnum.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only open issues can be deleted.",
        )

    try:
        async with change_photos(db) as photos:
            issue.deleted_at = datetime.now(timezone.utc)
            issue.delete_reason = delete_reason
            urls = {media.url for media in issue.media}
            issue.media.clear()
            for url in urls:
                await photos.retire(url)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete issue.",
        )

    return {"message": "Issue deleted successfully.", "data": {"id": issue_id}}


async def get_editable_issue(issue_id: str, citizen_id: str, db: AsyncSession, *, lock: bool):
    issue_response = await get_issue_by_id(issue_id, db, citizen_id, for_update=lock)
    issue = issue_response["data"]

    if issue.citizen_id != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to edit this issue.",
        )

    if issue.status != IssueStatusEnum.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only open issues can be edited.",
        )
    return issue


async def update_issue(
    issue_id: str,
    citizen_id: str,
    data: IssueUpdate,
    db: AsyncSession,
    images: list[UploadFile] = [],
    retained_media_ids: list[str] | None = None,
):
    if images:
        await get_editable_issue(issue_id, citizen_id, db, lock=False)

    validate_image_files(images)

    try:
        async with change_photos(db) as photos:
            urls = await upload_issue_photos(photos, images)
            issue = await get_editable_issue(issue_id, citizen_id, db, lock=True)
            if data.category_id is not None and data.category_id != issue.category_id:
                category = await db.scalar(
                    select(Category).where(Category.id == data.category_id, Category.deleted_at.is_(None))
                )
                if category is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="Category not found."
                    )

            pin_fields = ("latitude", "longitude", "local_level_id")
            if any(getattr(data, field) is not None for field in pin_fields):
                issue.local_level_id = await validate_report_area(
                    db, data.local_level_id, data.latitude, data.longitude
                )
                issue.latitude = data.latitude
                issue.longitude = data.longitude
                # Write all three values even if another edit changed one since we loaded the issue.
                for field in pin_fields:
                    flag_modified(issue, field)
            for field in ("category_id", "title"):
                if (value := getattr(data, field)) is not None:
                    setattr(issue, field, value)
            for field in ("description", "address"):
                if field in data.model_fields_set:
                    setattr(issue, field, getattr(data, field))

            # Omitted retained IDs preserve the gallery unless new files replace it.
            if urls or retained_media_ids is not None:
                retained_ids = set(retained_media_ids or [])
                if not retained_ids <= {media.id for media in issue.media}:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid media id in retained_media_ids.",
                    )
                if not 1 <= len(retained_ids) + len(urls) <= MAX_IMAGES:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Issue must end with 1 to {MAX_IMAGES} photos.",
                    )
                removed = {media.url for media in issue.media if media.id not in retained_ids}
                issue.media = [media for media in issue.media if media.id in retained_ids]
                issue.media.extend(IssueMedia(url=url) for url in urls)
                for url in removed - {media.url for media in issue.media}:
                    await photos.retire(url)

        db.expire_all()

        result = await db.execute(
            select(Issue)
            .where(Issue.id == issue_id)
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
                selectinload(Issue.upvotes),
            )
        )
        updated_issue = result.scalar_one()
        attach_votes([updated_issue], citizen_id)
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issue. Please try again.",
        )

    return {
        "message": "Issue updated successfully",
        "data": updated_issue,
    }


async def list_issues(
    query: CitizenIssueQuery, db: AsyncSession, current_user_id: str | None, *scope
):
    conditions = [Issue.deleted_at.is_(None), *scope]
    if query.category_id:
        conditions.append(Issue.category_id == query.category_id)
    if query.search:
        conditions.append(
            or_(
                Issue.title.icontains(query.search, autoescape=True),
                Issue.description.icontains(query.search, autoescape=True),
                Issue.address.icontains(query.search, autoescape=True),
                Issue.category.has(
                    Category.name.icontains(query.search, autoescape=True)
                ),
            )
        )
    try:
        # Status chips count the search/category matches before status selection.
        counts = await db.execute(
            select(Issue.status, func.count(Issue.id))
            .where(*conditions)
            .group_by(Issue.status)
        )
        status_counts = {state: 0 for state in IssueStatusEnum}
        status_counts.update(dict(counts.all()))
        total = (
            status_counts[query.status] if query.status else sum(status_counts.values())
        )
        if query.status:
            conditions.append(Issue.status == query.status)
        result = await db.execute(
            select(Issue)
            .where(*conditions)
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
                selectinload(Issue.upvotes),
            )
            .order_by(Issue.created_at.desc(), Issue.id.desc())
            .offset((query.page - 1) * query.limit)
            .limit(query.limit)
        )
        issues = attach_votes(list(result.scalars().all()), current_user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issues.",
        )
    return {
        "message": "Issues fetched successfully",
        "data": {
            "meta": {
                "total": total,
                "page": query.page,
                "limit": query.limit,
                "total_pages": math.ceil(total / query.limit),
            },
            "status_counts": status_counts,
            "issues": issues,
        },
    }


async def get_all_issues(
    query: CitizenIssueQuery, db: AsyncSession, current_user_id: str | None = None
):
    return await list_issues(query, db, current_user_id)


async def get_issues_by_location(
    location_id: str | None,
    query: CitizenIssueQuery,
    db: AsyncSession,
    current_user_id: str | None = None,
):
    if not location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no location set.",
        )
    try:
        area_ids = await report_feed_area_ids(db, location_id)
        return await list_issues(
            query, db, current_user_id, Issue.local_level_id.in_(area_ids)
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issues.",
        )


async def set_vote(issue_id: str, user_id: str, upvoted: bool, db: AsyncSession):
    issue_response = await get_issue_by_id(issue_id, db, user_id, for_update=True)
    issue = issue_response["data"]

    try:
        vote = next((vote for vote in issue.upvotes if vote.user_id == user_id), None)
        count = issue.upvote_count
        if upvoted and vote is None:
            db.add(Upvote(user_id=user_id, issue_id=issue.id))
            count += 1
            if issue.citizen_id and issue.citizen_id != user_id:
                notify(
                    db,
                    issue.citizen_id,
                    "upvote",
                    "New upvote",
                    f"Your report '{issue.title}' received an upvote.",
                    issue_id=issue.id,
                )
        elif not upvoted and vote is not None:
            await db.delete(vote)
            count -= 1
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update upvote.",
        )

    return {
        "message": "Upvoted successfully" if upvoted else "Upvote removed",
        "data": {"upvoted": upvoted, "upvote_count": count},
    }
