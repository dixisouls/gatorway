from __future__ import annotations

from fastapi import APIRouter, Depends

from gatorway.db.models import User

from ..deps import current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me(user: User = Depends(current_user)):
    """The signed-in student. The first call after sign-up creates their local record; sign-up and sign-in themselves happen in Firebase."""
    return {"id": user.id, "email": user.email}
