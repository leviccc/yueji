"""Assistant-authored annotations checked against source paragraphs, not human gold."""
import json,hashlib
from pathlib import Path
from yueji_qa.ingest import parse_book,paragraphs
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evaluation/corpus_v1'
# First ten entries per book have an early/late progress pair; last five are answerable only.
# question, answer points, chapter:paragraph references, keywords, category, attribution
ITEMS={
'honglou':[
("林如海在科举中取得过什么名次？","前科探花。","2:5","探花","fact","narrator"),
("据冷子兴介绍，元春因何入宫，担任什么职务？","因贤孝才德被选入宫作女史；这是冷子兴的介绍。","2:15","女史","attribution","character_claim"),
("宝玉给黛玉取了什么字，探春对他所引典故有什么反应？","宝玉取字颦颦；探春怀疑典故是杜撰，不能把宝玉的引书当作已经核实的文献。","3:21","颦颦|杜撰","conflict","character_claim"),
("黛玉带来的雪雁多大，贾母后来又拨给黛玉哪个丫头？","雪雁十岁；贾母又拨给她鹦哥。","3:24","十岁|鹦哥","fact","narrator"),
("据门子叙述，冯渊原计划买下女子后隔多久让她过门？","三日后过门；需保留门子叙述的归属。","4:8","三日","attribution","character_claim"),
("门子所说的薛公子有什么混名？","混名呆霸王。","4:10","呆霸王","alias","character_claim"),
("薛姨妈为何愿意住在梨香院，薛蟠为何原先不愿住贾宅？","薛姨妈希望约束儿子；薛蟠担心姨父管约拘禁、不能自在。","4:15,4:16","儿子|拘禁","multi_hop","narrator"),
("据门子所说，他凭英莲脸上的什么特征帮助辨认她？","眉心从胎里带来的米粒大小胭脂胎记；属于门子的辨认说明。","4:9","眉心|米粒","attribution","character_claim"),
("警幻介绍给宝玉的茶叫什么名字？","警幻称此茶千红一窟。","5:11","千红一窟","attribution","character_claim"),
("警幻介绍给宝玉的酒叫什么名字？","警幻称此酒万艳同杯。","5:12","万艳同杯","attribution","character_claim"),
("甄士隐女儿的乳名是什么，出场时几岁？","乳名英莲，出场时三岁。","1:7","英莲|三岁","fact","narrator"),
("贾雨村穷困时暂住何处，以什么为生？","暂寄葫芦庙，卖字作文为生。","1:11","葫芦庙|卖字","fact","narrator"),
("第四回门子所说的被争买女子，与第一回甄士隐的女儿有什么关系？请联系两处原文。","第一回女儿为英莲；第四回门子指出被争买女子正是甄家英莲，身份映射来自门子说明。","1:7,4:8","英莲|甄","multi_hop","character_claim"),
("袭人原来叫什么，宝玉为什么替她改名？","原名珍珠；姓花，宝玉取花气袭人诗句改名。","3:24","珍珠|花气袭人","reason","narrator"),
("警幻所说的茶和酒的原料有什么不同？","茶以仙花灵叶上的宿露烹煮；酒以百花蕊、万木汁等酿成；均为警幻对幻境饮品的说法。","5:11,5:12","宿露|百花","multi_hop","character_claim")
],
'sanguo':[
("刘备与县吏商议时，县吏怎样解释督邮的来意？","县吏认为无非是要贿赂；这是县吏判断。","2:10","贿赂","attribution","character_claim"),
("张飞鞭打督邮时使用什么，打折了多少？","使用柳条，一连打折十数枝。","2:11","柳条|十数","fact","narrator"),
("为说服吕布来投，董卓交给李肃哪些财物和坐骑？","赤兔马、黄金一千两、明珠数十颗、玉带一条。","3:20","赤兔|一千两|玉带","fact","narrator"),
("吕布杀死丁原后，怎样改变了自己与董卓的关系？","杀死丁原后携首级投董卓，请拜董卓为义父。","3:24,3:25","丁原|义父","multi_hop","narrator"),
("曹操谋刺董卓时，向谁借了什么兵器？","向王允借七星宝刀。","4:16","允|七星","fact","narrator"),
("放走曹操并随他出逃的县令姓名和字是什么？","县令陈宫，字公台。","4:22","陈宫|公台","fact","narrator"),
("曹操在吕伯奢家听见磨刀后如何判断，厨下所见是否支持这个判断？","他怀疑有人要擒杀自己而先杀人，后来发现缚猪待宰，陈宫指出误杀；不能把猜疑当作事实。","4:24","猪|误杀","conflict","narrator"),
("讨伐董卓的诸侯推举谁为盟主，由谁总督粮草？","推举袁绍为盟主，由袁术总督粮草。","5:10,5:11","袁绍|袁术","multi_hop","narrator"),
("孙坚军缺粮的直接原因是什么，原文如何描述后果？","袁术听从劝阻而不发粮，孙坚军缺食自乱。","5:14","袁术|粮","reason","narrator"),
("祖茂为了帮助孙坚脱身，交换了什么，追兵为何追错目标？","换戴孙坚显眼的赤帻，追兵认赤帻追赶，孙坚从小路脱身。","5:15","赤帻|祖茂","reason","narrator"),
("张飞自述以什么营生，并愿意怎样帮助刘备起兵？","自述卖酒屠猪，有庄田资财，愿招募乡勇同举大事。","1:12","卖酒|屠猪","attribution","character_claim"),
("关羽最初打造的刀叫什么，又名什么，重多少？","青龙偃月刀，又名冷艳锯，重八十二斤。","1:15","青龙偃月|冷艳锯|八十二","fact","narrator"),
("桃园结义时三人如何排行，这是否意味着他们同年同月同日出生？","刘备为兄、关羽次之、张飞为弟；誓言不求同年同月同日生，不能据结义推出相同生日。","1:14","刘备|关羽|张飞","conflict","narrator"),
("曹操杀吕伯奢家人和后来杀吕伯奢本人，陈宫认为两者有何不同？","前者被陈宫指出是误杀，后者是知而故杀；应区分两个事件。","4:24,4:25","误|故杀","multi_hop","character_claim"),
("关羽请战华雄时是什么职务，曹操与袁术对此持何不同态度？","关羽是马弓手；袁术轻视身份要赶出，曹操主张让其试战。","5:18","马弓手|曹操|袁术","conflict","narrator")
],
'shuihu':[
("金翠莲怎样说明三千贯债务的来由，她是否实际收到过这笔钱？","她说被郑屠强取，写三千贯文书却虚钱实契，未拿过一文而被追债；保留自述归属。","2:12","三千贯|一文","attribution","character_claim"),
("据金老汉介绍，镇关西本名和营生是什么？","状元桥下卖肉的郑屠，绰号镇关西。","2:13","郑屠|卖肉","alias","character_claim"),
("鲁达在郑屠肉铺先后索要哪三样东西，每样多少？","先十斤精肉，再十斤肥肉，后十斤寸金软骨，均要剁臊子。","2:17,2:19,2:20","精肉|肥|软骨|十斤","multi_hop","narrator"),
("鲁达剃度时获得什么法名？","长老赐法名智深。","3:12","智深","alias","narrator"),
("铁匠最终建议鲁智深的禅杖多重，两件兵器合计索价多少？","最终建议六十二斤水磨禅杖；禅杖与戒刀合计五两银子，区别于最初要求一百斤。","3:24","六十二|五两","conflict","character_claim"),
("刘太公为什么为女儿招夫烦恼，他说女儿多大？","他说十九岁的女儿被山寨大王强定亲，并非情愿，无法争执。","4:6","十九|情愿","attribution","character_claim"),
("据李忠叙述，鲁智深在桃花庄打的二头领是谁，有什么绰号？","二头领周通，绰号小霸王。","4:16","周通|小霸王","alias","character_claim"),
("据李忠说明，他和周通在桃花山的座次怎样形成？","李忠打败周通后被留作寨主，周通让第一把交椅给他。","4:16","李忠|周通|第一","attribution","character_claim"),
("鲁智深初次与崔道成、邱道人交战为什么败退？","腹中无食、赶路劳累，并且敌不过两人生力夹攻。","5:7","无食|两个","reason","narrator"),
("鲁智深再次攻打瓦官寺前获得了什么帮助，为什么气力不同？","史进给干肉烧饼并共同回寺；有同伴壮胆且吃饱恢复气力。","5:10","史进|饱","reason","narrator"),
("史进为什么被叫作九纹龙？","身体刺绣九条龙，乡人称九纹龙史进。","1:24","九条龙","reason","narrator"),
("王进离家时家中配偶与母亲的情况怎样？","无妻子，只有六旬以上老母。","1:13","无妻子|老母","fact","narrator"),
("史进的武艺与王进是什么关系，王进如何评价他先前学的本事？","史进拜王进为师；王进说先前学的是好看却不实用的花棒。","1:24","王进|花棒","attribution","character_claim"),
("金翠莲父女为什么到渭州又陷于困境？","她自述原来投亲，亲戚迁南京，母亲病死，父女流落；随后遭郑屠逼迫。","2:12","南京|母亲","reason","character_claim"),
("史进后来遇到和尚时怎样确认是旧识，之后如何协助他？","听出熟悉声音，互通姓名确认鲁智深；随后给食物并帮攻瓦官寺。","5:9,5:10","声音|史进","multi_hop","narrator")
],
'laocan':[
("据茶房介绍，白妞本名是什么？","茶房说白妞叫王小玉。","2:9","王小玉","alias","character_claim"),
("据旁座观众的话，黑妞与白妞有什么关系，谁教黑妞唱法？","黑妞是白妞妹子，调门由白妞教；保留观众介绍的归属。","2:14","妹子|白妞","attribution","character_claim"),
("老残在明湖居怎样才获得座位，给了多少钱？","给看坐儿的二百个钱，才得到一张短板凳。","2:10","二百|板凳","fact","narrator"),
("老残离开病人家往济南时，收到多少诊金？","收到一千两银子作为医生酬劳。","2:2","一千两","fact","narrator"),
("老残通过哪家汇票庄寄了多少钱回哪里？","通过日升昌汇八百两回江南徐州老家。","3:2","日升昌|八百|徐州","fact","narrator"),
("北柱楼席上的人为何认为路不拾遗未必说明百姓幸福？","席间介绍百姓不敢捡包袱是害怕丢一家性命，并有人质疑酷刑与冤案；不能只看表面治安。","3:14","性命|冤","conflict","character_claim"),
("老残自己怎样解释不追求高官的原因？","自称性情疏放不合时宜，并认为攀高跌重，不想攀高是想跌轻些。","3:17","疏放|跌","attribution","character_claim"),
("老残住的董二房老店掌柜和唯一伙计分别是谁？","掌柜姓董，人称老董；伙计王三。","4:11","老董|王三","fact","narrator"),
("据老董叙述，于朝栋家最初被抢走什么，价值大约多少？","一些衣服首饰，价值几百吊钱；属于老董讲述。","4:13","衣服首饰|几百","attribution","character_claim"),
("据老董转述，衙门原有多少架站笼，为什么不能立刻再装于家父子？","十二架，前三天已站满没有空位；这是转述中的差人说法。","5:4","十二|没有空","attribution","character_claim"),
("老残原来的姓名和号是什么？","姓铁名英，号补残；老残是后来通行别号。","1:2","铁|英|补残","alias","narrator"),
("老残怎样学得治病本事并谋生？","拜摇串铃的道士为师，学几个口诀，之后走江湖治病糊口。","1:3","道士|治病","reason","narrator"),
("老残收到诊金与汇款回家哪件先发生，各自涉及多少银子？","先收到一千两诊金，后汇八百两回家；不能据此断定无其他花费、现金恰剩二百两。","2:2,3:2","一千|八百","multi_hop","narrator"),
("老董说玉大人是清官，是否同时认为他的办案没有伤害百姓？请结合于家父子的遭遇。","不是；老董说手太辣、后来成为强盗兵器，并叙述于家父子被拉去站笼；清廉不等于办案无害。","4:12,5:4","清官|站笼","multi_hop","character_claim"),
("明湖居这场演出中黑妞与白妞谁先唱，原文如何衔接？","黑妞先唱完退下，随后王小玉登场。","2:14,2:15","黑妞|王小玉","multi_hop","narrator")
]}
UNANSWERABLE={
'honglou':["甄士隐父亲的姓名是什么？","宝玉出生的确切年号和年月日是什么？","警幻仙姑的确切年龄是多少？","林黛玉用什么凶器杀死了贾母？","冯渊杀死薛蟠后藏在什么地方？"],
'sanguo':["张飞的母亲叫什么名字？","关羽的青龙偃月刀刀柄精确长多少寸？","给吕布打造玉带的工匠叫什么名字？","刘备亲手杀死结义兄弟关羽时用了哪件兵器？","王允为什么任命董卓为桃园结义的大哥？"],
'shuihu':["王进母亲的姓名是什么？","史进身上每条龙各用了多少针刺成？","给鲁智深打造戒刀的铁匠妻子叫什么？","史进为何杀死师父王进？","金翠莲自愿无偿赠送郑屠三千贯后为何后悔？"],
'laocan':["白妞母亲叫什么名字？","老残所拜道士的确切出生年月日是什么？","董二房老店全部房间精确面积是多少？","黑妞为什么杀死姐姐白妞？","老残偷走日升昌八百两后逃往哪里？"]
}

