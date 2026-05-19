from enum import Enum


class AccountStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    deleted = "deleted"


class LocalLevelType(Enum):
    MA_NA_PA = "Ma.Na.Pa."
    UPA_MA = "Upa.Ma."
    NA_PA = "Na.Pa."
    GA_PA = "Ga.Pa."
