"""把模型关系候选按 taxonomy.md 归一化，导出为 evaluate.py 可读的 predictions JSON。

用法：python normalize.py [输出文件]
"""
import json
import sys

import app
import dialogue
from dedupe import dedupe
from filters import drop_events

BOOK = "guduzhe_dev"

NAME_TO_ID = {
    "我": "wo",
    "魏连殳": "wei_lianzhu",
    "连殳": "wei_lianzhu",
    "祖母": "zumu",
    "连殳的祖母": "zumu",
    "家里的祖母": "zumu",
    "女工": "nvgong",
    "老女工": "nvgong",
    "大良": "daliang",
    "二良": "erliang",
    "三良": "sanliang",
    "堂兄": "tangxiong",
    "堂兄的小儿子": "tangxiong_son",
    "父亲": "fuqin",
    "连殳的父亲": "fuqin",
    "母亲": "muqin",
    "大良们的祖母": "daliang_zumu",
    "大良的祖母": "daliang_zumu",
    "杜师长": "du_shizhang",
    "连殳的从堂兄弟": "congtang_xiongdi",
    "远房侄子": "yuanfang_zhizi",
    "十三大人": "shisan_daren",
}

# 原始标签 -> (归一标签, 方向)；方向为 None 时沿用模型输出。
LABEL_MAP = {
    "相识": ("相识", False),
    "朋友/相识": ("相识", False),
    "抚养": ("祖孙", False),
    "祖孙": ("祖孙", False),
    "继母与继子": ("继亲", False),
    "非生母关系": ("继亲", False),
    "堂兄弟": ("兄弟", False),
    "从堂兄弟": ("兄弟", False),
    "父子": ("亲子", False),
    "远房侄子": ("叔侄", False),
    "欲过继其子": ("过继", True),
    "寄钱": ("赠予", True),
    "分赠器具并借屋居住": ("赠予", True),
    "赠口琴": ("赠予", True),
    "劝慰": ("劝慰", True),
    "访问": ("往来", True),
    "辞别": ("往来", True),
    "关切": ("关切", True),
    "管理并爱护": ("关切", True),
    "逐渐疏远": ("疏远", True),
    "请求忘记": ("疏远", True),
    "忘却": ("疏远", True),
    "逐出": ("冲突", True),
    "托付求职": ("请托", True),
    "承诺设法推荐": ("帮助", True),
    "寄信": ("通信", True),
    "回信意愿": ("其他", True),
    "担任顾问": ("顾问", True),
    "感谢": ("感激", True),
    "租客与房东": ("租佃", True),
    "疑心": ("怀疑", True),
    "指认画像为对方的祖母": ("其他", True),
    "询问存款": ("其他", True),
}


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "predictions_guduzhe.json"
    with app.connect() as db:
        rows = db.execute(
            "SELECT chapter,payload FROM candidates WHERE book_id=? AND kind='relation' ORDER BY chapter,rowid",
            (BOOK,),
        ).fetchall()
        names = [r[0] for r in db.execute("SELECT DISTINCT name FROM names WHERE book_id=?", (BOOK,))]
        speakers = {}
        for chapter in sorted({row["chapter"] for row in rows}):
            paragraphs = [dict(r) for r in db.execute(
                "SELECT id,text FROM paragraphs WHERE book_id=? AND chapter=? ORDER BY id", (BOOK, chapter)
            ).fetchall()]
            speakers.update(dialogue.speaker_map(paragraphs, names))

    predictions = []
    for row in rows:
        item = dialogue.remap(json.loads(row["payload"]), speakers)
        label, directed = LABEL_MAP[item["relation"]]
        predictions.append({
            "book_id": BOOK,
            "progress_chapter": row["chapter"],
            "source": NAME_TO_ID[item["source"]],
            "target": NAME_TO_ID[item["target"]],
            "relation": label,
            "directed": directed,
            "action": "assert",
        })

    predictions = drop_events(dedupe(predictions))
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(predictions, fh, ensure_ascii=False, indent=2)
    print(f"wrote {len(predictions)} predictions to {output}")


if __name__ == "__main__":
    main()
