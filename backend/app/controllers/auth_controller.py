from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models import User
from app.views.auth import Token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
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
