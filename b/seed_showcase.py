"""安装人工构造的动态人物关系演示；不调用模型，不覆盖已有书目。"""
import json
import uuid

import app

BOOK_ID = "showcase_dynamic"


def main():
    fixture = json.loads((app.ROOT / "data" / "synthetic_progress_pair.json").read_text(encoding="utf-8"))
    story = next(book for book in fixture["books"] if book["book_id"] == "synthetic_a")
    app.initialize()
    with app.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM books WHERE id=?", (BOOK_ID,)).fetchone():
            print("演示书目已存在，未修改现有数据。")
            return False
        db.execute("INSERT INTO books VALUES (?,?)", (BOOK_ID, "码头来信（人工构造演示）"))
        for chapter, data in enumerate(story["chapters"], 1):
            db.execute("INSERT INTO chapters VALUES (?,?,?)", (BOOK_ID,chapter,data["title"]))
            for index, paragraph in enumerate(data["paragraphs"],1):
                db.execute("INSERT INTO paragraphs VALUES (?,?,?,?)", (BOOK_ID,f"ch{chapter:04d}_p{index:04d}",chapter,paragraph))
        for person, name, chapter in (("lin","林岚",1),("zhou","周渡",1),("mask","蒙面人",4)):
            paragraph = f"ch{chapter:04d}_p0001"
            db.execute("INSERT INTO people VALUES (?,?,?)", (BOOK_ID,person,chapter))
            db.execute("INSERT INTO names(book_id,person_id,name,known_chapter,paragraph_id) VALUES (?,?,?,?,?)", (BOOK_ID,person,name,chapter,paragraph))
        def relation(source, target, label, directed, action, chapter):
            cur=db.execute("INSERT INTO relations(book_id,source_id,target_id,relation,directed,action,known_chapter,paragraph_id) VALUES (?,?,?,?,?,?,?,?)",(BOOK_ID,source,target,label,directed,action,chapter,f"ch{chapter:04d}_p0001"))
            return cur.lastrowid
        start=relation("lin","zhou","合作",0,"assert",1)
        relation("lin","zhou","怀疑",1,"assert",2)
        relation("zhou","lin","帮助",1,"assert",3)
        end=relation("lin","zhou","合作",0,"end",5)
        relation("lin","zhou","亲属",0,"assert",7)
        relation("zhou","lin","敌对",1,"assert",8)
        db.execute("INSERT INTO relation_order_constraints VALUES (?,?,?,?,?,?,?)",(uuid.uuid4().hex,BOOK_ID,start,end,5,"ch0005_p0001","结束当初与周渡的合作"))
        db.execute("INSERT INTO person_merges VALUES (?,?,?,?,?,?,?)",(uuid.uuid4().hex,BOOK_ID,"mask","zhou",6,"ch0006_p0001","原来是周渡"))
        db.execute("INSERT INTO profile_facts VALUES (?,?,?,?,?,?,?,?,?,?)",(uuid.uuid4().hex,BOOK_ID,"lin","目标","寻找失踪的信","explicit","ch0001_p0001","寻找失踪的信",1,None))
    print("已创建人工构造演示书目：",BOOK_ID)
    return True


if __name__ == "__main__":
    main()
