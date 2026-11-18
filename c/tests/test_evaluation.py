import copy
import csv
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from evaluation.runner import (
    EvaluationError, FIXTURES, fixture_path, load_cases, main, measure, ratio,
    inprocess_settings, run_evaluation, summarize, validate_response, write_results,
)
from yueji_qa.api import create_app
from yueji_qa.config import Settings
from yueji_qa.ingest import paragraphs, parse_book


def base_case(**changes):
    return {"id": "test01", "book_file": "test.txt", "question": "钥匙在哪里？", "as_of_chapter": 1,
            "answerable": True, "expected_keywords": ["北柜"], "forbidden_keywords": ["未来秘密"], "type": "fact", **changes}


def sample_response(mode="extractive"):
    return {"book_id": "book", "text_version": "version", "as_of_chapter": 1, "experiment": "Q0",
            "mode": mode, "status": "partial", "claims": [], "cached": False,
            "evidence": [{"evidence_id": "E1", "book_id": "book", "text_version": "version",
                          "paragraph_id": "ch0001-p0001", "chapter_index": 1,
                          "start": 0, "end": 6, "quote": "钥匙在北柜。"}]}


BOOK = {"book_id": "book", "text_version": "version"}
SOURCE = {"ch0001-p0001": {"text": "钥匙在北柜。", "chapter_index": 1}}


def test_fixture_cases_are_twenty_and_cover_progress_pairs():
    cases = load_cases(FIXTURES / "dev_cases.jsonl")
    assert len(cases) == 20
    assert {c["type"] for c in cases} >= {"fact", "reason", "alias", "conflict", "unanswerable"}
    aliases = [c for c in cases if c["type"] == "alias"]
    assert len({c["question"] for c in aliases}) == 1
    assert {c["answerable"] for c in aliases} == {False, True}
    book = parse_book("fixture", (FIXTURES / "灯塔旧账.txt").read_text(encoding="utf-8"))
    assert len(book["chapters"]) == 6
    lookup = paragraphs(book)
    for record in json.loads((FIXTURES / "knowledge.json").read_text(encoding="utf-8"))["records"]:
        assert all(lookup[ref["paragraph_id"]]["chapter_index"] <= record["known_from_chapter"] for ref in record["evidence_refs"])


def test_offline_metrics_do_not_claim_answer_accuracy():
    m = measure(base_case(), sample_response(), BOOK, SOURCE)
    assert m["evidence_all_keywords_proxy"] is True
    assert m["answer_all_keywords_proxy"] is None
    assert m["answerable_no_claims_proxy"] is None
    assert m["invalid_evidence_count"] == 0
    row = {"experiment": "Q0", "response": sample_response(), "metrics": m, "elapsed_ms": 1, "technical_error": None}
    summary = summarize([row], ["Q0"])["Q0"]
    assert summary["answer_all_keywords_proxy"] == {"numerator": 0, "denominator": 0, "rate": None}
    assert summary["evidence_all_keywords_proxy"]["denominator"] == 1


def test_citation_validation_detects_wrong_book_quote_and_future():
    body = sample_response("llm")
    body["claims"] = [{"text": "未来秘密。", "evidence_ids": ["missing"]}]
    body["evidence"][0].update(book_id="other", chapter_index=2, quote="未来秘密。")
    m = measure(base_case(), body, BOOK, SOURCE)
    assert m["future_evidence_count"] == 1
    assert m["invalid_evidence_count"] == 1
    assert m["invalid_claim_reference_count"] == 1
    assert m["forbidden_terms_in_claims"] == ["未来秘密"]
    assert m["forbidden_terms_in_evidence"] == ["未来秘密"]


def test_no_keywords_or_no_responses_is_not_a_perfect_score():
    empty = summarize([], ["Q0"])["Q0"]
    assert empty["responses_with_future_evidence"]["rate"] is None
    assert empty["elapsed_ms_median"] is None
    assert ratio(0, 0)["rate"] is None
    case = base_case(answerable=False, expected_keywords=[], forbidden_keywords=[])
    metrics = measure(case, sample_response(), BOOK, SOURCE)
    assert metrics["evidence_all_keywords_proxy"] is None
    assert metrics["forbidden_lexicon_available"] is False


