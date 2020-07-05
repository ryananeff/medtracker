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
    admin = User(email=_ADMIN_USER, name="Test User", superadmin=True, active=True)
    admin.hash_password(_ADMIN_PASS)

    db.session.add(admin)
    db.session.commit()

    with medtracker.app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_fp)


def login_as_admin(client):
    return client.post(
        "/login",
        data={"username": _ADMIN_USER, "password": _ADMIN_PASS},
        follow_redirects=True,
    )


def test_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"COVID-19" in response.data


def test_login(client):
    response = login_as_admin(client)
    assert response.status_code == 200
    assert f"{_ADMIN_USER}".encode("utf-8") in response.data
    assert b"Welcome" in response.data


def test_survey_creation(client):
    login_as_admin(client)
    response = client.post(
        "/surveys/new/",
        data={"title": "test survey", "description": "just for testing"},
        follow_redirects=True,
    )

    assert b"test survey" in response.data
    assert b"just for testing" in response.data
