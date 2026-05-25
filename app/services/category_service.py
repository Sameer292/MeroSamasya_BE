from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Category
from app.schemas.schema import CategoryCreate, CategoryUpdate
from fastapi import HTTPException, status

CATEGORIES = [
    {"name": "Roads & Transport", "icon": "ri-route-fill", "color": "#F59E0B"},
    {"name": "Water & Drainage", "icon": "ri-drop-fill", "color": "#3B82F6"},
    {"name": "Waste & Sanitation", "icon": "ri-delete-bin-fill", "color": "#16A34A"},
    {
        "name": "Electricity & Utilities",
        "icon": "ri-flashlight-fill",
        "color": "#EAB308",
    },
    {
        "name": "Public Safety & Health",
        "icon": "ri-alarm-warning-fill",
        "color": "#DC2626",
    },
    {"name": "Environment & Nature", "icon": "ri-tree-fill", "color": "#10B981"},
    {"name": "Public Infrastructure", "icon": "ri-building-2-fill", "color": "#4B5563"},
    {
        "name": "Civic Services & Feedback",
        "icon": "ri-file-list-3-fill",
        "color": "#6366F1",
    },
    {"name": "Other", "icon": "ri-tools-fill", "color": "#64748B"},
]


async def get_categories(db: AsyncSession):
    try:
        result = await db.execute(select(Category))
        categories = result.scalars().all()
    except Exception as e:
        print(f"SEED ERROR: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch categories.",
        )
    return {
        "message": "Categories fetched successfully",
        "data": categories,
    }


async def create_category(data: CategoryCreate, db: AsyncSession):
    existing = await db.execute(select(Category).where(Category.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category already exists.",
        )

    try:
        category = Category(
            name=data.name,
            icon=data.icon,
            color=data.color,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category.",
        )

    return {
        "message": "Category created successfully",
        "data": category,
    }


async def update_category(category_id: str, data: CategoryUpdate, db: AsyncSession):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    try:
        if data.name is not None:
            category.name = data.name
        if data.icon is not None:
            category.icon = data.icon
        if data.color is not None:
            category.color = data.color

        await db.commit()
        await db.refresh(category)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category.",
        )

    return {
        "message": "Category updated successfully",
        "data": category,
    }


async def delete_category(category_id: str, db: AsyncSession):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    try:
        await db.delete(category)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category.",
        )

    return {
        "message": "Category deleted successfully.",
        "data": {"id": category_id},
    }


async def seed_categories(db: AsyncSession):
    added = []
    skipped = []

    try:
        for cat in CATEGORIES:
            existing = await db.execute(
                select(Category).where(Category.name == cat["name"])
            )
            if existing.scalar_one_or_none():
                skipped.append(cat["name"])
                continue
            db.add(Category(**cat))
            added.append(cat["name"])

        await db.commit()
    except Exception as e:
        print(f"SEED ERROR: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed categories.",
        )

    return {
        "message": "Categories seeded successfully",
        "data": {
            "added": added,
            "skipped": skipped,
        },
    }
