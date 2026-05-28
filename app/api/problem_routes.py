from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, exists
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.core.database import get_db
from app.models.models import Problem, Vote, User
from app.schemas.problem_schema import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemListResponse,
    PaginatedProblems,
    VoteResponse,
)
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


async def build_problem_response(problem, current_user, db):
    vote_count_result = await db.execute(
        select(func.count(Vote.id)).where(Vote.problem_id == problem.id)
    )
    vote_count = vote_count_result.scalar() or 0

    has_voted_result = await db.execute(
        select(exists().where(
            Vote.problem_id == problem.id,
            Vote.user_id == current_user.id,
        ))
    )
    has_voted = has_voted_result.scalar()

    return ProblemResponse(
        id=problem.id,
        title=problem.title,
        description=problem.description,
        category=problem.category,
        image_url=problem.image_url,
        is_resolved=problem.is_resolved,
        vote_count=vote_count,
        has_voted=has_voted,
        user=problem.user,
        location_id=problem.location_id,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
    )


# ── Create Problem ────────────────────────────────────────────────────────────
@router.post("/", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    payload: ProblemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    problem = Problem(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        image_url=payload.image_url,
        location_id=payload.location_id,
        user_id=current_user.id,
    )
    db.add(problem)
    await db.commit()

    result = await db.execute(
        select(Problem)
        .where(Problem.id == problem.id)
        .options(selectinload(Problem.user))
    )
    problem = result.scalar_one()
    return await build_problem_response(problem, current_user, db)


# ── List Problems ─────────────────────────────────────────────────────────────
@router.get("/", response_model=PaginatedProblems)
async def list_problems(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    category: str = Query(default=None),
    location_id: str = Query(default=None),
    is_resolved: bool = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Problem)
        .options(selectinload(Problem.user))
        .where(Problem.deleted_at == None)
        .order_by(Problem.created_at.desc())
    )

    if category:
        query = query.where(Problem.category == category)
    if location_id:
        query = query.where(Problem.location_id == location_id)
    if is_resolved is not None:
        query = query.where(Problem.is_resolved == is_resolved)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    problems = result.scalars().all()

    items = []
    for p in problems:
        vc = await db.execute(
            select(func.count(Vote.id)).where(Vote.problem_id == p.id)
        )
        hv = await db.execute(
            select(exists().where(
                Vote.problem_id == p.id,
                Vote.user_id == current_user.id,
            ))
        )
        items.append(ProblemListResponse(
            id=p.id,
            title=p.title,
            category=p.category,
            is_resolved=p.is_resolved,
            vote_count=vc.scalar() or 0,
            has_voted=hv.scalar(),
            user=p.user,
            location_id=p.location_id,
            created_at=p.created_at,
        ))

    return PaginatedProblems(total=total, page=page, page_size=page_size, problems=items)


# ── Get Single Problem ────────────────────────────────────────────────────────
@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Problem)
        .where(Problem.id == problem_id, Problem.deleted_at == None)
        .options(selectinload(Problem.user))
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    return await build_problem_response(problem, current_user, db)


# ── Update Problem ────────────────────────────────────────────────────────────
@router.put("/{problem_id}", response_model=ProblemResponse)
async def update_problem(
    problem_id: str,
    payload: ProblemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Problem)
        .where(Problem.id == problem_id, Problem.deleted_at == None)
        .options(selectinload(Problem.user))
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if problem.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own problems")

    if payload.title is not None:
        problem.title = payload.title
    if payload.description is not None:
        problem.description = payload.description
    if payload.category is not None:
        problem.category = payload.category
    if payload.image_url is not None:
        problem.image_url = payload.image_url
    if payload.is_resolved is not None:
        problem.is_resolved = payload.is_resolved

    await db.commit()
    await db.refresh(problem)
    return await build_problem_response(problem, current_user, db)


# ── Delete Problem (soft) ─────────────────────────────────────────────────────
@router.delete("/{problem_id}")
async def delete_problem(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Problem)
        .where(Problem.id == problem_id, Problem.deleted_at == None)
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if problem.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own problems")

    problem.deleted_at = datetime.utcnow()
    await db.commit()
    return {"message": "Problem deleted successfully"}


# ── Toggle Vote ───────────────────────────────────────────────────────────────
@router.post("/{problem_id}/vote", response_model=VoteResponse)
async def toggle_vote(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Problem).where(
            Problem.id == problem_id,
            Problem.deleted_at == None
        )
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    vote_result = await db.execute(
        select(Vote).where(
            Vote.problem_id == problem_id,
            Vote.user_id == current_user.id,
        )
    )
    existing_vote = vote_result.scalar_one_or_none()

    if existing_vote:
        await db.delete(existing_vote)
        await db.commit()
        voted = False
        message = "Vote removed successfully"
    else:
        db.add(Vote(user_id=current_user.id, problem_id=problem_id))
        await db.commit()
        voted = True
        message = "Vote added successfully"

    count_result = await db.execute(
        select(func.count(Vote.id)).where(Vote.problem_id == problem_id)
    )

    return VoteResponse(
        message=message,
        vote_count=count_result.scalar() or 0,
        has_voted=voted
    )