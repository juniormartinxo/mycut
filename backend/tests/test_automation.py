"""Real ASGI/store/FFmpeg flow; only external CLIs and ElevenLabs HTTP are fixtures."""
import base64
import copy
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import test_studio  # Sets isolated DATA before the application modules are imported.
from mycut import agent_runner, bridge, commands, costs, elevenlabs, integrations, pipeline, store
from mycut.config import DATA
from test_free_short import fake_voice

CATALOG = {'voices': [{'id':'junior123','name':'Junior','category':'cloned'}],
           'models':[{'id':'eleven_multilingual_v2','name':'Multilingual v2'}]}
PARAGRAPHS = [
    'Uma tarefa pode continuar na nuvem enquanto você acompanha o andamento pelo celular e revisa depois.',
    'Cada sessão usa um ambiente próprio para trabalhar no repositório escolhido e preparar as alterações solicitadas.',
    'Antes de publicar as mudanças você confere o resultado e decide se quer abrir uma revisão.',
]
RESEARCH = {'accessible':True, 'summary':'Exemplo de teste, não uma notícia real.', 'limitations':'Fixture',
            'sources':[{'title':'Fonte de teste', 'url':'https://example.com/news'}],
            'facts':[{'claim':'Tarefas na nuvem.', 'source_url':'https://example.com/news', 'evidence':'Exemplo verificado pela fixture.'}]}
SCRIPT = {'title':'Trabalho na nuvem #IA', 'description':'Exemplo para teste.', 'tags':'IA, nuvem', 'narration':PARAGRAPHS}
DIRECTION = {'accent':'#bd4b28', 'scenes':[{'title':t,'layout':'flow','items':['Pauta','Tarefa','Revisão']} for t in ['Trabalho na nuvem','Ambiente próprio','Você revisa']]}
# Concept of a cover made by the director before covers moved to their own chat.
LEGACY_COVER = {'headline':'Trabalho na nuvem','subtitle':'Acompanhe e revise','labels':['Inicie','Acompanhe','Revise']}

class AutomationTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown
    edit = test_studio.StudioTests.edit
    fill = test_studio.StudioTests.fill

    def configure(self):
        integrations.save_section('elevenlabs', {**integrations.DEFAULTS['elevenlabs'], 'api_key':'test-only-secret', 'voice_id':'junior123', 'voice_name':'Junior'})
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {'time':time.time(), 'providers':{'codex':True,'claude':True,'grok':True}})
        self.edit(brief='https://example.com/news')

    def start(self, kind='pipeline'):
        self.configure()
        job = store.enqueue(self.project['id'], 'preview', self.project['revision'], kind, integrations.read())
        store.claim()
        return store.get_job(job['id'], private=True)

    def test_secret_is_local_never_returned_or_snapshotted(self):
        with patch.object(elevenlabs,'catalog',return_value=CATALOG):
            response=self.client.post('/api/integrations/elevenlabs/connect',json={'api_key':'test-only-secret'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertNotIn('test-only-secret',response.text)
            self.assertTrue(response.json()['settings']['elevenlabs']['connected'])
            selected=self.client.put('/api/integrations/elevenlabs',json={'voice_id':'junior123','model_id':'eleven_multilingual_v2'})
            self.assertEqual(selected.status_code,200,selected.text)
            self.assertEqual(selected.json()['elevenlabs']['voice_name'],'Junior')
        path=DATA/'private/integrations.json'
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertNotIn('test-only-secret',self.client.get('/api/integrations').text)
        self.fill()
        response=self.client.post(f'/api/projects/{self.project["id"]}/run',json={'kind':'voice','revision':self.project['revision']})
        self.assertEqual(response.status_code,202,response.text)
        self.assertNotIn('test-only-secret',json.dumps(store.get_job(response.json()['id'],private=True)))
        self.client.post('/api/integrations/elevenlabs/disconnect')
        self.assertFalse(integrations.public()['elevenlabs']['connected'])

    def test_secret_validation_and_failed_connection_do_not_leak_or_replace_key(self):
        integrations.save_section('elevenlabs', {'api_key':'old-key'})
        invalid='private-'*60
        response=self.client.post('/api/integrations/elevenlabs/connect',json={'api_key':invalid})
        self.assertEqual(response.status_code,422)
        self.assertNotIn(invalid,response.text)
        with patch.object(elevenlabs,'catalog',side_effect=ValueError('Chave recusada.')):
            response=self.client.post('/api/integrations/elevenlabs/connect',json={'api_key':'rejected-key'})
        self.assertEqual(response.status_code,422)
        self.assertEqual(integrations.read()['elevenlabs']['api_key'],'old-key')

    def test_offline_creation_does_not_create_fake_production(self):
        (bridge.BRIDGE/'heartbeat.json').unlink(missing_ok=True)
        response=self.client.post('/api/projects',json={'title':'Pauta','brief':'Uma notícia','automation':'plan'})
        self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(len(store.all_projects()),1)
        self.assertEqual(store.jobs(),[])

    def test_cancelled_checkpoint_cannot_overwrite_later_edits(self):
        job=self.start('plan')
        saved=store.checkpoint(job['id'],{'title':'Roteiro do agente'})
        self.assertEqual(saved['revision'],self.project['revision']+1)
        self.assertNotIn('_agents',store.get_project(self.project['id']))
        self.assertEqual(store.job_input(job['id'])['title'],self.project['title'])
        original=self.client.get(f'/api/jobs/{job["id"]}/materials/input.json')
        self.assertEqual(original.status_code,200)
        self.assertEqual(original.json()['title'],self.project['title'])
        self.assertNotIn('test-only-secret',original.text)
        self.assertNotIn('_voice',original.json())
        store.cancel(job['id'])
        store.update_project(self.project['id'],{'title':'Minha revisão'},saved['revision'])
        with self.assertRaises(store.Conflict):
            store.checkpoint(job['id'],{'title':'Saída atrasada'})
        self.assertEqual(store.get_project(self.project['id'])['title'],'Minha revisão')

    def test_rejected_review_never_calls_paid_voice(self):
        job=self.start()
        rejected={'approved':False,'issues':['Afirmação sem evidência.']}
        with patch.object(bridge,'invoke',side_effect=[RESEARCH,SCRIPT,DIRECTION,rejected,SCRIPT,DIRECTION,rejected]), patch.object(elevenlabs,'synthesize') as voice:
            with self.assertRaisesRegex(ValueError,'não aprovou'):
                pipeline.produce(job)
            voice.assert_not_called()
        self.assertEqual(store.get_project(self.project['id'])['revision'],self.project['revision'])
        review=next(s for s in store.get_job(job['id'])['steps'] if s['name']=='reviewer')
        self.assertEqual(review['state'],'failed')

    def test_inaccessible_source_never_invents_script(self):
        job=self.start('plan')
        with patch.object(bridge,'invoke',return_value={**RESEARCH,'accessible':False}) as invoke:
            with self.assertRaisesRegex(ValueError,'não conseguiu verificar'):
                pipeline.produce(job)
        self.assertEqual(invoke.call_count,1)

    def test_project_costs_are_itemized_by_version_step_attempt_and_model(self):
        integrations.save_section('agents', {'research': {'provider': 'grok', 'model': ''},
            'writer': {'provider': 'claude', 'model': 'claude-sonnet-5-5'},
            'director': {'provider': 'codex', 'model': 'gpt-6-astra'}, 'reviewer': {'provider': 'codex', 'model': 'unpriced-model'}})
        job=self.start()
        envelopes={'grok': {'modelUsage': {'grok-4.7-build': {'inputTokens': 1000, 'outputTokens': 200, 'cacheReadInputTokens': 500, 'costUSD': .01}},
                            'usage': {'reasoning_tokens': 150}},
                   'claude': {'modelUsage': {'claude-sonnet-5-5': {'inputTokens': 10, 'outputTokens': 900, 'cacheReadInputTokens': 4000,
                                                                   'cacheCreationInputTokens': 2000, 'webSearchRequests': 1, 'costUSD': .05},
                                             'claude-haiku-5-5': {'inputTokens': 3000, 'outputTokens': 100, 'costUSD': .004}}}}
        outputs=iter([RESEARCH,SCRIPT,DIRECTION,{'approved':True,'issues':[]}])
        def runner(config, prompt, schema, web=False, request_id=None):
            if config['provider']=='codex':
                stdout='{"type":"turn.completed","usage":{"input_tokens":1000000,"cached_input_tokens":400000,"output_tokens":20000,"reasoning_output_tokens":5000}}'
            else:
                stdout=json.dumps(envelopes[config['provider']])
            bridge.atomic_json(bridge.BRIDGE/'requests'/request_id/'response.json',
                               {'result': {}, 'usage': costs.extract(config['provider'], config['model'], stdout)})
            return next(outputs)
        mp3=DATA/'fixture-costs.mp3'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=8','-codec:a','libmp3lame',str(mp3)],check=True)
        text='\n\n'.join(PARAGRAPHS)
        step=7.5/len(text)
        chars={'characters':list(text),'character_start_times_seconds':[i*step for i in range(len(text))],'character_end_times_seconds':[(i+1)*step for i in range(len(text))]}
        def api(key, method, path, meta=None, **kwargs):
            meta['credits']=321.0
            return {'audio_base64':base64.b64encode(mp3.read_bytes()).decode(),'normalized_alignment':chars}
        with patch.object(bridge,'invoke',side_effect=runner), patch.object(elevenlabs,'api',side_effect=api):
            pipeline.produce(job)
        store.finish(job['id'],'succeeded','Pronto')
        # An older version from before the feature has no usage rows.
        old=store.enqueue(self.project['id'],'preview',store.get_project(self.project['id'])['revision'],'plan',integrations.read())
        store.claim(); store.finish(old['id'],'failed','Antiga')
        usage=self.client.get(f'/api/projects/{self.project["id"]}/usage').json()
        version=next(v for v in usage['versions'] if v['id']==job['id'])
        lines={(c['step'],c['model']): c for c in version['calls']}
        self.assertEqual(set(lines),{('research','grok-4.7-build'),('writer','claude-sonnet-5-5'),('writer','claude-haiku-5-5'),
                                     ('director','gpt-6-astra'),('reviewer','unpriced-model'),('voice','eleven_multilingual_v2')})
        self.assertEqual(lines[('research','grok-4.7-build')]['reasoning'],150)
        self.assertEqual(lines[('writer','claude-sonnet-5-5')]['cost_source'],'cli')
        self.assertEqual(lines[('writer','claude-sonnet-5-5')]['web_searches'],1)
        director=lines[('director','gpt-6-astra')]
        self.assertEqual((director['input'],director['cache_read'],director['output']),(600000,400000,20000))
        self.assertAlmostEqual(director['usd'],.6*10+.4*1+.02*50)
        self.assertEqual(director['cost_source'],'tabela')
        self.assertIsNone(lines[('reviewer','unpriced-model')]['usd'])
        voice=lines[('voice','eleven_multilingual_v2')]
        self.assertEqual((voice['credits'],voice['usd'],voice['credits_estimated']),(321.0,None,False))
        self.assertEqual(version['total']['unpriced'],2)
        self.assertAlmostEqual(version['total']['usd'],.01+.05+.004+7.4)
        self.assertFalse(next(v for v in usage['versions'] if v['id']==old['id'])['recorded'])
        pricing={**integrations.read()['pricing'],'elevenlabs_usd_per_1k_credits':.3,'usd_brl':5}
        pricing['models']={**pricing['models'],'unpriced-model':{'input':1,'cache_read':.1,'output':2}}
        self.assertEqual(self.client.put('/api/integrations/pricing',json={k:pricing[k] for k in ('usd_brl','elevenlabs_usd_per_1k_credits','models')}).status_code,200)
        usage=self.client.get(f'/api/projects/{self.project["id"]}/usage').json()
        self.assertEqual(usage['total']['unpriced'],0)
        self.assertAlmostEqual(usage['total']['usd'],.064+7.4+(.6*1+.4*.1+.02*2)+.321*.3)
        self.assertEqual(usage['usd_brl'],5)
        listed=next(p for p in self.client.get('/api/projects').json() if p['id']==self.project['id'])
        self.assertAlmostEqual(listed['usage_total']['usd'],usage['total']['usd'])
        self.assertEqual(self.client.put('/api/integrations/pricing',json={'usd_brl':0,'models':{}}).status_code,422)

    def test_interrupted_call_is_reconciled_from_the_runner_answer(self):
        job=self.start('plan')
        store.usage_start('late-answer',job['id'],'research',1,'grok','')
        store.cancel(job['id'])
        usage=costs.project(self.project['id'],integrations.read()['pricing'])
        self.assertEqual(usage['versions'][0]['calls'][0]['state'],'interrupted')
        self.assertTrue(usage['versions'][0]['calls'][0]['unreported'])
        bridge.atomic_json(bridge.BRIDGE/'requests'/'late-answer'/'response.json', {'error':'Agente interrompido.','usage':[
            {'model':'grok-4.7-build','input':10,'cache_read':0,'cache_write':0,'output':5,'reasoning':0,'web_searches':0,'cost_usd':.002}]})
        call=costs.project(self.project['id'],integrations.read()['pricing'])['versions'][0]['calls'][0]
        self.assertEqual((call['state'],call['usd'],call['output']),('failed',.002,5))

    def test_real_pipeline_renders_provider_audio_with_timestamps(self):
        job=self.start()
        mp3=DATA/'fixture.mp3'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=8','-codec:a','libmp3lame',str(mp3)],check=True)
        text='\n\n'.join(PARAGRAPHS)
        step=7.5/len(text)
        chars={'characters':list(text),'character_start_times_seconds':[i*step for i in range(len(text))], 'character_end_times_seconds':[(i+1)*step for i in range(len(text))]}
        response={'audio_base64':base64.b64encode(mp3.read_bytes()).decode(),'normalized_alignment':chars}
        with patch.object(bridge,'invoke',side_effect=[RESEARCH,SCRIPT,DIRECTION,{'approved':True,'issues':[]}]) as invoke, patch.object(elevenlabs,'api',return_value=response) as api:
            output=pipeline.produce(job)
        self.assertEqual(invoke.call_count,4)
        self.assertTrue(invoke.call_args_list[0].kwargs['web'])
        self.assertFalse(invoke.call_args_list[1].kwargs['web'])
        api.assert_called_once()
        self.assertEqual(api.call_args.kwargs['json']['text'],text)
        self.assertTrue(output['has_audio'])
        project=store.get_project(self.project['id'])
        self.assertEqual(project['title'],SCRIPT['title'])
        self.assertEqual(project['audio']['script_hash'],store.script_hash(project))
        self.assertEqual(project['revision'],self.project['revision']+2)
        folder=DATA/'projects'/project['id']/'renders'/job['id']
        self.assertTrue((folder/'short.mp4').is_file())
        self.assertTrue((folder/'legendas.srt').is_file())
        self.assertEqual(len(list((folder/'agents').glob('*.json'))),4)
        self.assertEqual([s['state'] for s in store.get_job(job['id'])['steps']],['succeeded']*6)
        store.finish(job['id'],'succeeded','Pronto',output)
        self.assertEqual(self.client.get(f'/api/jobs/{job["id"]}/files/short.mp4').status_code,200)

    def test_invalid_provider_timestamps_are_rejected(self):
        audio=DATA/'timestamp.wav';audio.write_bytes(b'fixture')
        with self.assertRaisesRegex(ValueError,'fora de ordem'):
            elevenlabs.transcript_from_characters({'characters':['a','b'],'character_start_times_seconds':[1,0], 'character_end_times_seconds':[2,1]},audio)
        with self.assertRaisesRegex(ValueError,'incompletos'):
            elevenlabs.transcript_from_characters({'characters':['a'],'character_start_times_seconds':[], 'character_end_times_seconds':[]},audio)

    def test_cli_adapters_parse_structured_outputs_and_disable_approval_prompts(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(commands.shutil,'which',side_effect=lambda name:'/bin/'+name):
            folder=Path(temp)
            for provider in bridge.PROVIDERS:
                args=agent_runner.command(provider,'test-model',folder,{'type':'object'},False)
                self.assertIn('--model',args)
                self.assertNotIn('--dangerously-skip-permissions',args)
                self.assertEqual(agent_runner.parse_result(provider,folder,json.dumps({'structured_output':{'approved':True}})),{'approved':True})
            self.assertEqual(agent_runner.parse_result('grok',folder,json.dumps({'text':'{"approved":true}'})),{'approved':True})
            (folder/'result.json').write_text('{"approved":true}')
            self.assertEqual(agent_runner.parse_result('codex',folder,'ignored'),{'approved':True})
            with self.assertRaisesRegex(ValueError,'JSON válido'):
                agent_runner.parse_result('claude',folder,'login required')

    def test_runner_restart_does_not_repeat_claimed_request(self):
        folder=bridge.BRIDGE/'requests'/'interrupted'
        folder.mkdir(parents=True,exist_ok=True)
        request=folder/'request.json';request.write_text('{}')
        (folder/'started').touch()
        with patch.object(agent_runner.subprocess,'Popen') as process:
            agent_runner.run_request(request)
            process.assert_not_called()
        self.assertIn('reiniciou',json.loads((folder/'response.json').read_text())['error'])

    def test_host_runner_executes_request_and_returns_structured_result(self):
        folder=bridge.BRIDGE/'requests'/'host-roundtrip'
        folder.mkdir(parents=True,exist_ok=True)
        request=folder/'request.json'
        request.write_text(json.dumps({'provider':'grok','model':'','prompt':'fixture','schema':{'type':'object'},'web':False,'expires':time.time()+30}))
        (folder/'lease').touch()
        import sys
        args=[sys.executable,'-c','import json; print(json.dumps({"text": "{\\\"approved\\\": true}"}))']
        with patch.object(agent_runner,'command',return_value=args):
            agent_runner.run_request(request)
        response=json.loads((folder/'response.json').read_text())
        self.assertEqual(response,{'result':{'approved':True},'usage':[]})
        self.assertTrue((folder/'started').is_file())
        # A second scan must not execute or overwrite a completed request.
        with patch.object(agent_runner.subprocess,'Popen') as process:
            agent_runner.run_request(request)
            process.assert_not_called()


    def test_the_author_edits_a_format_script_before_the_voice_and_the_voice_says_the_edited_text(self):
        # "Roteiro e cenas primeiro" stops before the voice: the author has the last word on the speech (ADR 0005).
        job=self.start('plan')
        with patch.object(bridge,'invoke',side_effect=[RESEARCH,SCRIPT,DIRECTION,{'approved':True,'issues':[]}]), \
                patch.object(elevenlabs,'api',side_effect=AssertionError('Sem voz antes da edição.')):
            pipeline.produce(job)
        store.finish(job['id'],'succeeded','Roteiro pronto')
        self.project=self.client.get(f'/api/projects/{self.project["id"]}').json()
        edited='Uma tarefa continua na nuvem enquanto você acompanha tudo pelo celular.'
        self.assertEqual(self.edit(scenes=[dict(self.project['scenes'][0],narration=edited),*self.project['scenes'][1:]]).status_code,200)
        response=self.client.post(f'/api/projects/{self.project["id"]}/run',json={'kind':'voice','revision':self.project['revision']})
        self.assertEqual(response.status_code,202,response.text)
        requests=[]
        with patch.object(elevenlabs,'api',side_effect=fake_voice(requests)):
            pipeline.produce(store.get_job(store.claim()['id'],private=True))
        self.assertTrue(requests[0]['text'].startswith(edited+'\n\n'+PARAGRAPHS[1]),requests[0]['text'])
        self.assertNotIn(PARAGRAPHS[0],requests[0]['text'])

    def test_plan_versions_keep_downloadable_text_without_cover_or_video(self):
        job=self.start('plan')
        with patch.object(bridge,'invoke',side_effect=[RESEARCH,SCRIPT,DIRECTION,{'approved':True,'issues':[]}]):
            self.assertIsNone(pipeline.produce(job))
        store.finish(job['id'],'succeeded','Roteiro pronto')
        result=store.get_job(job['id'])
        self.assertIsNone(result['output'])
        self.assertIn('roteiro.txt',result['materials'])
        # Covers are a separate process: the script agents never create one.
        self.assertNotIn('capa.png',result['materials'])
        self.assertNotIn('cover',store.get_project(self.project['id']))
        self.assertNotIn('narracao.wav',result['materials'])
        url=f'/api/jobs/{job["id"]}/materials/roteiro.txt'
        previous=self.client.get(url)
        self.assertEqual(previous.status_code,200)
        self.assertIn(PARAGRAPHS[0],previous.text)
        current=store.get_project(self.project['id'])
        store.update_project(current['id'],{'scenes':[dict(s,narration='Novo texto.') for s in current['scenes']]},current['revision'])
        self.assertEqual(self.client.get(url).text,previous.text)
        self.assertEqual(self.client.get(f'/api/jobs/{job["id"]}/materials/worker.log').status_code,404)
