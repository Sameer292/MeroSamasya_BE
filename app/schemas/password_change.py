from pydantic import BaseModel, SecretStr


class CitizenPasswordChangeRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr
    confirm_new_password: SecretStr | None = None


class PasswordChangeRequest(CitizenPasswordChangeRequest):
    confirm_new_password: SecretStr
