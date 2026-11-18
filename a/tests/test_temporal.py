from itertools import permutations

from helpers import link, make_event

from yueji_plot.models import EvidenceType, Relation
from yueji_plot.temporal import build_timeline, compare_events


def test_flashback_and_transitive_support():
    events = [make_event("归来"), make_event("见面", 2), make_event("旧事", 3)]
    constraints = [link("归来", "见面", chapter=2), link("旧事", "归来", chapter=3)]
    timeline = build_timeline(events, constraints, 3)
    assert compare_events(timeline, "旧事", "见面")["relation"] == Relation.BEFORE
    assert len(compare_events(timeline, "旧事", "见面")["supporting_constraint_ids"]) == 2
    assert timeline.layers == [["旧事"], ["归来"], ["见面"]]


def test_unknown_nodes_are_retained_without_a_total_order():
    events = [make_event(name) for name in ("甲", "乙", "丙", "丁")]
    timeline = build_timeline(events, [link("甲", "乙")], 1)
    assert {event.id for event in timeline.events} == {"甲", "乙", "丙", "丁"}
    assert compare_events(timeline, "丙", "乙")["relation"] == Relation.UNKNOWN
    assert set(timeline.unplaced_ids) == {"丙", "丁"}
    assert not timeline.simultaneous_groups


def test_explicit_simultaneity_is_transitive():
    events = [make_event(name) for name in ("甲", "乙", "丙", "丁")]
    constraints = [
        link("甲", "乙", "simultaneous"),
        link("乙", "丙", "simultaneous"),
        link("丙", "丁"),
    ]
    timeline = build_timeline(events, constraints, 1)
    assert compare_events(timeline, "甲", "丙")["relation"] == Relation.SIMULTANEOUS
    assert compare_events(timeline, "甲", "丁")["relation"] == Relation.BEFORE


def test_equal_strength_cycle_is_pending_in_every_input_order():
    events = [make_event(name) for name in ("甲", "乙", "丙")]
    constraints = [link("甲", "乙"), link("乙", "丙"), link("丙", "甲")]
    for order in permutations(constraints):
        timeline = build_timeline(events, list(order), 1)
        assert len(timeline.pending_ids) == 3
        assert not timeline.accepted_ids
        assert compare_events(timeline, "甲", "丙")["relation"] == Relation.UNKNOWN
        assert timeline.conflicts


def test_stronger_evidence_wins_without_model_confidence():
    events = [make_event(name) for name in ("甲", "乙", "丙")]
    constraints = [link("甲", "乙"), link("乙", "丙"), link("丙", "甲", strength="inferred")]
    timeline = build_timeline(events, constraints, 1)
    assert timeline.pending_ids == [constraints[-1].id]
    assert compare_events(timeline, "甲", "丙")["relation"] == Relation.BEFORE


def test_conflict_between_start_equality_and_before():
    events = [make_event("甲"), make_event("乙")]
    constraints = [link("甲", "乙", "simultaneous"), link("甲", "乙")]
    timeline = build_timeline(events, constraints, 1)
    assert len(timeline.pending_ids) == 2
    assert compare_events(timeline, "甲", "乙")["relation"] == Relation.UNKNOWN


def test_weak_equality_does_not_override_explicit_before():
    events = [make_event("甲"), make_event("乙")]
    constraints = [link("甲", "乙", "simultaneous", strength="inferred"), link("甲", "乙")]
    timeline = build_timeline(events, constraints, 1)
    assert timeline.pending_ids == [constraints[0].id]
    assert compare_events(timeline, "甲", "乙")["relation"] == Relation.BEFORE


def test_future_constraints_cannot_rewrite_early_views():
    events = [make_event("甲"), make_event("乙")]
    constraints = [link("甲", "乙", chapter=2)]
    assert (
        compare_events(build_timeline(events, constraints, 1), "甲", "乙")["relation"]
        == Relation.UNKNOWN
    )
    assert (
        compare_events(build_timeline(events, constraints, 2), "甲", "乙")["relation"]
        == Relation.BEFORE
    )


def test_same_day_is_not_automatically_simultaneous():
    events = [make_event("甲"), make_event("乙")]
    for event in events:
        event.time_expression = "同一天"
    assert compare_events(build_timeline(events, [], 1), "甲", "乙")["relation"] == Relation.UNKNOWN


def test_after_direction_and_evidence_priority():
    events = [make_event("甲"), make_event("乙")]
    timeline = build_timeline(events, [link("乙", "甲", "after", EvidenceType.ANCHORED)], 1)
    assert compare_events(timeline, "甲", "乙")["relation"] == Relation.BEFORE


def test_weaker_relation_cannot_resolve_a_tied_stronger_conflict():
    events = [make_event("甲"), make_event("乙")]
    constraints = [
        link("甲", "乙"),
        link("甲", "乙", "simultaneous"),
        link("甲", "乙", "simultaneous", strength="inferred"),
    ]
    timeline = build_timeline(events, constraints, 1)
    assert compare_events(timeline, "甲", "乙")["relation"] == Relation.UNKNOWN
    assert len(timeline.pending_ids) == 3
