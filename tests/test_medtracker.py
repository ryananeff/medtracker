import os
import tempfile

import pytest

from medtracker import medtracker

@pytest.fixture
def client():
    db_fd, medtracker.app.config["DATABASE"] = tempfile.mkstemp()
    medtracker.app.config["TESTING"] = True

    with medtracker.app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(medtracker.app.config["DATABASE"])


def test_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"COVID-19" in response.data
