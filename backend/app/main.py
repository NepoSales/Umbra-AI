from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  registra as tabelas no Base
from app.controllers import auth_controller, user_controller
from app.core.database import Base, engine
from app.core.exceptions import AuthenticationError, ConflictError

Base.metadata.create_all(engine)

app = FastAPI(title="Umbra AI")
app.include_router(auth_controller.router)
app.include_router(user_controller.router)

@app.exception_handler(ConflictError)
def handle_conflict(request: Request, exc: ConflictError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

@app.exception_handler(AuthenticationError)
def handle_authentication(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )
