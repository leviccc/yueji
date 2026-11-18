"""校验关系标注的字段和逐字证据，不判断关系是否被语义支持。"""
import argparse
import hashlib
import json
from pathlib import Path
import app

REQUIRED=("draft_id","book_id","progress_chapter","source","target","relation","directed","action","evidence_paragraph","quote","annotation_origin","review_status")

def validate(document, text):
    preview=app.split_preview(text)
    paragraphs={f"ch{chapter:04d}_p{index:04d}": (chapter,paragraph) for chapter,c in enumerate(preview["chapters"],1) for index,paragraph in enumerate(c["paragraphs"],1)}
    errors=[]
    seen=set()
    items=document.get("items") if isinstance(document,dict) else None
    if not isinstance(items,list) or not items:
        return {"items":0,"errors":[{"error":"items 必须是非空数组"}],"note":"只验证格式和引文位置，未判断标注是否正确或完整"}
    for index,row in enumerate(items,1):
        if not isinstance(row,dict):
            errors.append({"row":index,"error":"标注必须是对象"})
            continue
        missing=[key for key in REQUIRED if key not in row]
        if missing:
            errors.append({"row":index,"error":"缺少字段","fields":missing})
            continue
        strings=("draft_id","book_id","source","target","relation","action","evidence_paragraph","quote","annotation_origin","review_status")
        invalid=[key for key in strings if not isinstance(row[key],str) or not row[key].strip()]
        if invalid:
            errors.append({"row":index,"error":"字段须为非空字符串","fields":invalid})
            continue
        if row["draft_id"] in seen:
            errors.append({"row":index,"error":"标注编号重复"})
        seen.add(row["draft_id"])
        paragraph=paragraphs.get(row["evidence_paragraph"])
        if not paragraph:
            errors.append({"row":index,"error":"证据段落不存在"})
        elif not isinstance(row["quote"],str) or not row["quote"] or row["quote"] not in paragraph[1]:
            errors.append({"row":index,"error":"引文不是段落的非空逐字片段"})
        elif type(row["progress_chapter"]) is not int or row["progress_chapter"] != paragraph[0]:
            errors.append({"row":index,"error":"获知章节与证据章节不一致"})
        if type(row["directed"]) is not bool or row["action"] not in ("assert","end"):
            errors.append({"row":index,"error":"方向或动作字段无效"})
        if row["review_status"] not in ("unreviewed","accepted","rejected","uncertain"):
            errors.append({"row":index,"error":"复核状态无效"})
    return {"items":len(items),"errors":errors,"note":"只验证格式和引文位置，未判断标注是否正确或完整"}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations")
    parser.add_argument("text")
    args=parser.parse_args()
    raw=Path(args.text).read_bytes()
    result=validate(json.loads(Path(args.annotations).read_text(encoding="utf-8")),raw.decode("utf-8"))
    result["text_sha256"]=hashlib.sha256(raw).hexdigest()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result["errors"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