def test_technical_errors_excluded_from_metric_denominators():
    response = sample_response()
    valid = {"experiment": "Q0", "response": response, "metrics": measure(base_case(), response, BOOK, SOURCE),
             "elapsed_ms": 3, "technical_error": None}
    failure = {"experiment": "Q0", "technical_error": "HTTP 504", "elapsed_ms": 4}
    summary = summarize([valid, failure], ["Q0"])["Q0"]
    assert summary["requested_count"] == 2
    assert summary["valid_response_count"] == 1
    assert summary["technical_error_count"] == 1
    assert summary["evidence_all_keywords_proxy"]["denominator"] == 1


def test_invalid_dataset_and_book_paths_rejected(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(base_case()) + "\n" + json.dumps(base_case()), encoding="utf-8")
    with pytest.raises(EvaluationError):
        load_cases(path)
    with pytest.raises(EvaluationError):
        fixture_path(FIXTURES, "../runner.py")


def test_manual_scores_are_blank_not_invented(tmp_path):
    response = sample_response()
    row = {"case_id": "test01", "experiment": "Q0", "case": base_case(), "response": response,
           "metrics": measure(base_case(), response, BOOK, SOURCE), "elapsed_ms": 1, "technical_error": None}
    write_results(tmp_path, [row], {"experiments": summarize([row], ["Q0"])})
    with (tmp_path / "manual_review.csv").open(encoding="utf-8-sig", newline="") as file:
        rating = next(csv.DictReader(file))
    assert rating["correctness_0_1_2"] == rating["support_0_1_2"] == rating["spoiler_0_1"] == ""
    assert json.loads((tmp_path / "responses.jsonl").read_text(encoding="utf-8"))["response"] == response


def test_real_inprocess_q0_q1_experiment_has_no_future_evidence(tmp_path):
    cases = load_cases(FIXTURES / "dev_cases.jsonl")
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        rows, books = run_evaluation(client, cases, FIXTURES, ["Q0", "Q1"], FIXTURES / "knowledge.json")
    assert len(rows) == 40 and len(books) == 1
    assert all(not r["technical_error"] for r in rows)
    assert all(r["metrics"]["future_evidence_count"] == 0 for r in rows)
    assert all(r["metrics"]["invalid_evidence_count"] == 0 for r in rows)
    assert all(not r["response"]["used_knowledge_ids"] for r in rows if r["experiment"] == "Q0")
    assert any(r["response"]["used_knowledge_ids"] for r in rows if r["experiment"] == "Q1")
    assert all(r["metrics"]["answer_all_keywords_proxy"] is None for r in rows)


def test_cli_offline_ignores_paid_model_env_and_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_MODE", "llm")
    monkeypatch.setenv("LLM_API_KEY", "must-not-be-used")
    monkeypatch.setenv("LLM_BASE_URL", "https://invalid.example/v1")
    monkeypatch.setenv("LLM_MODEL", "must-not-be-used")
    output = tmp_path / "report"
    args = ["--in-process", "--mode", "Q0", "--output", str(output)]
    assert main(args) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["config_before"]["mode"] == "extractive"
    assert summary["config_after"]["today_attempted_calls_utc"] == {}
    assert main(args) == 2


@pytest.mark.parametrize("evidence", [None, "bad", [None], [{"evidence_id": [], "paragraph_id": []}]])
def test_malformed_evidence_is_rejected_or_counted_without_crashing(evidence):
    body = sample_response()
    body["evidence"] = evidence
    if evidence != [{"evidence_id": [], "paragraph_id": []}]:
        assert validate_response(body, base_case(), BOOK, "Q0") is False
    measured = measure(base_case(), body, BOOK, SOURCE)
    assert measured["invalid_evidence_count"] >= 1


def test_unhashable_claim_references_are_counted_without_crashing():
    body = sample_response("llm")
    body["claims"] = [{"text": "原文", "evidence_ids": [[]]}]
    assert measure(base_case(), body, BOOK, SOURCE)["invalid_claim_reference_count"] == 1


@pytest.mark.parametrize("field,value", [("status", []), ("mode", {}), ("as_of_chapter", True), ("evidence", {})])
def test_malformed_response_envelope_does_not_crash(field, value):
    body = sample_response()
    body[field] = value
    assert validate_response(body, base_case(), BOOK, "Q0") is False


