import copy,json
from pathlib import Path
from fastapi.testclient import TestClient
from evaluation.research import audit_corpus,retrieval_metrics,union_covers,analyze_run,summarize_scores
from evaluation.runner import run_evaluation,load_cases,EvaluationError
from yueji_qa.api import create_app
from yueji_qa.config import Settings
import pytest

class TraceChat:
    def __init__(self):self.calls=[]
    def complete_json(self,system,payload):
        self.calls.append(copy.deepcopy(payload))
        if 'claims' in payload:
            return {'checks':[{'claim_index':i,'verdict':'supported' if i==0 else 'unsupported',
                              'answers_question':True,'attribution_correct':True} for i in range(len(payload['claims']))]}
        es=payload['evidence']
        return {'status':'answered','claims':[
            {'text':'第一项','kind':'fact','assertion_type':'narrator','evidence_ids':[es[0]['evidence_id']]},
            {'text':'不支持项','kind':'fact','assertion_type':'narrator','evidence_ids':[es[-1]['evidence_id']]}]}

def test_verifier_sees_only_each_claim_citations_and_trace_stays_private(tmp_path):
    chat=TraceChat()
    settings=Settings(data_dir=tmp_path,mode='llm',llm_base_url='https://example.test',llm_api_key='fake',llm_model='fake')
    with TestClient(create_app(settings,chat=chat)) as client:
        b=client.post('/api/books',json={'title':'t','text':'第一章\n钥匙在北柜。\n钥匙是一把铜钥匙。'}).json()
        service=client.app.state.service;service.trace_enabled=True
        response=client.post(f"/api/books/{b['book_id']}/qa",json={'question':'钥匙在哪里？','as_of_chapter':1,'experiment':'Q0'}).json()
        assert 'trace' not in response and len(response['claims'])==1
        trace=service.last_trace
        assert len(trace['draft']['claims'])==2 and len(trace['checks'])==2
        verify=chat.calls[1]
        assert 'evidence' not in verify
        for c in verify['claims']:
            assert {e['evidence_id'] for e in c['cited_evidence']}==set(c['evidence_ids'])
        again=client.post(f"/api/books/{b['book_id']}/qa",json={'question':'钥匙在哪里？','as_of_chapter':1,'experiment':'Q0'}).json()
        assert again['cached'] and service.last_trace is None

def test_corpus_frozen_book_split_and_quote_integrity():
    result=audit_corpus()
    assert result['cases']==120 and result['splits']=={'development':30,'test':90}
    assert result['unique_question_groups']==80
    assert all(20000<=b['characters']<=100000 for b in result['books'].values())

def test_retrieval_partial_overlap_is_not_full_support():
    case={'answerable':True,'gold_evidence_sets':[[{'paragraph_id':'p','start':0,'end':20}]]}
    m=retrieval_metrics(case,[{'paragraph_id':'p','start':0,'end':5}])
    assert m['paragraph_overlap_recall']==1 and not m['full_annotated_spans_covered']
    assert union_covers(0,20,[(0,12),(10,20)])
    assert not union_covers(0,20,[(0,5),(6,20)])
    assert retrieval_metrics({'answerable':False},[]) is None

def test_multibook_knowledge_and_progress_rollback(tmp_path):
    root=Path(__file__).resolve().parents[1]/'evaluation/corpus_v1'
    cases=load_cases(root/'all_cases.jsonl')
    selected=[c for c in cases if c['id'] in {'honglou-02-late','honglou-02-early','sanguo-02-late','sanguo-02-early'}]
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        rows,books=run_evaluation(client,selected,root/'books',['Q0','Q1'],root/'knowledge.json')
    assert len(books)==2 and len(rows)==8 and all(not r['technical_error'] for r in rows)
    for row in rows:
        trace=row['trace']
        assert all(e['chapter_index']<=row['case']['as_of_chapter'] for e in trace['candidate_evidence'])
        assert all(e['book_id']==row['book_id'] for e in trace['candidate_evidence'])
        assert all(k['known_from_chapter']<=row['case']['as_of_chapter'] for k in trace['knowledge'])
    assert all(r['response']['claims']==[] for r in rows)

