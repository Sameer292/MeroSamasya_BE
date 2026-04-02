from enum import Enum

class RoleEnum(str, Enum):
    citizen = "citizen"
    admin = "admin"
    superadmin = "superadmin"

class AccountStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    deleted = "deleted"