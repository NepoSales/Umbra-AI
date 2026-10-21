from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, verify_password
from app.models import User

def login(db: Session, identifier: str, password: str) -> str:
    """Autentica por username ou email e devolve o token de acesso."""
    user = db.scalar(select(User).where(or_(User.username == identifier, User.email == identifier)))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Credenciais inválidas")
    return create_access_token(user.id)
