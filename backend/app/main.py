from fastapi import FastAPI

from app import models  # noqa: F401  registra as tabelas no Base
from app.controllers import auth_controller, user_controller
from app.core.database import Base, engine

Base.metadata.create_all(engine)

app = FastAPI(title="Umbra AI")
app.include_router(auth_controller.router)
app.include_router(user_controller.router)
