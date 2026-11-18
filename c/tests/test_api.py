import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from yueji_qa.api import create_app
from yueji_qa.config import Settings
from yueji_qa.ingest import parse_book, paragraphs
from yueji_qa.providers import ProviderError


NOVEL = """第一章 借钥匙
林舟从青禾手中接过铜钥匙，铜钥匙能打开北柜。
青禾说：“我昨天没有去渡口。”林舟暂未证实这句话。
第二章 怀疑
林舟发现青禾的鞋上有渡口的红泥，因此开始怀疑青禾。
林舟仍与青禾合作寻找账册，但并未因此信任青禾。
第三章 揭晓
青禾承认自己的本名是陆澄，暗号叫夜鹤。
"""


def claim(text="林舟拿到了铜钥匙。", ids=None, kind="fact", attribution="narrator"):
    return {"text": text, "kind": kind, "assertion_type": attribution, "evidence_ids": ids or ["E1"]}


class FakeChat:
    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.payloads = []

    def complete_json(self, system, payload):
        self.payloads.append(copy.deepcopy(payload))
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        if "claims" in payload:
            return {"checks": [{"claim_index": i, "verdict": "supported", "answers_question": True,
                                "attribution_correct": True} for i in range(len(payload["claims"]))]}
        return {"status": "answered", "claims": [claim()]}


def client_for(tmp_path, *, llm=False, fake=None, **config):
    settings = Settings(data_dir=tmp_path, mode="llm" if llm else "extractive",
                        llm_base_url="https://example.invalid/v1" if llm else "",
                        llm_api_key="test" if llm else "", llm_model="test-model" if llm else "", **config)
    return TestClient(create_app(settings, chat=fake))


def upload(client, text=NOVEL):
    r = client.post("/api/books", json={"title": "测试小说", "text": text})
    assert r.status_code == 201, r.text
    return r.json()


def ask(client, book, cutoff=1, question="林舟拿到了什么？", mode="Q1"):
    return client.post(f"/api/books/{book['book_id']}/qa", json={"question": question, "as_of_chapter": cutoff, "experiment": mode})


def knowledge(book, *, chapter=1, version="v1", text="林舟得到铜钥匙。", pid="ch0001-p0001"):
    return {"text_version": book["text_version"], "records": [{
        "record_id": "profile", "source": "B", "kind": "character", "text": text,
        "known_from_chapter": chapter, "assertion_type": "narrator", "version": version,
        "evidence_refs": [{"paragraph_id": pid, "start": 0}],
    }]}


def test_offline_retrieval_and_original_coordinates(tmp_path):
    client = client_for(tmp_path)
    book = upload(client)
    assert "chapters" not in book
    answer = ask(client, book).json()
    assert answer["mode"] == "extractive" and answer["status"] == "partial"
    assert answer["claims"] == []
    assert answer["evidence"]
    for e in answer["evidence"]:
        p = client.get(e["paragraph_url"]).json()
        assert p["text"][e["start"]:e["end"]] == e["quote"]
        assert e["chapter_index"] <= 1
    assert "陆澄" not in json.dumps(answer, ensure_ascii=False)


def test_progress_zero_titles_and_paragraph_guard(tmp_path):
    c = client_for(tmp_path)
    b = upload(c)
    assert ask(c, b, 0).json()["evidence"] == []
    result = c.get(f"/api/books/{b['book_id']}/chapters", params={"as_of_chapter": 1}).json()
    assert len(result["chapters"]) == 1
    assert "揭晓" not in json.dumps(result, ensure_ascii=False)
    assert c.get(f"/api/books/{b['book_id']}/paragraphs/ch0003-p0001", params={"as_of_chapter": 1}).status_code == 404
    assert ask(c, b, 4).status_code == 422


@pytest.mark.parametrize("body", [
    {"question": "问题", "as_of_chapter": -1},
    {"question": "问题", "as_of_chapter": "1"},
    {"question": "问题", "as_of_chapter": True},
    {"question": "  ", "as_of_chapter": 1},
    {"question": "问题", "as_of_chapter": 1, "history": ["陆澄"]},
])
def test_bad_requests_do_not_enter_model(tmp_path, body):
    c = client_for(tmp_path)
    b = upload(c)
    assert c.post(f"/api/books/{b['book_id']}/qa", json=body).status_code == 422


def test_txt_upload_encodings_and_limits(tmp_path):
    c = client_for(tmp_path)
    for encoding in ("utf-8", "gb18030"):
        r = c.post("/api/books/upload", files={"file": ("test.txt", NOVEL.encode(encoding), "text/plain")}, data={"encoding": encoding})
        assert r.status_code == 201, r.text
    assert c.post("/api/books", json={"title": "空", "text": "未分章内容"}).status_code == 422
    assert c.post("/api/books", json={"title": "过长", "text": "字" * 100001}).status_code == 422
    assert c.post("/api/books/upload", files={"file": ("bad.txt", b"\xff\xff", "text/plain")}).status_code == 422


