import os
import tempfile

import pytest

from medtracker import medtracker
from medtracker.database import db
from medtracker.forms import UsernamePasswordForm
from medtracker.models import User

_ADMIN_USER = "test@test.com"
_ADMIN_PASS = "test_password"
@pytest.fixture
def client():
    db_fd, db_fp = tempfile.mkstemp()

    # three slashes for absolute path
    db_uri = f"sqlite:///{db_fp}"
    medtracker.app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    medtracker.app.config["TESTING"] = True
    medtracker.app.config["WTF_CSRF_ENABLED"] = False

    db.create_all()
    admin = User(email=_ADMIN_USER, name="Test User", superadmin=True)
    admin.hash_password(_ADMIN_PASS)

    db.session.add(admin)
    db.session.commit()

    with medtracker.app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_fp)


def test_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"COVID-19" in response.data


def test_login(client):
    response = client.post(
        "/login", data={"username": _ADMIN_USER, "password": _ADMIN_PASS}
    )
    assert response.status_code == 200
    assert f"{_ADMIN_USER}".encode("utf-8") in response.data
