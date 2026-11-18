import pytest
from export_evaluation import build_annotation_bundle
from helpers import link, make_event

from yueji_plot.evaluation import calculate_metrics, evaluate
from yueji_plot.models import Relation


def bundle():
    events = [
        make_event("归来"),
        make_event("见面", 2),
        make_event("旧事", 3),
        make_event("同时", 2),
        make_event("未知", 2),
    ]
    constraints = [
        link("归来", "见面", chapter=2),
        link("旧事", "归来", chapter=3),
        link("见面", "同时", "simultaneous", chapter=2),
    ]
    pairs = [
        {"left_id": "旧事", "right_id": "见面", "cutoff": 3, "relation": "before"},
        {"left_id": "见面", "right_id": "旧事", "cutoff": 3, "relation": "after"},
        {"left_id": "见面", "right_id": "同时", "cutoff": 3, "relation": "simultaneous"},
        {"left_id": "未知", "right_id": "归来", "cutoff": 3, "relation": "unknown"},
    ]
    return {
        "name": "算法验收样例",
        "scenes": [
            {
                "id": "倒叙",
                "events": [event.model_dump(mode="json") for event in events],
                "constraints": [constraint.model_dump(mode="json") for constraint in constraints],
                "gold_pairs": pairs,
            }
        ],
    }


def test_fixed_raw_outputs_can_be_evaluated_without_model_calls():
    result = evaluate(bundle())
    assert result["metrics"]["T2"]["macro_f1"] == 1
    assert result["metrics"]["T2"]["determined_coverage"] == 1
    assert result["metrics"]["T2"]["unknown_false_certain_rate"] == 0
    assert result["metrics"]["T0"]["accuracy"] < result["metrics"]["T2"]["accuracy"]
    assert result["metrics"]["T1"]["determined_coverage"] < 1


def test_gold_labels_do_not_feed_back_into_t2():
    original = bundle()
    baseline = evaluate(original)["predictions"]
    original["scenes"][0]["gold_pairs"][0]["relation"] = "unknown"
    changed = evaluate(original)["predictions"]
    assert [row["predictions"] for row in baseline] == [row["predictions"] for row in changed]


def test_unknown_false_certainty_is_reported_and_not_hidden_by_coverage():
    result = calculate_metrics(
        [Relation.UNKNOWN, Relation.BEFORE], [Relation.BEFORE, Relation.UNKNOWN]
    )
    assert result["unknown_false_certain_rate"] == 1
    assert result["determined_precision"] == 0
    assert result["determined_coverage"] == 0


def test_export_limits_pair_generation_and_rejects_negative_limit(store, book):
    events = [make_event(f"event-{index}").model_dump(mode="json") for index in range(20)]
    with store.connection() as connection:
        connection.execute("UPDATE books SET profile=? WHERE id=?", ("test:plot-v1", book["id"]))
    store.save_artifact(
        book["id"], "test:plot-v1", "extraction", 1, "00000", "events", {"events": events}
    )

    limited = build_annotation_bundle(store, book["id"], 1, 1)
    empty = build_annotation_bundle(store, book["id"], 1, 0)

    assert len(limited["scenes"][0]["events"]) == 20
    assert len(limited["scenes"][0]["gold_pairs"]) == 1
    assert empty["scenes"][0]["gold_pairs"] == []
    with pytest.raises(ValueError, match="不能小于零"):
        build_annotation_bundle(store, book["id"], 1, -1)
