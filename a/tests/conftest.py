import pytest

from yueji_plot.ingestion import decode_text, detect_boundaries, parse_chapters
from yueji_plot.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.sqlite3"))


@pytest.fixture
def book(store):
    text = decode_text(
        "第一章 归来\n沈砚收到匿名信，回到长安。\n\n第二章 茶馆\n林晚与沈砚约定一起查信。\n第三章 回忆\n七年前，沈砚曾把旧信交给林晚。".encode()
    )
    imported = store.import_book("测试小说", text, parse_chapters(text, detect_boundaries(text)))
    store.set_progress(imported["id"], 3)
    return store.book(imported["id"])