def refs(spec, lookup):
    out=[]
    for part in spec.split(','):
        c,p=map(int,part.split(':'));pid=f'ch{c:04d}-p{p:04d}'
        text=lookup[pid]['text']
        out.append({'paragraph_id':pid,'start':0,'end':len(text),'quote':text})
    return out

def main():
    manifest=json.loads((OUT/'source_manifest.json').read_text(encoding='utf-8'))
    all_cases=[]; knowledge={'books':{}}; annotations={}
    for info in manifest:
        key=info['key']; book_file=info['book_file']
        book=parse_book(info['title'],(OUT/'books'/book_file).read_text(encoding='utf-8'))
        lookup=paragraphs(book); cases=[]; records=[]
        for i,(q,a,locations,words,kind,attribution) in enumerate(ITEMS[key],1):
            evidence=refs(locations,lookup)
            chapter=max(lookup[e['paragraph_id']]['chapter_index'] for e in evidence)
            keywords=words.split('|')
            # Gold is for evaluation only. It is never passed to the QA provider.
            base={'book_file':book_file,'question':q,'type':kind,'group_id':f'{key}-g{i:02d}',
                  'split':info['split'],'annotation_source':'assistant_source_grounded_pending_human_review',
                  'earliest_answerable_chapter':chapter,'gold_evidence_sets':[evidence],
                  'answer_points':a,'expected_assertion_type':attribution,
                  'scope':'provided_five_chapter_excerpt'}
            late={**base,'id':f'{key}-{i:02d}-late','as_of_chapter':chapter,
                  'answerable':True,'expected_keywords':keywords,'forbidden_keywords':[],
                  'answerability_category':'currently_answerable','forbidden_facts':[]}
            # Show late before early on half the pairs to exercise progress rollback.
            if i<=10:
                assert chapter>=2
                early={**base,'id':f'{key}-{i:02d}-early','as_of_chapter':chapter-1,
                       'answerable':False,'expected_keywords':[],'forbidden_keywords':[],
                       'answerability_category':'future_only','forbidden_facts':[a],
                       'answer_points':'当前已读选段证据不足，应保留未知，不确认后文事实。'}
                cases.extend([late,early] if i%2==0 else [early,late])
            else: cases.append(late)
            # Broad reference material condition, intentionally assistant-curated.
            # Only 8 records per book; no question text or gold labels in payload.
            if i in {1,2,4,6,7,10,11,12}:
                records.append({'record_id':f'{key}-record-{i:02d}',
                    'source':'B' if kind in {'alias','attribution','conflict'} else 'A',
                    'kind':'alias' if kind=='alias' else ('character' if kind in {'attribution','conflict'} else 'event'),
                    'text':a,'known_from_chapter':chapter,'assertion_type':attribution,
                    'version':'assistant-curated-v1',
                    'evidence_refs':[{k:e[k] for k in ('paragraph_id','start','end')} for e in evidence]})
        for i,q in enumerate(UNANSWERABLE[key],1):
            cases.append({'id':f'{key}-unknown-{i:02d}','book_file':book_file,'question':q,
                          'as_of_chapter':5,'answerable':False,'expected_keywords':[],
                          'forbidden_keywords':[],'type':'false_premise' if i>3 else 'unanswerable',
                          'group_id':f'{key}-unknown-{i:02d}','split':info['split'],
                          'annotation_source':'assistant_source_grounded_pending_human_review',
                          'earliest_answerable_chapter':None,'gold_evidence_sets':[],
                          'answer_points':'所提供选段没有支持该具体信息或事件前提的证据，不能编造。',
                          'answerability_category':'absent_or_false_premise','forbidden_facts':[],
                          'scope':'provided_five_chapter_excerpt'})
        assert len(cases)==30 and sum(c['answerable'] for c in cases)==15
        all_cases.extend(cases); knowledge['books'][book_file]={'records':records}
        annotations[key]={'cases':30,'groups':20,'positive':15,'future_only':10,'absent_or_false':5}
    def save(name,rows):
        (OUT/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    save('all_cases.jsonl',all_cases)
    save('development.jsonl',[c for c in all_cases if c['split']=='development'])
    save('heldout.jsonl',[c for c in all_cases if c['split']=='test'])
    (OUT/'knowledge.json').write_text(json.dumps(knowledge,ensure_ascii=False,indent=2),encoding='utf-8')
    freeze={'dataset_id':'gutenberg-excerpts-v1','annotation_status':'assistant_annotated_pending_human_validation',
            'split_unit':'source_novel','total_cases':120,'development_cases':30,'heldout_cases':90,
            'independent_question_groups':80,'knowledge_condition':'assistant_curated_reference_not_automatic_AB',
            'books':annotations,'hashes':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in list((OUT/'books').glob('*.txt'))+[OUT/n for n in ('all_cases.jsonl','development.jsonl','heldout.jsonl','knowledge.json')]}}
    (OUT/'freeze.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in freeze.items() if k!='hashes'},ensure_ascii=False))
if __name__=='__main__':main()

