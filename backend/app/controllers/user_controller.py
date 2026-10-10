from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, hash_password
from app.models import User
from app.views.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

def _ensure_unique(db: Session, username: str | None, email: str | None, ignore_id: int | None = None):
    conditions = []
    if username:
        conditions.append(User.username == username)
    if email:
        conditions.append(User.email == email)
    if not conditions:
        return

    query = select(User).where(or_(*conditions))
    if ignore_id is not None:
        query = query.where(User.id != ignore_id)
    if db.scalar(query):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username ou email já cadastrado")

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    _ensure_unique(db, data.username, data.email)
    user = User(username=data.username, email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)):
    return user

@router.patch("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_unique(db, data.username, data.email, ignore_id=user.id)
    if data.username is not None:
        user.username = data.username
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(user)
    db.commit()
