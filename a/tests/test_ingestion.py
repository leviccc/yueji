import pytest

from yueji_plot.ingestion import chunk_chapter, decode_text, detect_boundaries, parse_chapters
from yueji_plot.models import Boundary


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "gb18030"])
def test_encodings_and_original_offsets(encoding):
    original = "第一章 雨\r\n　　雨落长安。\r\n\r\n第二章 晴\r\n故人重逢。"
    text = decode_text(original.encode(encoding))
    chapters = parse_chapters(text, detect_boundaries(text))
    assert len(chapters) == 2
    for chapter in chapters:
        for paragraph in chapter.paragraphs:
            assert text[paragraph.start : paragraph.end] == paragraph.text
    assert chapters[0].paragraphs[0].text == "雨落长安。"


def test_manual_correction_preserves_paragraph_identity():
    text = "上篇\n雨落长安。\n下篇\n故人重逢。"
    assert not detect_boundaries(text)
    with pytest.raises(ValueError, match="指定"):
        parse_chapters(text, [])
    chapters = parse_chapters(
        text, [Boundary(line=1, title="上篇"), Boundary(line=3, title="下篇")]
    )
    changed = parse_chapters(
        text, [Boundary(line=1, title="第一部分"), Boundary(line=3, title="第二部分")]
    )
    assert chapters[0].paragraphs[0].id == changed[0].paragraphs[0].id


@pytest.mark.parametrize(
    "lengths", [[100_000 - 3], [1995, 10], [160, 1840, 5], [1800, 200, 10], [100] * 100]
)
def test_chunking_retains_every_character_and_stays_within_chapter(lengths):
    text = "第一章\n" + "\n".join("字" * length for length in lengths)
    chapter = parse_chapters(text, detect_boundaries(text))[0]
    chunks = chunk_chapter(chapter)
    assert all(sum(len(passage.text) for passage in chunk.passages) <= 2000 for chunk in chunks)
    for paragraph in chapter.paragraphs:
        covered = set()
        for chunk in chunks:
            assert chunk.chapter == 1
            for passage in chunk.passages:
                if passage.paragraph_id == paragraph.id:
                    covered.update(range(passage.start, passage.start + len(passage.text)))
                    assert (
                        paragraph.text[passage.start : passage.start + len(passage.text)]
                        == passage.text
                    )
        assert len(covered) == len(paragraph.text)


def test_million_character_limit_and_invalid_boundaries():
    with pytest.raises(ValueError, match="100万"):
        decode_text(("第一章\n" + "字" * 1_000_000).encode())
    with pytest.raises(ValueError, match="递增"):
        parse_chapters("第一章\n原文。", [Boundary(line=3, title="不存在")])


def test_section_headings_for_literary_sources():
    text = "一\n正文甲。\n二\n正文乙。\n三\n正文丙。"
    assert len(parse_chapters(text, detect_boundaries(text))) == 3


def test_long_body_referencing_an_earlier_chapter_is_not_a_heading():
    prose = "第四回中既将薛家母子在荣府内寄居等事略已表明，" + "如今且说林黛玉自在荣府以来。" * 25
    text = "第一章 原作第四回\n正文。\n第二章 原作第五回\n" + prose
    chapters = parse_chapters(text, detect_boundaries(text))
    assert len(chapters) == 2
    assert chapters[1].paragraphs[0].text == prose


def test_chunking_exact_size_and_zero_overlap():
    text = "第一章\n" + "甲" * 10 + "\n" + "乙" * 10
    chapter = parse_chapters(text, detect_boundaries(text))[0]

    chunks = chunk_chapter(chapter, target=10, overlap=0)

    assert [sum(len(passage.text) for passage in chunk.passages) for chunk in chunks] == [10, 10]
    assert (
        "".join(passage.text for chunk in chunks for passage in chunk.passages)
        == "甲" * 10 + "乙" * 10
    )
