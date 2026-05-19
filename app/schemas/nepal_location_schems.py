from pydantic import BaseModel


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
    type: str

    class Config:
        from_attributes = True
