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
