"""A conservative display projection; raw interaction records stay untouched."""
import re

from . import bootstrap
from relationship_timeline import summarize
from yueji_plot.ingestion import stable_id

# Explicit relationship labels only. Do not infer a lasting relationship from
# asking, ordering, teaching once, fighting once, visiting, giving money, etc.
GROUPS = [
    ("养父子", False, "养父子"),
    ("养父女", False, "养父女"),
    ("养母子", False, "养母子"),
    ("养母女", False, "养母女"),
    ("养亲", False, "养父母|养亲"),
    ("结义兄弟", False, "结义兄弟|结拜兄弟|义兄弟|结拜|结义"),
    ("父子", False, "父子|父子关系|父亲与儿子"),
    ("父女", False, "父女|父女关系|父亲与女儿"),
    ("母子", False, "母子|母子关系|母亲与儿子|母子同行"),
    ("母女", False, "母女|母女关系|母亲与女儿"),
    ("亲子", False, "亲子|父母子女|父亲|母亲|儿子|女儿"),
    ("夫妻", False, "夫妻|夫妇|配偶|丈夫|妻子|夫君|妻妾|妾室"),
    ("兄弟", False, "兄弟|亲兄弟|堂兄弟|从兄弟|兄长|弟弟"),
    ("姐妹", False, "姐妹|姊妹|亲姐妹|姐姐|妹妹"),
    ("祖孙", False, "祖孙|祖父与孙子|祖母与孙子|祖父母与孙辈"),
    ("叔侄", False, "叔侄|叔姪|叔伯与侄辈"),
    ("姻亲", False, "岳丈与女婿|岳父与女婿|岳婿|翁婿|姻亲|婆媳|翁媳"),
    ("亲属", False, "亲戚|亲属|族亲|其他亲属|远亲|继亲"),
    ("师徒", False, "师徒|师生|师事|拜师|收徒|师父|师傅|徒弟|弟子|老师|学生"),
    ("朋友", False, "朋友|好友|挚友|友人|故交|知己|友谊"),
    ("主仆", False, "主仆|主从|庄客|仆从|主人与仆人|主人和仆人"),
    ("雇佣", None, "雇佣|雇主与雇工"),
    ("君臣", False, "君臣|君主与臣子"),
    ("上下级", False, "上下级|上级与下级|上司与下属|隶属|统属"),
    ("同僚", False, "同僚|同事|同袍"),
    ("同门", False, "同门|师兄弟|师姐妹"),
    ("同盟", False, "同盟|盟友|结盟|同党|同伙"),
    ("合作", False, "合作|协作|合作伙伴"),
    ("敌对", None, "敌对|敌对交战|敌人|仇敌|宿敌|敌对关系"),
    ("怨恨", None, "怨恨|仇视|仇恨|敌视|敌意|积怨"),
    ("怀疑", None, "怀疑|疑心|猜疑|不信任|质疑忠诚"),
    ("信任", None, "信任|信赖|深信|倚重"),
    ("赏识", None, "赏识|器重|看重"),
    ("轻视", None, "轻视|轻之|鄙视|藐视"),
    ("爱慕", None, "爱慕|倾慕|暗恋|恋慕"),
    ("恋人", False, "恋人|恋爱"),
    ("关切", None, "关切|关心|爱护|疼爱"),
    ("疏远", None, "疏远|冷落"),
    ("不和", None, "不和"),
    ("决裂", None, "决裂"),
    ("依赖", None, "依赖|依靠|依靠度日"),
]
MATCHERS = [(label, direction, re.compile(r"(?:" + pattern + r")")) for label,direction,pattern in GROUPS]


def classify(label):
    text = re.sub(r"\s+", "", label)
    if re.search(r"疑似|可能|似乎|仿佛|未确定|不明", text):
        return []
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    found = {}
    for part in re.split(r"[/、，,；;兼]", text):
        for canonical, direction, pattern in MATCHERS:
            if pattern.fullmatch(part):
                found[canonical] = direction
                break
    return list(found.items())


def major_relationships(graph, constraints=()):
    raw = {r["id"]:r for r in graph["edges"]}
    normalized, visible_ids = [], set()
    for r in graph["edges"]:
        if r["source_id"] == r["target_id"]:
            continue
        for label, direction in classify(r["relation"]):
            directed = bool(r["directed"]) if direction is None else direction
            source, target = r["source_id"], r["target_id"]
            if not directed:
                source, target = sorted((source,target))
            normalized.append({**r, "source_id":source,"target_id":target,"directed":directed,"relation":label})
            visible_ids.add(r["id"])
    # A precise kinship label supersedes a generic label for the same pair.
    # Keep generic records in the raw graph, not as a second redundant edge.
    kinship = {"养父子","养父女","养母子","养母女","养亲","父子","父女","母子","母女","亲子","夫妻","兄弟","姐妹","祖孙","叔侄","姻亲","亲属"}
    pairs = {}
    for r in normalized:
        pairs.setdefault(tuple(sorted((r["source_id"],r["target_id"]))),set()).add(r["relation"])
    def redundant(r):
        labels = pairs[tuple(sorted((r["source_id"],r["target_id"])))]
        if r["relation"] == "亲属":
            return bool((labels & kinship) - {"亲属"})
        if r["relation"] == "亲子":
            return bool(labels & {"父子","父女","母子","母女","养父子","养父女","养母子","养母女","养亲"})
        return False
    normalized = [r for r in normalized if not redundant(r)]
    visible_ids = {r["id"] for r in normalized}
    output = []
    for group in summarize(normalized, constraints):
        records = [raw[v] for v in group["record_ids"]]
        output.append({**group,
            "id":"major-"+stable_id(group["source_id"],group["target_id"],group["relation"],group["directed"]),
            "known_chapter": min(r["known_chapter"] for r in records),
            "action":"end" if group["status"] == "end_evidence" else "assert",
            "records": records})
    return {"edges":output,"raw_count":len(raw),"major_record_count":len(visible_ids),"secondary_count":len(raw)-len(visible_ids)}
