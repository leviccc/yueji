import pytest
from helpers import make_event

from yueji_plot.evidence import event_passages, resolve_quotes, resolve_synthesis
from yueji_plot.models import Passage, Quote, Synthesis


def test_quote_positions_use_unicode_codepoints():
    passage = Passage(
        paragraph_id="p1", chapter=1, paragraph_number=1, start=0, text="𠮷先生收到一封信。"
    )
    evidence = resolve_quotes([Quote(paragraph_id="p1", quote="收到一封信")], [passage])[0]
    assert evidence.start == 3
    assert passage.text[evidence.start : evidence.end] == evidence.quote


def test_missing_closing_quote_is_rejected_with_exact_source_feedback():
    text = '小童献茶，忽家人飞报：“严老爷来拜。'
    passage = Passage(paragraph_id="p1", chapter=1, paragraph_number=1, start=0, text=text)
    with pytest.raises(ValueError) as failure:
        resolve_quotes([Quote(paragraph_id="p1", quote=text + '”')], [passage])
    assert repr(text) in str(failure.value)
    assert "不能补全" in str(failure.value)
    result = resolve_quotes([Quote(paragraph_id="p1", quote=text)], [passage])
    assert result[0].quote == text


def test_quote_with_wrong_paragraph_is_rejected_and_reports_available_source():
    text = "张梁张宝败走，曹操率军拦截，二人死战得脱。"
    passages = [
        Passage(paragraph_id="p1", chapter=1, paragraph_number=1, start=0, text="曹操年少时的故事。"),
        Passage(paragraph_id="p2", chapter=1, paragraph_number=2, start=0, text=text),
    ]
    with pytest.raises(ValueError, match="paragraph_id=p2"):
        resolve_quotes([Quote(paragraph_id="p1", quote=text)], passages)


def test_summary_cannot_convert_a_plan_to_fact():
    event = make_event("计划", statement="plan")
    draft = Synthesis(
        items=[
            {
                "text": "他离开了",
                "event_ids": [event.id],
                "statement": "fact",
                "evidence": [
                    {
                        "paragraph_id": event.evidence[0].paragraph_id,
                        "quote": event.evidence[0].quote,
                    }
                ],
            }
        ]
    )
    with pytest.raises(ValueError, match="计划"):
        resolve_synthesis(draft, [event], event_passages([event]))


def test_synthesis_rejects_event_ids_outside_its_scope():
    event = make_event("当前")
    draft = Synthesis(
        items=[
            {
                "text": "未知的事件",
                "event_ids": ["未来"],
                "statement": "fact",
                "evidence": [
                    {
                        "paragraph_id": event.evidence[0].paragraph_id,
                        "quote": event.evidence[0].quote,
                    }
                ],
            }
        ]
    )
    with pytest.raises(ValueError, match="未知事件"):
        resolve_synthesis(draft, [event], event_passages([event]))


def test_a_valid_quote_from_an_unrelated_event_cannot_support_the_summary():
    first = make_event("甲")
    other = make_event("乙")
    draft = Synthesis(
        items=[
            {
                "text": "甲发生了",
                "event_ids": [first.id],
                "statement": "fact",
                "evidence": [
                    {
                        "paragraph_id": other.evidence[0].paragraph_id,
                        "quote": other.evidence[0].quote,
                    }
                ],
            }
        ]
    )
    with pytest.raises(ValueError, match="关联事件"):
        resolve_synthesis(draft, [first, other], event_passages([first, other]))
