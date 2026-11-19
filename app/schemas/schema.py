from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from typing import Annotated, Optional
from datetime import datetime
from .enum import AccountStatusEnum, IssueStatusEnum, UserRole
from .password_policy import validate_password_strength

FullName = Annotated[
    str,
    Field(
        min_length=2,
        max_length=50,
        pattern=r"^[a-zA-Z\s]+$",
        description="Letters and spaces only",
        examples=["Bishal Baniya"],
    ),
]
PhoneNumber = Annotated[
    str,
    Field(
        pattern=r"^[0-9]{10}$",
        description="Number must be 10 digits",
        examples=["9800000000"],
    ),
]


class UserCreate(BaseModel):
    name: FullName
    phone: PhoneNumber
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class LocationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, coerce_numbers_to_str=True)

    id: str
    name: str


class LocationResponse(BaseModel):
    message: str
    data: list[LocationSchema]


class UpdateLocationRequest(BaseModel):
    location_id: str


class UserData(BaseModel):
    id: str
    email: EmailStr
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[LocationSchema] = None
    profile_picture_url: Optional[str] = None
    account_status: AccountStatusEnum
    role: UserRole
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    message: str
    data: UserData


class RegisterData(BaseModel):
    user_id: str


class RegisterResponse(BaseModel):
    message: str
    data: RegisterData


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str


class TokenResponse(BaseModel):
    message: str
    data: TokenData


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    name: Optional[FullName] = None
    phone: Optional[PhoneNumber] = None
    location_id: Optional[str] = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    icon: str = Field(min_length=1)
    color: str = Field(min_length=4, max_length=7)


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    icon: Optional[str] = None
    color: Optional[str] = Field(None, min_length=4, max_length=7)


class CategoryData(BaseModel):
    id: str
    name: str
    icon: str
    color: str

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    message: str
    data: CategoryData


class CategoryListResponse(BaseModel):
    message: str
    data: list[CategoryData]


IssueTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)
]


class IssueCreate(BaseModel):
    category_id: str = Field(min_length=1)
    title: IssueTitle
    description: Optional[str] = Field(None, min_length=5)
    latitude: float
    longitude: float
    address: Optional[str] = Field(None, min_length=1)
    local_level_id: str


class IssueUpdate(BaseModel):
    category_id: Optional[str] = None
    title: IssueTitle | None = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    local_level_id: Optional[str] = None


class IssueMediaResponse(BaseModel):
    id: str
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


class IssueData(BaseModel):
    id: str = Field(description="Stable issue UUID used in URLs and as the displayed reference.")
    citizen_id: Optional[str] = None
    category: Optional[CategoryData] = None
    title: str
    description: Optional[str] = None
    status: IssueStatusEnum
    latitude: float
    longitude: float
    address: Optional[str] = None
    media: list[IssueMediaResponse] = []
    upvote_count: int = 0
    has_upvoted: bool = False
    local_level_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IssueResponse(BaseModel):
    message: str
    data: IssueData


class IssueListData(BaseModel):
    total: int
    issues: list[IssueData]


class LocationListResponse(BaseModel):
    message: str
    data: list[LocationResponse]


class DeleteData(BaseModel):
    id: str


class DeleteResponse(BaseModel):
    message: str
    data: DeleteData


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int


class PaginatedIssueData(BaseModel):
    meta: PaginationMeta
    issues: list[IssueData]


class PaginatedIssueResponse(BaseModel):
    message: str
    data: PaginatedIssueData


class UpvoteData(BaseModel):
    upvoted: bool
    upvote_count: int


class UpvoteResponse(BaseModel):
    message: str
    data: UpvoteData


class NotificationData(BaseModel):
    id: str
    type: str
    title: str
    message: str
    read: bool
    issue_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListData(BaseModel):
    meta: PaginationMeta
    unread_count: int
    notifications: list[NotificationData]


class NotificationListResponse(BaseModel):
    message: str
    data: NotificationListData


class NotificationResponse(BaseModel):
    message: str
    data: NotificationData


class KycDocumentLinks(BaseModel):
    selfie: str
    front: str
    back: str


class KycData(BaseModel):
    id: str
    full_name: str
    citizenship_number: str
    gender: str
    date_of_birth: datetime
    issued_date: datetime
    ward_number: str
    tole: Optional[str] = None
    province_name: str
    district_name: str
    municipality_name: str
    local_level_id: Optional[str] = None
    status: str
    reviewer_note: Optional[str] = None
    documents: KycDocumentLinks
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KycResponse(BaseModel):
    message: str
    data: KycData


class KycListData(BaseModel):
    meta: PaginationMeta
    submissions: list[KycData]


class KycListResponse(BaseModel):
    message: str
    data: KycListData


class KycReviewRequest(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")
    note: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    status: IssueStatusEnum


class AdminOverviewData(BaseModel):
    open: int
    in_progress: int
    resolved: int
    closed: int
    total_issues: int
    total_users: int
    kyc_pending: int


class AdminOverviewResponse(BaseModel):
    message: str
    data: AdminOverviewData
