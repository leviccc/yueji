from contextlib import contextmanager
from threading import Event, Thread, current_thread

import pytest


def test_rechapter_transaction_serializes_analysis_creation(store, book):
    transaction_started = Event()
    create_started = Event()
    create_finished = Event()
    release_rechapter = Event()
    create_errors = []
    original_connection = store.connection

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, statement, parameters=()):
            cursor = self.connection.execute(statement, parameters)
            if statement == "BEGIN IMMEDIATE" and current_thread().name == "replace-chapters":
                transaction_started.set()
                assert release_rechapter.wait(5)
            return cursor

    @contextmanager
    def interleaved_connection():
        with original_connection() as connection:
            yield ConnectionProxy(connection)

    store.connection = interleaved_connection

    def create_task():
        create_started.set()
        try:
            store.create_task(book["id"], 2, "test:plot-v1")
        except ValueError as error:
            create_errors.append(error)
        finally:
            create_finished.set()

    replace_thread = Thread(
        name="replace-chapters",
        target=lambda: store.replace_chapters(book["id"], book["chapters"]),
    )
    create_thread = Thread(name="create-task", target=create_task)
    replace_thread.start()
    assert transaction_started.wait(5)
    create_thread.start()
    assert create_started.wait(5)
    assert not create_finished.wait(0.1)
    release_rechapter.set()
    replace_thread.join(5)
    create_thread.join(5)

    assert not replace_thread.is_alive()
    assert not create_thread.is_alive()
    assert len(create_errors) == 1
    assert "已读范围" in str(create_errors[0])
    assert store.book_metadata(book["id"])["progress"] == 0
    with pytest.raises(KeyError, match="任务不存在"):
        store.task("no-task-created")
