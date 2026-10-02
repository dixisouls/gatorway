"""Maps a verified Firebase identity to the local users row that owns saved courses and pathways."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gatorway.db.models import User

from .firebase import Identity


class AccountConflict(Exception):
    """This email already belongs to a different Firebase account."""


def resolve_user(db: Session, identity: Identity) -> User:
    user = db.scalar(select(User).where(User.firebase_uid == identity.uid))
    if user is None:
        existing = db.scalar(select(User).where(User.email == identity.email))
        if existing is not None:
            if existing.firebase_uid is not None:
                # Same email, different Firebase account (the first one was deleted?). Never hand its data to a new sign-in.
                raise AccountConflict(identity.email)
            existing.firebase_uid = identity.uid  # a pre-Firebase account: its owner signs in with the same email
            db.commit()
            return existing
        user = User(email=identity.email, firebase_uid=identity.uid, password_hash=None)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:  # two first requests raced
            db.rollback()
            return db.scalar(select(User).where(User.firebase_uid == identity.uid))
        return user
    if user.email != identity.email:
        user.email = identity.email
        db.commit()
    return user
