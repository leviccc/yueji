from app import connect, initialize

DEMO_CHAPTERS = [("demo",1,"一"),("demo",2,"二"),("demo",3,"三")]

def main():
    initialize()
    with connect() as db:
        if db.execute("SELECT 1 FROM books WHERE id='demo'").fetchone():
            db.executemany("INSERT OR IGNORE INTO chapters VALUES (?,?,?)", DEMO_CHAPTERS)
            print("示例已存在，未覆盖；已补齐缺失的章节标题。")
            return
        db.execute("INSERT INTO books VALUES (?,?)", ("demo", "雾港来信"))
        db.executemany("INSERT INTO paragraphs VALUES (?,?,?,?)", [("demo","p1",1,"林舟和沈宁决定一起寻找失踪的信。"),("demo","p2",2,"林舟开始怀疑沈宁隐瞒了线索。"),("demo","p3",3,"沈宁说：我就是此前的蒙面人。")])
        db.executemany("INSERT INTO chapters VALUES (?,?,?)", DEMO_CHAPTERS)
        db.executemany("INSERT INTO people VALUES (?,?,?)", [("demo","lin",1),("demo","shen",1)])
        db.executemany("INSERT INTO names(book_id,person_id,name,known_chapter,paragraph_id) VALUES (?,?,?,?,?)", [("demo","lin","林舟",1,"p1"),("demo","shen","沈宁",1,"p1"),("demo","shen","蒙面人",3,"p3")])
        db.executemany("INSERT INTO relations(book_id,source_id,target_id,relation,directed,action,known_chapter,paragraph_id) VALUES (?,?,?,?,?,?,?,?)", [("demo","lin","shen","合作",0,"assert",1,"p1"),("demo","lin","shen","怀疑",1,"assert",2,"p2")])
    print("已创建示例小说。")

if __name__ == "__main__":
    main()