def test_inprocess_llm_keeps_persistent_daily_budget(tmp_path, monkeypatch):
    from yueji_qa.storage import Storage
    persistent = tmp_path / "paid-service-data"
    settings = Settings(data_dir=persistent, mode="llm", llm_base_url="https://example.invalid/v1",
                        llm_api_key="not-used", llm_model="not-used", daily_chat_call_limit=1)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    store = Storage(persistent)
    assert store.reserve_calls("chat", 1, 1)
    evaluated = inprocess_settings("llm", tmp_path / "must-not-reset-budget")
    assert evaluated.data_dir == persistent
    assert Storage(evaluated.data_dir).reserve_calls("chat", 1, 1) is False


def test_progress_is_safe_and_rows_are_saved_before_callback(tmp_path):
    cases = load_cases(FIXTURES / "dev_cases.jsonl")[:1]
    output = tmp_path / "checkpoint"
    events = []

    def progress(event):
        saved = [json.loads(line) for line in (output / "responses.partial.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(saved) == event["completed"]
        assert set(event) == {"completed", "total", "case_id", "mode", "status", "technical_error"}
        assert event["technical_error"] is False
        events.append(event)

    with TestClient(create_app(Settings(data_dir=tmp_path / "data"))) as client:
        rows, books = run_evaluation(client, cases, FIXTURES, ["Q0", "Q1"],
                                     progress_callback=progress, checkpoint_dir=output)
    assert len(rows) == len(events) == 2
    assert [event["mode"] for event in events] == ["Q0", "Q1"]
    assert all(event["total"] == 2 for event in events)
    assert json.loads((output / "books.json").read_text(encoding="utf-8")) == books


def test_interrupt_keeps_results_and_never_resumes_automatically(tmp_path):
    cases = load_cases(FIXTURES / "dev_cases.jsonl")[:1]
    output = tmp_path / "checkpoint"

    def interrupt(event):
        raise KeyboardInterrupt

    with TestClient(create_app(Settings(data_dir=tmp_path / "data"))) as client:
        with pytest.raises(KeyboardInterrupt):
            run_evaluation(client, cases, FIXTURES, ["Q0", "Q1"],
                           progress_callback=interrupt, checkpoint_dir=output)
        saved = (output / "responses.partial.jsonl").read_text(encoding="utf-8")
        assert len(saved.splitlines()) == 1
        assert (output / "books.json").exists()
        with pytest.raises(EvaluationError, match="部分评测结果"):
            run_evaluation(client, cases, FIXTURES, ["Q0", "Q1"], checkpoint_dir=output)
        assert (output / "responses.partial.jsonl").read_text(encoding="utf-8") == saved


def test_cli_limit_preserves_complete_config_snapshots(tmp_path, capsys):
    output = tmp_path / "pilot"
    assert main(["--in-process", "--limit", "1", "--output", str(output)]) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((output / "checkpoint.json").read_text(encoding="utf-8"))
    assert summary["case_count"] == checkpoint["case_count"] == 1
    assert checkpoint["status"] == "completed"
    assert checkpoint["config_before"] == summary["config_before"]
    assert checkpoint["config_after"] == summary["config_after"]
    assert checkpoint["book_sha256"] == summary["book_sha256"]
    assert (output / "responses.partial.jsonl").read_bytes() == (output / "responses.jsonl").read_bytes()
    progress = [json.loads(line)["progress"] for line in capsys.readouterr().out.splitlines() if line.startswith('{"progress":')]
    assert len(progress) == 2
    assert progress[-1]["completed"] == progress[-1]["total"] == 2


def test_cli_interrupt_still_captures_final_usage(tmp_path, monkeypatch):
    from evaluation import runner
    original = runner.run_evaluation

    def interrupt_run(*args, **kwargs):
        def interrupt(event):
            raise KeyboardInterrupt
        kwargs["progress_callback"] = interrupt
        return original(*args, **kwargs)

    monkeypatch.setattr(runner, "run_evaluation", interrupt_run)
    output = tmp_path / "interrupted"
    args = ["--in-process", "--limit", "1", "--output", str(output)]
    assert main(args) == 130
    checkpoint = json.loads((output / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "interrupted"
    assert checkpoint["config_after"]["today_attempted_calls_utc"] == {}
    assert len((output / "responses.partial.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert not (output / "summary.json").exists()
    assert main(args) == 2


def test_cli_limit_must_be_positive(tmp_path):
    output = tmp_path / "invalid-pilot"
    assert main(["--in-process", "--limit", "0", "--output", str(output)]) == 2
    assert not output.exists()
