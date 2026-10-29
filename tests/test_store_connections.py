import sqlite3

import pytest

from app.store import Store


def test_connection_commits_and_closes(tmp_path):
    store = Store(tmp_path)
    with store.connect() as db:
        db.execute('CREATE TABLE connection_test (value INTEGER)')
        db.execute('INSERT INTO connection_test VALUES (1)')
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute('SELECT 1')
    with store.connect() as check:
        assert check.execute('SELECT value FROM connection_test').fetchall() == [(1,)]


def test_connection_rolls_back_and_closes_on_error(tmp_path):
    store = Store(tmp_path)
    with store.connect() as db:
        db.execute('CREATE TABLE connection_test (value INTEGER)')
    with pytest.raises(RuntimeError, match='abort'):
        with store.connect() as db:
            db.execute('INSERT INTO connection_test VALUES (1)')
            raise RuntimeError('abort')
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute('SELECT 1')
    with store.connect() as check:
        assert check.execute('SELECT value FROM connection_test').fetchall() == []