def test_multibook_mapping_must_not_silently_skip_book(tmp_path):
    folder=tmp_path/'books';folder.mkdir()
    for name in ('a.txt','b.txt'):(folder/name).write_text('第一章\n钥匙在北柜。',encoding='utf-8')
    cases=[{'id':n,'book_file':n,'question':'钥匙','as_of_chapter':1,'answerable':True,'type':'fact','expected_keywords':['北柜'],'forbidden_keywords':[]} for n in ('a.txt','b.txt')]
    knowledge=tmp_path/'knowledge.json';knowledge.write_text('{"books":{"a.txt":{"records":[]}}}')
    with TestClient(create_app(Settings(data_dir=tmp_path/'db'))) as client:
        with pytest.raises(EvaluationError,match='覆盖每本'):
            run_evaluation(client,cases,folder,['Q1'],knowledge)



def test_blinded_export_keeps_scores_blank_and_hides_conditions(tmp_path):
    import csv
    evidence={'evidence_id':'E1','paragraph_id':'ch0001-p0001','start':0,'end':6,'quote':'钥匙在北柜。'}
    draft={'status':'answered','claims':[{'text':'钥匙在北柜。','evidence_ids':['E1']}]}
    row={'case_id':'x','experiment':'Q1','book_id':'book','technical_error':None,
         'case':{'book_file':'b.txt','question':'钥匙在哪里？','as_of_chapter':1,'answerable':True},
         'response':{**draft,'evidence':[evidence]},
         'trace':{'draft':draft,'candidate_evidence':[evidence]}}
    (tmp_path/'responses.jsonl').write_text(json.dumps(row,ensure_ascii=False)+'\n',encoding='utf-8')
    result=analyze_run(tmp_path)
    assert result['semantic_accuracy'] is None
    with (tmp_path/'blinded_review.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==2 and 'experiment' not in rows[0] and 'stage' not in rows[0]
    assert all(not r['reviewer'] and not r['correctness_0_1_2'] for r in rows)
    assert summarize_scores(tmp_path,tmp_path/'blinded_review.csv')['per_reviewer']=={}

def test_scoring_rejects_unknown_samples_and_incomplete_review(tmp_path):
    import csv
    (tmp_path/'review_key.json').write_text(json.dumps([{'sample_id':'known','experiment':'Q0','stage':'final'}]))
    path=tmp_path/'scores.csv'
    path.write_text('sample_id,reviewer,correctness_0_1_2,support_0_1_2_or_NA,spoiler_0_1\nunknown,A,2,2,0\n',encoding='utf-8')
    with pytest.raises(ValueError,match='Unknown'):summarize_scores(tmp_path,path)
    path.write_text('sample_id,reviewer,correctness_0_1_2,support_0_1_2_or_NA,spoiler_0_1\nknown,A,,2,0\n',encoding='utf-8')
    with pytest.raises(ValueError,match='valid scores'):summarize_scores(tmp_path,path)

def test_explicit_batch_refuses_existing_output_before_credentials(tmp_path,monkeypatch):
    from scripts import run_deepseek_batch
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps([{'output':str(tmp_path)}]))
    monkeypatch.setattr('sys.argv',['run_deepseek_batch.py','--plan',str(plan)])
    def forbid(*args,**kwargs):raise AssertionError('Must refuse before asking for credentials')
    monkeypatch.setattr(run_deepseek_batch.getpass,'getpass',forbid)
    with pytest.raises(ValueError,match='Output exists'):run_deepseek_batch.main()



def test_multibook_empty_records_mean_no_knowledge(tmp_path):
    folder=tmp_path/'books';folder.mkdir()
    for name in ('a.txt','b.txt'):(folder/name).write_text('第一章\n钥匙在北柜。',encoding='utf-8')
    cases=[{'id':n,'book_file':n,'question':'钥匙在哪里？','as_of_chapter':1,'answerable':True,'type':'fact','expected_keywords':['北柜'],'forbidden_keywords':[]} for n in ('a.txt','b.txt')]
    knowledge=tmp_path/'knowledge.json'
    knowledge.write_text(json.dumps({'books':{n:{'records':[]} for n in ('a.txt','b.txt')}}))
    with TestClient(create_app(Settings(data_dir=tmp_path/'db'))) as client:
        rows,books=run_evaluation(client,cases,folder,['Q0','Q1'],knowledge)
    assert len(rows)==4 and all(not r['technical_error'] for r in rows)
    assert all(not r['response']['used_knowledge_ids'] for r in rows)

