import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2/'src'))
from retrieval_eval.common import load_config, digest, canonical, write_json, V2Error
from retrieval_eval.corpus_manifest import load_corpus, index_signature
from retrieval_eval.qrels_io import load_questions, load_qrels
from retrieval_eval.validate_chunks import validate_chunks
from retrieval_eval.scoring import ranked_metrics, fact_coverage, evaluate
from retrieval_eval.preparation import prepare_markdown
from retrieval_eval import backend

spec = importlib.util.spec_from_file_location('v2_runner_test', V2/'scripts/run_pipeline.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.v2 = self.root/'V2'
        for p in ['scripts','configs','data/rag_eval_questions','data/chunked','results/retrieval']:
            (self.v2/p).mkdir(parents=True, exist_ok=True)
        (self.v2/'scripts/prepare_retrieval_qrels.py').write_bytes((V2/'scripts/prepare_retrieval_qrels.py').read_bytes())
        folder = self.root/'data/chunked'
        folder.mkdir(parents=True)
        self.content = 'Обязательное требование: напряжение не более 220 В при заданных условиях.'
        self.chunks = {
            'answer': {'id':'answer','content':self.content,'metadata':{'Clause':'1.2.3','Document':'ПУЭ'}},
            'reference': {'id':'reference','content':'См. пункт 1.2.3 и таблицу 1.2.4.', 'metadata':{'Clause':'9.9.9','Document':'ПУЭ'}}}
        (folder/'test.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in self.chunks.values()),encoding='utf-8')
        question = {'id':1,'query':'Какое ограничение?', 'question_revision':1,'required_clauses':['1.2.3'],
                    'expected_clause':'1.2.3','required_tables':[], 'split':'development',
                    'mandatory_answer_facts':[{'text':self.content}]}
        self.q = [question]
        qpath = self.v2/'data/rag_eval_questions/eval_questions.json'
        qpath.write_text(json.dumps({'questions':self.q},ensure_ascii=False),encoding='utf-8')
        config = json.loads((V2/'configs/pipeline.json').read_text())
        config['search_depth']=5
        config['k_values']=[1,3,5]
        for mode in config['modes'].values():mode['dimension']=2
        (self.v2/'configs/pipeline.json').write_text(json.dumps(config),encoding='utf-8')
        self.c = load_config(self.v2)
        self.actual, loc, self.man = load_corpus(self.c)
        meta=self.actual['answer']['metadata']
        ev = {'chunk_id':'answer','quote':self.content,'start_char':0,'end_char':len(self.content),
              'quote_sha256':hashlib.sha256(self.content.encode()).hexdigest()}
        self.fact = {'gold_fact_index':1,'gold_fact':question['mandatory_answer_facts'][0],
                     'required_for_coverage':True,'requires_asset_ids':[],
                     'evidence_sets':[{'all_of_chunk_ids':['answer'],'evidence_ids':['ev1'],
                                       'text_only_complete':True,'with_linked_assets_complete':True}]}
        t=runner.load_config # Обычная фикстура эталона для тестов, не авторазметка реального корпуса.
        self.gold = {'schema_version':'1.0','artifact_version':'fixture',
            'corpus_version':{'chunk_count':2,'jsonl_file_count':1,'files':self.man['files'],
                              'chunk_set_sha256':self.man['chunk_set_sha256']},
            'question_dataset':{'questions_canonical_sha256':digest(self.q),
                                'source_file_sha256':hashlib.sha256(qpath.read_bytes()).hexdigest()},
            'qrels':{'1':{'answer':2,'reference':0}}, 'clause_qrels':{'1':{'answer':1}},
            'questions':[{'qid':'1','query':question['query'],'question_revision':1,
                          'split':'development','required_clauses':['1.2.3'],
                          'full_answer_scoring_eligible_text_only':True,
                          'full_answer_scoring_eligible_with_linked_assets':True,
                          'fact_judgments':[self.fact], 'issues':[]}],
            'chunks':{cid:{'path':loc[cid]['path'],'line':loc[cid]['line'],
                          'content_sha256':hashlib.sha256(c['content'].encode()).hexdigest(),
                          'metadata_sha256':digest(c['metadata'])} for cid,c in self.actual.items()},
            'evidence':{'ev1':ev},'assets':{}}
        self.gold_path=self.v2/'data/rag_eval_questions/retrieval_qrels.json'
        self.gold_path.write_text(json.dumps(self.gold,ensure_ascii=False),encoding='utf-8')

    def runs(self):
        return [{'qid':'1','query':self.q[0]['query'],'question_revision':1,'delivered_asset_ids':[],
                 'results':[{'chunk_id':'answer','content':self.content,'metadata':self.chunks['answer']['metadata'],
                             'rank':1,'retrieval_score':0.8}]}]

    def snapshot(self):
        return {'schema_version':'v2-search-1','mode':'base','search_depth':5,
                'index_signature':index_signature(self.man,self.c['modes']['base']),
                'manifest':self.man,'questions_sha256':digest(self.q),'runs':self.runs()}

    def test_qrels_compatible(self):
        self.assertEqual(load_qrels(self.c)['artifact_version'],'fixture')

    def test_candidate_rejected(self):
        self.gold['schema_version']='qrels-candidates-1.0'
        self.gold_path.write_text(json.dumps(self.gold))
        with self.assertRaises(ValueError):load_qrels(self.c)

    def test_altered_quote_rejected(self):
        self.gold['evidence']['ev1']['quote']+='X'
        self.gold_path.write_text(json.dumps(self.gold))
        with self.assertRaises(ValueError):load_qrels(self.c)

    def test_wrong_collection_rejected(self):
        p=self.v2/'configs/pipeline.json'; c=json.loads(p.read_text())
        c['modes']['base']['collection']='diplom_multimodal'; p.write_text(json.dumps(c))
        with self.assertRaises(ValueError):load_config(self.v2)

    def test_write_outside_v2_blocked(self):
        with self.assertRaises(ValueError):write_json(self.root/'bad.json',{},self.v2)

    def test_never_overwrite(self):
        path=self.v2/'results/retrieval/a.json';write_json(path,{},self.v2)
        with self.assertRaises(FileExistsError):write_json(path,{},self.v2)

    def test_plan_no_db_or_models_or_outputs(self):
        with patch.object(runner,'V2',self.v2),patch.object(backend,'_client',side_effect=AssertionError('db')), \
             patch.object(backend,'_encoder',side_effect=AssertionError('model')):
            before=set(self.v2.rglob('*'))
            with redirect_stdout(io.StringIO()):code=runner.main(['plan'])
            self.assertEqual(code,0);self.assertEqual(before,set(self.v2.rglob('*')))

    def test_load_requires_flag(self):
        with patch.object(backend,'_client',side_effect=AssertionError('db')):
            with self.assertRaises(ValueError):backend.load(self.c,'base',self.actual,self.man)

    def test_validation_warns_not_semantic_acceptance(self):
        result=validate_chunks(self.c)
        self.assertTrue(result['warnings']);self.assertFalse(result['errors'])
        self.assertTrue(validate_chunks(self.c,strict=True)['errors'])

    def test_snapshot_metadata_tamper(self):
        snap=self.snapshot();snap['runs'][0]['results'][0]['metadata']={'Clause':'8.8.8'}
        with self.assertRaises(ValueError):runner.check_snapshot(self.c,snap,self.actual,self.man,self.q)

    def test_snapshot_wrong_model(self):
        snap=self.snapshot();snap['index_signature']='bad'
        with self.assertRaises(ValueError):runner.check_snapshot(self.c,snap,self.actual,self.man,self.q)

    def test_snapshot_wrong_resources(self):
        snap=self.snapshot();snap['manifest']=dict(self.man,assets_sha256='bad')
        with self.assertRaises(ValueError):runner.check_snapshot(self.c,snap,self.actual,self.man,self.q)

    def test_evaluate_no_db(self):
        snap=self.snapshot();path=self.v2/'results/retrieval/input.json';path.write_text(json.dumps(snap))
        with patch.object(runner,'V2',self.v2),patch.object(backend,'_client',side_effect=AssertionError('db')):
            with redirect_stdout(io.StringIO()):code=runner.main(['evaluate','--input','V2/results/retrieval/input.json'])
        self.assertEqual(code,0)
        metrics=list((self.v2/'results/retrieval').glob('*/metrics.json'))
        self.assertEqual(len(metrics),1)
        self.assertEqual(json.loads(metrics[0].read_text())['summary']['all']['1']['content']['hit']['mean'],1)

    def test_query_number_reference_not_positive(self):
        r=ranked_metrics(['reference'],self.gold['qrels']['1'],1,2)
        self.assertEqual(r['hit'],0)

    def test_duplicates_keep_rank_penalty(self):
        r=ranked_metrics(['x','x','answer'],{'x':0,'answer':2},3,2)
        self.assertAlmostEqual(r['rr'],1/3);self.assertEqual(r['duplicates_at_k'],1)

    def test_unjudged_not_removed(self):
        r=ranked_metrics(['unknown','answer'],{'answer':2},2,2)
        self.assertEqual(r['unjudged_at_k'],1);self.assertAlmostEqual(r['rr'],0.5)

    def test_grade_one_not_content_hit(self):
        self.assertEqual(ranked_metrics(['ctx'],{'ctx':1,'answer':2},1,2)['hit'],0)

    def test_no_positive_is_not_applicable(self):
        r=ranked_metrics(['a'],{},3,2);self.assertIsNone(r['hit']);self.assertIsNone(r['ndcg_reference_set'])

    def test_ndcg_ideal(self):
        self.assertAlmostEqual(ranked_metrics(['a','b'],{'a':2,'b':1},2,2)['ndcg_reference_set'],1)

    def test_multi_chunk_fact_requires_all(self):
        q=copy.deepcopy(self.gold['questions'][0]);q['fact_judgments'][0]['evidence_sets'][0]['all_of_chunk_ids']=['a','b']
        self.assertFalse(fact_coverage(q,['a'],[])['all_text_facts'])
        self.assertTrue(fact_coverage(q,['a','b'],[])['all_text_facts'])

    def test_image_not_counted_if_not_delivered(self):
        q=copy.deepcopy(self.gold['questions'][0]);f=q['fact_judgments'][0]
        f['requires_asset_ids']=['img'];f['evidence_sets'][0]['text_only_complete']=False
        self.assertFalse(fact_coverage(q,['answer'],[])['all_asset_facts'])
        self.assertTrue(fact_coverage(q,['answer'],['img'])['all_asset_facts'])

    def test_fake_delivered_images_rejected(self):
        runs=self.runs();runs[0]['delivered_asset_ids']=['invented']
        with self.assertRaises(ValueError):evaluate(self.gold,runs,[1],self.q)

    def test_missing_question_rejected(self):
        with self.assertRaises(ValueError):evaluate(self.gold,[],[1],self.q)

    def test_prepare_no_cross_reference_owner(self):
        md=self.root/'prepared';md.mkdir()
        (md/'ПУЭ.md').write_text('# 1.2.3. Требование\nТекст. См. пункт 8.8.8.\n# 1.2.4. Другой пункт\nТекст.',encoding='utf-8')
        result=prepare_markdown(self.c,'prepared')
        self.assertFalse(result['ready_for_final_scoring'])
        cs=[]
        for file in (self.v2/'data/chunked').glob('*.jsonl'):cs += [json.loads(x) for x in file.read_text().splitlines()]
        self.assertEqual([c['metadata']['Clause'] for c in cs],['1.2.3','1.2.4'])
        with self.assertRaises(ValueError):prepare_markdown(self.c,'prepared')

    def test_prepare_symlink_outside_v2_blocked(self):
        md=self.root/'prepared';md.mkdir()
        (md/'a.md').write_text('1.2.3. Требование\nТекст.',encoding='utf-8')
        target=self.v2/'data/chunked';target.rmdir()
        external=self.root/'must_not_write';external.mkdir()
        try:target.symlink_to(external,target_is_directory=True)
        except OSError:self.skipTest('ОС не разрешает создание ссылки')
        with self.assertRaises(ValueError):prepare_markdown(self.c,'prepared')
        self.assertEqual(list(external.iterdir()),[])

    def test_evaluate_wrong_mode_rejected(self):
        path=self.v2/'results/retrieval/input.json';path.write_text(json.dumps(self.snapshot()))
        with patch.object(runner,'V2',self.v2),redirect_stdout(io.StringIO()):
            code=runner.main(['evaluate','--mode','e5','--input','V2/results/retrieval/input.json'])
        self.assertEqual(code,2)

    def test_search_preserves_entity_and_rerank(self):
        client=FakeClient(self.actual,self.man,self.c['modes']['rerank'])
        encoder=FakeEncoder()
        class Reranker:
            def predict(self,pairs):return [0.1,0.9]
        runs=backend.search(self.c,'rerank',self.q,self.actual,self.man,client,encoder,Reranker())
        self.assertEqual(runs[0]['results'][0]['chunk_id'],'reference')
        self.assertEqual(runs[0]['results'][0]['metadata']['Clause'],'9.9.9')
        self.assertEqual(runs[0]['delivered_asset_ids'],[])

    def test_load_inserts_without_drop(self):
        client=LoadClient()
        module=types.SimpleNamespace(DataType=types.SimpleNamespace(VARCHAR=1,JSON=2,FLOAT_VECTOR=3))
        with patch.dict(sys.modules,{'pymilvus':module}):
            result=backend.load(self.c,'base',self.actual,self.man,True,client,FakeEncoder())
        self.assertEqual(result['inserted'],2)
        self.assertEqual({e['chunk_id'] for e in client.rows},set(self.actual))
        self.assertEqual(client.rows[0]['metadata'],self.actual[client.rows[0]['chunk_id']]['metadata'])
        self.assertTrue(client.created)

    def test_load_embedding_dimension_fails_before_creation(self):
        class BadEncoder:
            def encode(self,texts,**kwargs):return [[1.0] for _ in texts]
        client=LoadClient()
        with self.assertRaises(ValueError):backend.load(self.c,'base',self.actual,self.man,True,client,BadEncoder())
        self.assertFalse(client.created)

    def test_load_incomplete_insert_is_error(self):
        client=LoadClient();client.partial=True
        module=types.SimpleNamespace(DataType=types.SimpleNamespace(VARCHAR=1,JSON=2,FLOAT_VECTOR=3))
        with patch.dict(sys.modules,{'pymilvus':module}):
            with self.assertRaises(ValueError):backend.load(self.c,'base',self.actual,self.man,True,client,FakeEncoder())
        self.assertTrue(client.created)  # Не делаем скрытый drop даже после ошибки.

    def test_load_long_content_fails_before_connection(self):
        c=copy.deepcopy(self.actual);c['answer']['content']='я'*40000
        with patch.object(backend,'_client',side_effect=AssertionError('db')):
            with self.assertRaises(ValueError):backend.load(self.c,'base',c,self.man,True)

    def test_search_wrong_index_rejected_before_model(self):
        client=FakeClient(self.actual,self.man,self.c['modes']['base']);client.signature='bad'
        with patch.object(backend,'_encoder',side_effect=AssertionError('model')):
            with self.assertRaises(ValueError):backend.search(self.c,'base',self.q,self.actual,self.man,client)

    def test_load_existing_refuses_without_encoder(self):
        client=FakeClient(self.actual,self.man,self.c['modes']['base'])
        with patch.object(backend,'_encoder',side_effect=AssertionError('model')):
            with self.assertRaises(ValueError):backend.load(self.c,'base',self.actual,self.man,True,client)


class FakeEncoder:
    def encode(self,texts,**kwargs):return [[1.0,0.0] for _ in texts]


class FakeClient:
    def __init__(self,chunks,manifest,mode):
        self.chunks=chunks;self.manifest=manifest
        self.signature='v2:'+index_signature(manifest,mode)
    def has_collection(self,**kwargs):return True
    def describe_collection(self,**kwargs):return {'description':self.signature}
    def get_collection_stats(self,**kwargs):return {'row_count':len(self.chunks)}
    def load_collection(self,**kwargs):pass
    def search(self,**kwargs):
        return [[{'distance':1-i*0.1,'entity':{'chunk_id':cid, 'content':c['content'],
                  'metadata':c['metadata'],'corpus_sha':self.manifest['chunk_set_sha256']}}
                 for i,(cid,c) in enumerate(self.chunks.items())]]


class LoadClient:
    def __init__(self):self.created=False;self.rows=[];self.partial=False
    def has_collection(self,**kwargs):return False
    def create_schema(self,**kwargs):return types.SimpleNamespace(add_field=lambda **kw:None)
    def prepare_index_params(self):return types.SimpleNamespace(add_index=lambda **kw:None)
    def create_collection(self,**kwargs):self.created=True
    def insert(self,**kwargs):
        self.rows.extend(kwargs['data'])
        return {'insert_count':0 if self.partial else len(kwargs['data'])}
    def flush(self,**kwargs):pass
    def load_collection(self,**kwargs):pass
    def get_collection_stats(self,**kwargs):return {'row_count':len(self.rows)}


if __name__=='__main__':unittest.main(verbosity=2)
