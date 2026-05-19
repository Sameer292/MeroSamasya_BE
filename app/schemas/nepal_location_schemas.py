from pydantic import BaseModel

from app.schemas.enum import LocalLevelType


class ProvinceResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class DistrictResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class LocalLevelResponse(BaseModel):
    id: int
    name: str
    type: LocalLevelType

    class Config:
        from_attributes = True
