from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models import User, UserPublic

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserPublic)
def read_me(user: CurrentUser) -> User:
    """Returns the signed-in user."""
    return user
