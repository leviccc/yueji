"""关系断言去重。

持久关系（亲属、身份、态度）在同一对人物之间是状态，只保留最早获知的一条；
事件关系（往来、通信、赠予等）每次发生都算独立断言，不去重。
"""

STATE_RELATIONS = {
    "祖孙", "亲子", "继亲", "兄弟", "叔侄", "过继", "其他亲属",
    "相识", "雇佣", "租佃", "顾问",
    "关切", "疏远", "怀疑", "感激",
}
EVENT_RELATIONS = {"往来", "通信", "赠予", "劝慰", "请托", "帮助", "冲突", "其他"}


def identity(record):
    """无向关系对调双方视为同一断言。"""
    if record["directed"]:
        pair = (record["source"], record["target"])
    else:
        pair = tuple(sorted((record["source"], record["target"])))
    return (record["book_id"], pair[0], pair[1], record["relation"], record["directed"], record["action"])


def dedupe(records):
    ordered = sorted(records, key=lambda record: record["progress_chapter"])
    seen_state, seen_exact = set(), set()
    result = []
    for record in ordered:
        exact = identity(record) + (record["progress_chapter"],)
        if exact in seen_exact:
            continue
        seen_exact.add(exact)
        if record["relation"] in STATE_RELATIONS:
            ident = identity(record)
            if ident in seen_state:
                continue
            seen_state.add(ident)
        result.append(record)
    return result
