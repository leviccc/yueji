"""Behavior tests for progress isolation, retrieval relevance and degradation."""

import copy

import pytest

from yueji_qa.retrieval import retrieve


def chunk(chunk_id, text, *, chapter=1, book="book-1"):
    return {
        "chunk_id": chunk_id,
        "book_id": book,
        "text_version": "v1",
        "chapter_index": chapter,
        "text": text,
        "spans": [{"paragraph_id": f"p-{chunk_id}", "start": 0, "end": len(text)}],
    }


def test_small_corpus_still_retrieves_rare_character_name():
    result = retrieve("林舟拿走了什么？", [chunk("a", "林舟拿走了铜钥匙。")], book_id="book-1", as_of_chapter=1)
    assert [item["chunk_id"] for item in result.chunks] == ["a"]
    assert result.chunks[0]["retrieval_score"] > 0


def test_stopwords_do_not_make_unrelated_passage_relevant():
    result = retrieve(
        "请问火星飞船在哪里？",
        [chunk("a", "他在桥边看着她，她说这个时候已经很晚了。")],
        book_id="book-1", as_of_chapter=1,
    )
    assert result.chunks == []


def test_generic_question_has_no_lexical_evidence():
    result = retrieve("请问这是什么内容？", [chunk("a", "这是关于他和她的故事。")], book_id="book-1", as_of_chapter=1)
    assert result.chunks == []


def test_future_and_other_books_never_reach_embedding_or_cache():
    visible = chunk("a", "林舟在码头找到铜钥匙。")
    future = chunk("b", "林舟其实是失踪王子。", chapter=3)
    other = chunk("c", "林舟进入另一部小说。", book="book-2")

    class SpyEmbedder:
        def embed(self, texts):
            assert texts == ["林舟在哪里？", visible["text"]]
            return [[1.0, 0.0], [1.0, 0.0]]

    class SpyCache:
        def __init__(self):
            self.seen = []

        def get(self, item):
            self.seen.append(item["chunk_id"])
            return None

        def put(self, item, vector):
            self.seen.append(item["chunk_id"])

    cache = SpyCache()
    result = retrieve("林舟在哪里？", [future, visible, other], book_id="book-1", as_of_chapter=1, embedder=SpyEmbedder(), embedding_cache=cache)
    assert cache.seen == ["a", "a"]
    assert [item["chunk_id"] for item in result.chunks] == ["a"]
    assert result.method == "hybrid"


def test_changing_future_chapters_does_not_change_earlier_ranking():
    visible = [chunk("a", "林舟拿起铜钥匙。"), chunk("b", "苏禾提着灯笼来到码头。")]
    initial = retrieve("林舟拿起什么？", visible, book_id="book-1", as_of_chapter=1)
    extended = retrieve("林舟拿起什么？", visible + [chunk("z", "林舟拿起什么？铜钥匙！" * 100, chapter=9)], book_id="book-1", as_of_chapter=1)
    assert initial == extended


def test_progress_rollback_retrieves_only_earlier_source():
    chunks = [chunk("a", "林舟拿走了钥匙。"), chunk("b", "苏禾偷走了玉佩。", chapter=2)]
    later = retrieve("谁偷走了玉佩？", chunks, book_id="book-1", as_of_chapter=2)
    earlier = retrieve("谁偷走了玉佩？", chunks, book_id="book-1", as_of_chapter=1)
    assert [item["chunk_id"] for item in later.chunks] == ["b"]
    assert earlier.chunks == []


def test_embedding_failure_preserves_lexical_results_and_reports_fallback():
    class BrokenEmbedder:
        def embed(self, texts):
            raise TimeoutError("a remote service with possibly private details")

    result = retrieve("铜钥匙在哪里？", [chunk("a", "铜钥匙藏在石桥下面。")], book_id="book-1", as_of_chapter=1, embedder=BrokenEmbedder())
    assert [item["chunk_id"] for item in result.chunks] == ["a"]
    assert result.method == "bm25"
    assert "TimeoutError" in result.warnings[0]
    assert "private" not in result.warnings[0]


@pytest.mark.parametrize("vectors", [[], [[1, 0]], [[1, 0], [1]], [[1, 0], [float("nan"), 0]], [[0, 0], [1, 0]]])
def test_invalid_embedding_response_degrades_safely(vectors):
    class InvalidEmbedder:
        def embed(self, texts):
            return vectors

    result = retrieve("铜钥匙在哪里？", [chunk("a", "铜钥匙藏在石桥下面。")], book_id="book-1", as_of_chapter=1, embedder=InvalidEmbedder())
    assert len(result.chunks) == 1
    assert result.method == "bm25"
    assert result.warnings


def test_dense_channel_can_retrieve_paraphrase_and_exclude_orthogonal_text():
    class ParaphraseEmbedder:
        def embed(self, texts):
            return [[1, 0], [0.99, 0.01], [0, 1]]

    result = retrieve(
        "她藏匿之处是什么？",
        [chunk("a", "苏禾躲进废弃寺庙。"), chunk("b", "铜钥匙沉入河底。")],
        book_id="book-1", as_of_chapter=1, embedder=ParaphraseEmbedder(),
    )
    assert [item["chunk_id"] for item in result.chunks] == ["a"]
    assert result.method == "dense"


def test_cached_vectors_avoid_reembedding_passages():
    class CachedEmbedder:
        def embed(self, texts):
            assert texts == ["铜钥匙在哪里？"]
            return [[1, 0]]

    class Cache:
        def get(self, item):
            return [1, 0]

        def put(self, item, vector):
            pytest.fail("Existing vectors must not be written again")

    result = retrieve("铜钥匙在哪里？", [chunk("a", "铜钥匙在桥下。")], book_id="book-1", as_of_chapter=1, embedder=CachedEmbedder(), embedding_cache=Cache())
    assert len(result.chunks) == 1
    assert result.warnings == []


def test_context_budget_and_result_annotations_preserve_original_chunks():
    chunks = [chunk("a", "铜钥匙在石桥下面。"), chunk("b", "铜钥匙由苏禾保管。")]
    original = copy.deepcopy(chunks)
    result = retrieve("铜钥匙在哪里？", chunks, book_id="book-1", as_of_chapter=1, max_chars=12, top_k=2)
    assert len(result.chunks) == 1
    assert sum(len(item["text"]) for item in result.chunks) <= 12
    assert chunks == original
    assert result.chunks[0]["spans"] == chunks[0]["spans"]


def test_no_read_chapters_does_not_call_embedder():
    class ShouldNotRun:
        def embed(self, texts):
            pytest.fail("No permitted text may be sent to an embedding service")

    result = retrieve("铜钥匙在哪里？", [chunk("a", "铜钥匙在桥下。")], book_id="book-1", as_of_chapter=0, embedder=ShouldNotRun())
    assert result.chunks == []


def test_embedding_batches_for_large_book_are_bounded_and_progress_scoped():
    calls = []

    class BatchedEmbedder:
        def embed(self, texts):
            assert len(texts) <= 32
            assert all("未来秘密" not in text for text in texts)
            calls.append(list(texts))
            return [[1.0, 0.0] for _ in texts]

    chunks = [chunk(f"c{i:04d}", f"铜钥匙第{i}次出现。") for i in range(150)]
    chunks.append(chunk("future", "未来秘密。", chapter=2))
    result = retrieve("铜钥匙在哪里？", chunks, book_id="book-1", as_of_chapter=1, embedder=BatchedEmbedder())
    assert len(calls) == 5 and sum(map(len, calls)) == 151
    assert result.method == "hybrid" and not result.warnings