def test_auth_and_cors(tmp_path):
    c = client_for(tmp_path, app_token="local-secret")
    assert c.get("/health").status_code == 200
    assert c.get("/api/books").status_code == 401
    assert c.get("/api/books", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/api/books", headers={"Authorization": "Bearer local-secret"}).status_code == 200
    r = c.options("/api/books", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200


def test_generation_citations_cache_and_call_quota(tmp_path):
    fake = FakeChat()
    c = client_for(tmp_path, llm=True, fake=fake, daily_chat_call_limit=2)
    b = upload(c)
    first = ask(c, b)
    assert first.status_code == 200, first.text
    answer = first.json()
    assert answer["status"] == "answered" and answer["claims"][0]["verification"] == "model_supported"
    assert ask(c, b).json()["cached"] is True
    assert len(fake.payloads) == 2
    assert ask(c, b, question="青禾拿到了什么？").status_code == 429


def test_invalid_citations_never_display_draft(tmp_path):
    fake = FakeChat([{"status": "answered", "claims": [claim("泄露未来身份陆澄。", ["other-book-E99"])]}])
    c = client_for(tmp_path, llm=True, fake=fake)
    r = ask(c, upload(c))
    assert r.status_code == 200
    assert r.json()["status"] == "insufficient_evidence"
    assert "陆澄" not in r.text and r.json()["claims"] == []
    assert len(fake.payloads) == 1


def test_partial_support_removed_and_remaining_answer_marked_partial(tmp_path):
    fake = FakeChat([
        {"status": "answered", "claims": [claim(), claim("铜钥匙还可以打开皇宫。") ]},
        {"checks": [{"claim_index": 0, "verdict": "supported", "answers_question": True, "attribution_correct": True},
                    {"claim_index": 1, "verdict": "partially_supported", "answers_question": True, "attribution_correct": True}]},
    ])
    c = client_for(tmp_path, llm=True, fake=fake)
    r = ask(c, upload(c)).json()
    assert r["status"] == "partial" and len(r["claims"]) == 1
    assert "皇宫" not in json.dumps(r, ensure_ascii=False)
    assert r["summary"] == r["claims"][0]["text"]


@pytest.mark.parametrize("check", [
    {"claim_index": 0, "verdict": "supported", "answers_question": False, "attribution_correct": True},
    {"claim_index": 0, "verdict": "supported", "answers_question": True, "attribution_correct": False},
    {"claim_index": 0, "verdict": "unsupported", "answers_question": True, "attribution_correct": True},
])
def test_false_premise_or_wrong_attribution_is_rejected(tmp_path, check):
    fake = FakeChat([{"status": "answered", "claims": [claim("青禾昨天确实没去过渡口。", ["E2"])]}, {"checks": [check]}])
    c = client_for(tmp_path, llm=True, fake=fake)
    r = ask(c, upload(c)).json()
    assert r["claims"] == [] and r["status"] == "insufficient_evidence"
    assert r["summary"] == ""


@pytest.mark.parametrize("replies,code", [
    ([ProviderError("provider_timeout")], 504),
    ([{"status": "answered", "claims": [claim()]}, ProviderError("provider_network_error")], 502),
    ([{"status": "answered", "claims": [claim()]}, {"checks": []}], 502),
    ([{"invalid": "answer"}], 502),
])
def test_technical_failures_are_not_no_evidence(tmp_path, replies, code):
    c = client_for(tmp_path, llm=True, fake=FakeChat(replies))
    r = ask(c, upload(c))
    assert r.status_code == code and "error" in r.json()
    assert "insufficient_evidence" not in r.text


def test_knowledge_validation_and_atomic_import(tmp_path):
    c = client_for(tmp_path)
    b = upload(c)
    url = f"/api/books/{b['book_id']}/knowledge"
    bad = knowledge(b)
    bad["text_version"] = "wrong"
    assert c.post(url, json=bad).status_code == 409
    assert c.post(url, json=knowledge(b, pid="ch0003-p0001")).status_code == 422
    assert c.post(url, json=knowledge(b, pid="ch9999-p0001")).status_code == 422
    good = knowledge(b)
    assert c.post(url, json=good).status_code == 200
    assert c.post(url, json=good).status_code == 200
    assert c.post(url, json=knowledge(b, text="改写同版本")).status_code == 409
    mixed = knowledge(b)
    mixed["records"].insert(0, dict(mixed["records"][0], record_id="must-rollback"))
    mixed["records"][1]["text"] = "冲突"
    assert c.post(url, json=mixed).status_code == 409
    assert len(c.app.state.store.visible_knowledge(b["book_id"], 3)) == 1


def test_progress_rollback_filters_knowledge_even_if_citation_is_early(tmp_path):
    fake = FakeChat()
    c = client_for(tmp_path, llm=True, fake=fake)
    b = upload(c)
    url = f"/api/books/{b['book_id']}/knowledge"
    assert c.post(url, json=knowledge(b)).status_code == 200
    # Later interpretation cites an early paragraph: still hidden before ch3.
    assert c.post(url, json=knowledge(b, chapter=3, version="v2", text="林舟知道青禾本名陆澄。" )).status_code == 200
    assert ask(c, b, 3).status_code == 200
    late = fake.payloads[0]
    assert any("陆澄" in k["text"] for k in late["knowledge"])
    assert ask(c, b, 1).status_code == 200
    early = fake.payloads[2]
    assert "陆澄" not in json.dumps(early, ensure_ascii=False)
    assert early["knowledge"][0]["record_key"].endswith(":v1")
    assert "history" not in early


def test_q0_excludes_knowledge_and_q1_cache_invalidates(tmp_path):
    fake = FakeChat()
    c = client_for(tmp_path, llm=True, fake=fake)
    b = upload(c)
    assert ask(c, b).status_code == 200
    c.post(f"/api/books/{b['book_id']}/knowledge", json=knowledge(b))
    answer = ask(c, b)
    assert answer.status_code == 200 and answer.json()["cached"] is False
    assert fake.payloads[2]["knowledge"]
    assert ask(c, b, mode="Q0").status_code == 200
    assert fake.payloads[4]["knowledge"] == []


def test_knowledge_failure_falls_back_without_sticky_cache(tmp_path, monkeypatch):
    c = client_for(tmp_path)
    b = upload(c)
    store = c.app.state.store
    original = store.visible_knowledge
    monkeypatch.setattr(store, "visible_knowledge", lambda *args: (_ for _ in ()).throw(RuntimeError()))
    r = ask(c, b).json()
    assert r["evidence"] and any("A/B" in warning for warning in r["limitations"])
    monkeypatch.setattr(store, "visible_knowledge", original)
    assert ask(c, b).json()["cached"] is False


def test_other_book_and_changed_future_do_not_influence_early_quotes(tmp_path):
    c = client_for(tmp_path)
    b = upload(c)
    other = upload(c, "第一章 别书\n林舟得到星际飞船和秘密地址。")
    altered = upload(c, NOVEL.replace("青禾承认自己的本名是陆澄，暗号叫夜鹤。", "林舟得到未来藏宝地图和天文坐标。"))
    first, second = ask(c, b).json(), ask(c, altered).json()
    assert [e["quote"] for e in first["evidence"]] == [e["quote"] for e in second["evidence"]]
    assert all(e["book_id"] == b["book_id"] for e in first["evidence"])
    assert not second["cached"]


def test_chunk_offsets_cover_long_paragraphs_without_crossing_chapters():
    b = parse_book("长段落", "第一章 测试\n" + "甲乙丙丁戊。" * 250 + "\n尾段。\n第二章 后文\n后文秘密。")
    lookup = paragraphs(b)
    assert len(b["chunks"]) > 2
    for chunk in b["chunks"]:
        assert len(chunk["text"]) <= 600
        for ref in chunk["spans"]:
            p = lookup[ref["paragraph_id"]]
            assert p["chapter_index"] == chunk["chapter_index"]
            assert p["text"][ref["start"]:ref["end"]] in chunk["text"]


def test_persistence_between_app_instances(tmp_path):
    c = client_for(tmp_path)
    b = upload(c)
    ask(c, b)
    new_client = client_for(tmp_path)
    assert new_client.get(f"/api/books/{b['book_id']}").status_code == 200
    assert ask(new_client, b).json()["cached"] is True


def test_quotes_preserve_whitespace_at_chunk_boundaries(tmp_path):
    c = client_for(tmp_path)
    paragraph = "铜钥匙" * 199 + "甲乙 " + " " + "铜钥匙" * 40
    b = upload(c, "第一章 分块\n" + paragraph)
    result = ask(c, b, question="铜钥匙是什么？").json()
    assert any(e["quote"].endswith(" ") for e in result["evidence"])
    for evidence in result["evidence"]:
        assert evidence["quote"] == paragraph[evidence["start"]:evidence["end"]]


def test_many_tiny_paragraphs_cannot_expand_model_context_unbounded(tmp_path):
    fake = FakeChat()
    c = client_for(tmp_path, llm=True, fake=fake)
    b = upload(c, "第一章 短段落\n" + "铜钥匙。\n" * 1000)
    assert ask(c, b, question="铜钥匙在哪里？").status_code == 200
    payload = fake.payloads[0]
    assert len(payload["evidence"]) <= 64
    assert len(json.dumps(payload, ensure_ascii=False)) < 16000
    assert all(set(e) == {"evidence_id", "chapter_index", "quote"} for e in payload["evidence"])


def test_knowledge_keys_with_colons_do_not_collide(tmp_path):
    fake = FakeChat()
    c = client_for(tmp_path, llm=True, fake=fake)
    b = upload(c)
    body = knowledge(b)
    first = body["records"][0]
    first["record_id"], first["version"] = "profile:detail", "v1"
    body["records"].append(dict(first, record_id="profile", version="detail:v1"))
    assert c.post(f"/api/books/{b['book_id']}/knowledge", json=body).status_code == 200
    result = ask(c, b).json()
    assert len(set(result["used_knowledge_ids"])) == 2
