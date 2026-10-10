def test_register(client):
    res = client.post("/users", json={"username": "aria", "email": "aria@umbra.com", "password": "senha-forte"})
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "aria"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate(client, auth):
    res = client.post("/users", json={"username": "aria", "email": "outro@umbra.com", "password": "senha-forte"})
    assert res.status_code == 409


def test_register_invalid(client):
    res = client.post("/users", json={"username": "a", "email": "nao-e-email", "password": "123"})
    assert res.status_code == 422


def test_login_with_email(client, auth):
    res = client.post("/auth/login", data={"username": "aria@umbra.com", "password": "senha-forte"})
    assert res.status_code == 200


def test_login_wrong_password(client, auth):
    res = client.post("/auth/login", data={"username": "aria", "password": "errada123"})
    assert res.status_code == 401


def test_me(client, auth):
    res = client.get("/users/me", headers=auth)
    assert res.status_code == 200
    assert res.json()["email"] == "aria@umbra.com"


def test_me_without_token(client):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer lixo"}).status_code == 401


def test_update(client, auth):
    res = client.patch("/users/me", headers=auth, json={"username": "aria2", "password": "nova-senha"})
    assert res.status_code == 200
    assert res.json()["username"] == "aria2"
    assert client.post("/auth/login", data={"username": "aria2", "password": "nova-senha"}).status_code == 200


def test_update_conflict(client, auth):
    client.post("/users", json={"username": "kael", "email": "kael@umbra.com", "password": "senha-forte"})
    res = client.patch("/users/me", headers=auth, json={"email": "kael@umbra.com"})
    assert res.status_code == 409


def test_delete(client, auth):
    assert client.delete("/users/me", headers=auth).status_code == 204
    assert client.get("/users/me", headers=auth).status_code == 401
