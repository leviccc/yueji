"""Export raw relation candidates using only names visible at each candidate chapter.

Unresolved names and unmapped relation labels remain explicit so scoring cannot
silently discard model errors. This evaluates extraction conditional on the
supplied, reviewed person graph; it is not an end-to-end NER metric.
"""
import argparse
import json
from pathlib import Path
import app


def export(book_id, progress_chapter, label_map=None, status="all"):
    if progress_chapter < 1:
        raise ValueError("阅读进度必须大于零")
    if status not in ("all","pending","accepted","rejected"):
        raise ValueError("候选状态无效")
    mapping = label_map or {}
    if not isinstance(mapping,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not v for k,v in mapping.items()):
        raise ValueError("标签映射必须是原始标签到目标标签的 JSON 对象")
    with app.connect() as db:
        if not db.execute("SELECT 1 FROM books WHERE id=?",(book_id,)).fetchone():
            raise ValueError("小说不存在")
        rows=db.execute("SELECT id,chapter,payload,status FROM candidates WHERE book_id=? AND kind='relation' AND chapter<=? ORDER BY chapter,rowid",(book_id,progress_chapter)).fetchall()
    predictions=[]
    issues=[]
    snapshots={}
    for row in rows:
        if status != "all" and row["status"] != status:
            continue
        chapter=row["chapter"]
        if chapter not in snapshots:
            snapshots[chapter]=app.graph(book_id,chapter)["nodes"]
        item=json.loads(row["payload"])
        def resolve(name, role):
            matches=[node["id"] for node in snapshots[chapter] if name in [node["name"],*node["aliases"]]]
            if len(matches)==1:
                return matches[0]
            issues.append({"candidate_id":row["id"],"chapter":chapter,"type":"ambiguous_person" if matches else "unresolved_person","value":name})
            return "__unresolved__:"+row["id"]+":"+role
        relation=item["relation"]
        if mapping and relation not in mapping:
            issues.append({"candidate_id":row["id"],"chapter":chapter,"type":"unmapped_relation","value":relation})
        predictions.append({"book_id":book_id,"progress_chapter":chapter,"source":resolve(item["source"],"source"),"target":resolve(item["target"],"target"),"relation":mapping.get(relation,relation),"directed":item["directed"],"action":item["action"]})
    return {"predictions":predictions,"issues":issues,"scope":{"book_id":book_id,"progress_chapter":progress_chapter,"status":status,"name_resolution":"reviewed_graph_at_candidate_chapter"}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book",required=True)
    parser.add_argument("--progress",required=True,type=int)
    parser.add_argument("--output",required=True,help="预测 JSON 数组输出路径")
    parser.add_argument("--issues",required=True,help="未匹配项报告路径")
    parser.add_argument("--labels",help="可选的、预先固定的标签映射 JSON 文件")
    parser.add_argument("--status",choices=["all","pending","accepted","rejected"],default="all")
    args=parser.parse_args()
    labels=json.loads(Path(args.labels).read_text(encoding="utf-8")) if args.labels else {}
    result=export(args.book,args.progress,labels,args.status)
    Path(args.output).write_text(json.dumps(result["predictions"],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(args.issues).write_text(json.dumps({"scope":result["scope"],"issues":result["issues"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"导出 {len(result['predictions'])} 条候选；{len(result['issues'])} 个待核对项")

if __name__=="__main__":
    main()
