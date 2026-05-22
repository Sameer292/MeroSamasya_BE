from enum import Enum


class AccountStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    deleted = "deleted"


class IssueStatusEnum(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class LocalLevelType(Enum):
    MA_NA_PA = "Ma.Na.Pa."
    UPA_MA = "Upa.Ma."
    NA_PA = "Na.Pa."
    GA_PA = "Ga.Pa."
