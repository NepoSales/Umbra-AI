from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserOut, UserUpdate
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter()


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


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, tags=["users"])
def register(data: UserCreate, db: Session = Depends(get_db)):
    _ensure_unique(db, data.username, data.email)
    user = User(username=data.username, email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=Token, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # O campo "username" do formulário OAuth2 aceita username ou email
    user = db.scalar(select(User).where(or_(User.username == form.username, User.email == form.username)))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserOut, tags=["users"])
def read_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/users/me", response_model=UserOut, tags=["users"])
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


@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT, tags=["users"])
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(user)
    db.commit()
