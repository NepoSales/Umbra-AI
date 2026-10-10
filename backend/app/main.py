from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  registra as tabelas no Base
from app.controllers import auth_controller, game_controller, user_controller
from app.core.database import Base, engine
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NarratorUnavailableError,
    NotFoundError,
    ServiceError,
)

Base.metadata.create_all(engine)

app = FastAPI(title="Umbra AI")
app.include_router(auth_controller.router)
app.include_router(user_controller.router)
app.include_router(game_controller.router)

# Cada erro dos services vira um status HTTP. Erro sem entrada aqui vira 500.
ERROR_STATUS = {
    ConflictError: status.HTTP_409_CONFLICT,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    NarratorUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
}

@app.exception_handler(ServiceError)
def handle_service_error(request: Request, exc: ServiceError):
    code = ERROR_STATUS.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    headers = {"WWW-Authenticate": "Bearer"} if code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(status_code=code, content={"detail": str(exc)}, headers=headers)

# O front (HTML/CSS/JS puro) é servido na raiz. Fica por último pra não esconder as rotas da API.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
