from pydantic import BaseModel, SecretStr


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr
    confirm_new_password: SecretStr
