from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1)


class UserBase(BaseModel):
    email: EmailStr = Field(max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserPublic(UserBase):
    id: UUID
    created_at: datetime | None = None


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int


class Message(BaseModel):
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class NewPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
