from fastapi import FastAPI

from app.database import Base, engine
from app.routes import router

Base.metadata.create_all(engine)

app = FastAPI(title="Umbra AI")
app.include_router(router)
