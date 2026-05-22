from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    CategoryListResponse,
    CategoryResponse,
    CategoryCreate,
    CategoryUpdate,
    DeleteResponse,
)
from app.services.category_service import (
    get_categories,
    create_category,
    update_category,
    delete_category,
    seed_categories,
)
from app.core.database import get_db

router = APIRouter()


@router.get("/", response_model=CategoryListResponse, status_code=status.HTTP_200_OK)
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await get_categories(db)


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def add_category(data: CategoryCreate, db: AsyncSession = Depends(get_db)):
    return await create_category(data, db)


@router.patch(
    "/{category_id}", response_model=CategoryResponse, status_code=status.HTTP_200_OK
)
async def edit_category(
    category_id: str,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_category(category_id, data, db)


@router.delete(
    "/{category_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK
)
async def remove_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
):
    return await delete_category(category_id, db)


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed(db: AsyncSession = Depends(get_db)):
    return await seed_categories(db)
