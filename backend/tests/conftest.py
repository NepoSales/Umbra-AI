import os

os.environ["UMBRA_DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return TestClient(app)


@pytest.fixture
def auth(client):
    """Cadastra um usuário e devolve os headers com o token dele."""
    client.post("/users", json={"username": "aria", "email": "aria@umbra.com", "password": "senha-forte"})
    res = client.post("/auth/login", data={"username": "aria", "password": "senha-forte"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
