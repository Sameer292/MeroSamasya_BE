from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Category
from app.schemas.schema import CategoryCreate, CategoryUpdate
from fastapi import HTTPException, status

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


async def update_category(category_id: int, data: CategoryUpdate, db: AsyncSession):
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


async def delete_category(category_id: int, db: AsyncSession):
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


async def seed_categories(data: list[CategoryCreate], db: AsyncSession):
    added = []
    skipped = []

    try:
        for cat in data:
            existing = await db.execute(
                select(Category).where(Category.name == cat.name)
            )
            if existing.scalar_one_or_none():
                skipped.append(cat.name)
                continue
            db.add(Category(**cat.model_dump()))
            added.append(cat.name)

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
