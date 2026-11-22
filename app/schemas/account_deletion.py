from pydantic import BaseModel, Field, SecretStr


class AccountDeletionRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=1024)
