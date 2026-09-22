from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from contracts.events import (
    EventBookmarkUpdate,
    EventCreate,
    EventDetail,
    EventPublic,
    EventsPublic,
    EventUpdate,
)
from contracts.users import (
    DevUserCreate,
    LoginRequest,
    Message,
    NewPassword,
    RecoveryEmail,
    Token,
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
Tag = Literal["auth", "users", "events", "dev"]
ServiceName = Literal["user", "event"]


@dataclass(frozen=True, slots=True)
class PublicRoute:
    method: Method
    path: str
    name: str
    tag: Tag
    response: type[BaseModel]
    service: ServiceName
    body: type[BaseModel] | None = None
    caller: bool = False
    dev_only: bool = False
    paged: bool = False


# More specific paths stay ahead of `/{param}` so the mount order matches them.
PUBLIC_ROUTES: tuple[PublicRoute, ...] = (
    PublicRoute(
        "POST",
        "/auth/login",
        "login",
        "auth",
        Token,
        "user",
        body=LoginRequest,
    ),
    PublicRoute(
        "POST",
        "/auth/register",
        "register",
        "auth",
        UserPublic,
        "user",
        body=UserRegister,
    ),
    PublicRoute(
        "POST",
        "/auth/password-recovery",
        "recover_password",
        "auth",
        Message,
        "user",
        body=RecoveryEmail,
    ),
    PublicRoute(
        "POST",
        "/auth/reset-password",
        "reset_password",
        "auth",
        Message,
        "user",
        body=NewPassword,
    ),
    PublicRoute(
        "GET",
        "/users",
        "read_users",
        "users",
        UsersPublic,
        "user",
        caller=True,
        paged=True,
    ),
    PublicRoute(
        "POST",
        "/users",
        "create_user",
        "users",
        UserPublic,
        "user",
        body=UserCreate,
        caller=True,
    ),
    PublicRoute(
        "PATCH",
        "/users/me",
        "update_user_me",
        "users",
        UserPublic,
        "user",
        body=UserUpdateMe,
        caller=True,
    ),
    PublicRoute(
        "PATCH",
        "/users/me/password",
        "update_password_me",
        "users",
        Message,
        "user",
        body=UpdatePassword,
        caller=True,
    ),
    PublicRoute(
        "GET",
        "/users/me",
        "read_user_me",
        "users",
        UserPublic,
        "user",
        caller=True,
    ),
    PublicRoute(
        "DELETE",
        "/users/me",
        "delete_user_me",
        "users",
        Message,
        "user",
        caller=True,
    ),
    PublicRoute(
        "GET",
        "/users/{user_id}",
        "read_user_by_id",
        "users",
        UserPublic,
        "user",
        caller=True,
    ),
    PublicRoute(
        "PATCH",
        "/users/{user_id}",
        "update_user",
        "users",
        UserPublic,
        "user",
        body=UserUpdate,
        caller=True,
    ),
    PublicRoute(
        "DELETE",
        "/users/{user_id}",
        "delete_user",
        "users",
        Message,
        "user",
        caller=True,
    ),
    PublicRoute(
        "GET",
        "/events",
        "read_events",
        "events",
        EventsPublic,
        "event",
        caller=True,
        paged=True,
    ),
    PublicRoute(
        "GET",
        "/events/bookmarked",
        "read_bookmarked_events",
        "events",
        EventsPublic,
        "event",
        caller=True,
        paged=True,
    ),
    PublicRoute(
        "GET",
        "/events/{id}",
        "read_event",
        "events",
        EventDetail,
        "event",
        caller=True,
    ),
    PublicRoute(
        "PUT",
        "/events/{id}/bookmark",
        "set_event_bookmark",
        "events",
        EventPublic,
        "event",
        body=EventBookmarkUpdate,
        caller=True,
    ),
    PublicRoute(
        "POST",
        "/events",
        "create_event",
        "events",
        EventPublic,
        "event",
        body=EventCreate,
        caller=True,
    ),
    PublicRoute(
        "PUT",
        "/events/{id}",
        "update_event",
        "events",
        EventPublic,
        "event",
        body=EventUpdate,
        caller=True,
    ),
    PublicRoute(
        "DELETE",
        "/events/{id}",
        "delete_event",
        "events",
        Message,
        "event",
        caller=True,
    ),
    PublicRoute(
        "POST",
        "/dev/users",
        "create_user",
        "dev",
        UserPublic,
        "user",
        body=DevUserCreate,
        dev_only=True,
    ),
)
