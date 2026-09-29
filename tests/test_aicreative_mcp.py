from __future__ import annotations
import copy
import concurrent.futures
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared/media-runtime'))
import aicreative_mcp as mcp


def model():
    return {'modelType':'image','inputSettings':{'text':{'minCount':1,'maxCount':1300},
        'image':{'visibility':True,'maxCount':3,'maxWidth':3072,'maxHeight':3072},
        'frame':{'visibility':True,'type':'FIRST_LAST','forbiddenInputs':['image']}},
        'outputSettings':{'count':{'visibility':False,'minCount':1,'maxCount':6},
                          'aspectRatio':{'visibility':True,'values':[{'value':'1:1'}]}},
        'businessSettings':{'publicVisibility':{'visibility':True,'values':[{'value':'OFF'}]}}}


class Validation(unittest.TestCase):
    def setUp(self):
        self.request={'generationType':'IMAGE','prompt':'A'*1300,'parameters':{'count':1,'aspectRatioKey':'1:1','publicVisibilityKey':'OFF'}}

    def test_unicode_limit_and_oversize_reference(self):
        mcp.validate(self.request,model(),[])
        self.request['prompt']='😀'*1301
        with self.assertRaises(mcp.MCPError):mcp.validate(self.request,model(),[])
        self.request['prompt']='safe'
        with self.assertRaises(mcp.MCPError):mcp.validate(self.request,model(),[{'metadata':{'width':5120,'height':2880}}])

    def test_four_images_and_frame_conflicts(self):
        self.request['imageAssets']=[{'assetId':1}]*4
        with self.assertRaises(mcp.MCPError):mcp.validate(self.request,model(),[])
        self.request['imageAssets']=[];self.request['frame']={'lastFrame':{'assetId':1}}
        with self.assertRaises(mcp.MCPError):mcp.validate(self.request,model(),[])
        self.request['frame']['firstFrame']={'assetId':1};self.request['imageAssets']=[{'assetId':1}]
        with self.assertRaises(mcp.MCPError):mcp.validate(self.request,model(),[])

    def test_total_pixel_limit_without_dimension_limits(self):
        spec=model();spec['inputSettings']['image']={'visibility':True,'maxCount':14,'maxPixels':36000000}
        self.request['imageAssets']=[{'assetId':1}]
        with self.assertRaisesRegex(mcp.MCPError,'pixel-count'):
            mcp.validate(self.request,spec,[{'metadata':{'width':7000,'height':7000}}])
        mcp.validate(self.request,spec,[{'metadata':{'width':6000,'height':6000}}])

    def test_safe_configuration_and_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=Path(tmp)/'config.toml'
            cfg.write_text('[mcp_servers.aicreative]\nurl="https://trusted.test/api/mcp"\n[mcp_servers.aicreative.http_headers]\nAuthorization="Bearer private-secret"\n')
            with patch.dict(os.environ,{'AICREATIVE_CODEX_CONFIG':str(cfg)},clear=True):
                self.assertEqual(mcp.load_config()[0],'https://trusted.test/api/mcp')
                with self.assertRaises(mcp.MCPError):mcp.load_config('https://different.test/api/mcp')
        for url in ['file:///etc/passwd','http://example.com/a','https://user:pass@example.com/a']:
            with self.assertRaises(mcp.MCPError):mcp.https_url(url)

    def test_job_lock_prevents_duplicate_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'task.lock'
            with mcp.job_lock(path):
                with self.assertRaises(mcp.MCPError):
                    with mcp.job_lock(path):pass

    def test_credit_receipt_concurrent_claims_and_live_revalidation(self):
        class Client:
            scope='test-account';url='https://mcp.test/api/mcp';points=5
            def call(self,*args):return {'model':{**model(),'minPoints':self.points}}
        client=Client()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);review=root/'credits.json';source=root/'source.png'
            Image.new('RGB',(384,384),'blue').save(source)
            request={'generationType':'IMAGE','modelConfigId':2102,'prompt':'Product image',
                     'parameters':{'count':1,'aspectRatioKey':'1:1','publicVisibilityKey':'OFF'}}
            jobs=[mcp.credit_job(request,[str(source)],None,None,root/f'{i}.png',None) for i in range(2)]
            with self.assertRaisesRegex(mcp.MCPError,'大约需要消耗 10 积分'):
                mcp.prepare_credit_review(jobs,review,client)
            mcp.approve_credits(review,'Yes, proceed now')
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                claims=list(pool.map(lambda i:mcp.require_credit_job(jobs[i],review,client,f'id-{i}'),range(2)))
            self.assertEqual(len(claims),2)
            self.assertEqual(len(json.loads(review.read_text())['claims']),2)
            mcp.require_credit_job(jobs[0],review,client,'id-0')
            with self.assertRaisesRegex(mcp.MCPError,'already used'):
                mcp.require_credit_job(jobs[0],review,client,'new-id')
            for key,value in [('count',2),('publicVisibilityKey','ON')]:
                changed=copy.deepcopy(jobs[0]);changed['request']['parameters'][key]=value
                with self.assertRaisesRegex(mcp.MCPError,'does not cover'):
                    mcp.require_credit_job(changed,review,client,'id-0')
            client.points=8
            with self.assertRaisesRegex(mcp.MCPError,'starting credits changed'):
                mcp.require_credit_job(jobs[0],review,client,'id-0')
            client.points=5;client.scope='other-account'
            with self.assertRaisesRegex(mcp.MCPError,'does not cover'):
                mcp.require_credit_job(jobs[0],review,client,'id-0')
            client.scope='test-account';Image.new('RGB',(384,384),'red').save(source)
            with self.assertRaisesRegex(mcp.MCPError,'Reference content changed'):
                mcp.require_credit_job(jobs[0],review,client,'id-0')

    def test_json_rpc_sse_id_and_secret_redaction(self):
        with patch('aicreative_mcp.load_config',return_value=('https://mcp.test',{'authorization':'Bearer private-token'})):
            client=mcp.Client()
        class Response(io.BytesIO):
            headers={'Content-Type':'text/event-stream'}
        class Opener:
            def open(self,req,timeout):
                n=json.loads(req.data)['id']
                return Response(('data: '+json.dumps({'jsonrpc':'2.0','id':n,'result':{'ok':True}})+'\n\n').encode())
        client.opener=Opener()
        self.assertTrue(client.rpc('ping')['ok'])
        self.assertNotIn('private-token',client.redact('Bearer private-token'))
        client.opener.open=lambda req,timeout:Response(b'data: {"id":999,"result":{}}\n\n')
        with self.assertRaises(mcp.MCPError):client.rpc('ping')


class Workflows(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.state=self.root/'server.json'
        self.product=self.root/'product.png';Image.new('RGB',(384,384),'blue').save(self.product)
        self.env={k:v for k,v in os.environ.items() if not k.startswith(('AICREATIVE_','AI_GATEWAY_'))}
        self.env.update({'PYTHONPATH':os.pathsep.join([str(ROOT/'tests/fixtures'),str(Path(Image.__file__).parents[1]),os.environ.get('PYTHONPATH','')]), 'YOYO_FAKE_MCP_STATE':str(self.state),
            'AICREATIVE_MCP_URL':'https://mcp.test/api/mcp','AICREATIVE_MCP_TOKEN':'test-private-token',
            'AICREATIVE_CODEX_CONFIG':str(self.root/'missing.toml'),'AICREATIVE_CACHE_DIR':str(self.root/'cache')})

    def tearDown(self):self.temp.cleanup()

    def run_cli(self,script,*args,ok=True,approve=True):
        command=[sys.executable,str(ROOT/script),*map(str,args)]
        result=subprocess.run(command,env=self.env,text=True,capture_output=True)
        # Simulated human approval only in the isolated fake-service test harness.
        # The production CLI has no auto-approve switch or environment bypass.
        if approve and 'Credit approval required:' in result.stdout+result.stderr:
            for path in self.root.rglob('*.credits.json'):
                mcp.approve_credits(path, '同意上述预估积分（离线测试模拟用户）')
            result=subprocess.run(command,env=self.env,text=True,capture_output=True)
        if ok:self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        else:self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertNotIn('test-private-token',result.stdout+result.stderr)
        return result

    def server(self):return json.loads(self.state.read_text()) if self.state.exists() else {'tasks':{},'calls':[]}

    def bind(self):
        self.run_cli('standard-product-image/scripts/aicreative_mcp.py','bind','--file',self.product,'--asset-id','42')

    def image(self,*extra,ok=True,approve=True):
        return self.run_cli('standard-product-image/scripts/image_tool.py','edit','--prompt','Preserve the product','--image',self.product,
            '--output',self.root/'out.png','--save-json',self.root/'job.json','--poll-interval','0',*extra,ok=ok,approve=approve)

    def test_offline_preview_does_not_connect_or_require_binding(self):
        self.image('--dry-run')
        self.assertFalse(self.state.exists())
        self.assertFalse((self.root/'job.json').exists())

    def test_credit_gate_blocks_until_disclosed_estimate_is_approved(self):
        self.bind()
        result=self.image('--count','3',ok=False,approve=False)
        self.assertIn('大约需要消耗 15 积分',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)
        review=self.root/'job.json.credits.json'
        self.assertNotIn('approval',json.loads(review.read_text()))
        for reply in ['', '不同意', '不确认', '不可以', '不要继续', 'not approved', 'do not proceed']:
            with self.assertRaises(mcp.MCPError):mcp.approve_credits(review,reply)
        self.image('--count','3',ok=False,approve=False)
        self.assertEqual(len(self.server()['tasks']),0)
        self.run_cli('standard-product-image/scripts/aicreative_mcp.py','approve-credits',
                     '--review',review,'--confirmation','同意这次大约15积分',approve=False)
        journal=self.root/'job.json';state=json.loads(journal.read_text());state['startedAt']=1
        journal.write_text(json.dumps(state))
        self.image('--count','3',approve=False)
        self.assertLess(json.loads(journal.read_text())['observedSeconds'],30)
        self.assertEqual(len(self.server()['tasks']),1)
        self.assertEqual(len(json.loads(review.read_text())['claims']),1)

    def test_credit_gate_requotes_when_starting_price_changes(self):
        self.bind();self.image(ok=False,approve=False)
        review=self.root/'job.json.credits.json';mcp.approve_credits(review,'同意5积分')
        self.env['YOYO_FAKE_MIN_POINTS']='8'
        result=self.image(ok=False,approve=False)
        self.assertIn('大约需要消耗 8 积分',result.stderr)
        self.assertNotIn('approval',json.loads(review.read_text()))
        self.assertEqual(len(self.server()['tasks']),0)

    def test_credit_gate_rejects_unknown_price_and_tampered_review(self):
        self.bind();self.env['YOYO_FAKE_MIN_POINTS']='nan'
        result=self.image(ok=False,approve=False)
        self.assertIn('minPoints is unavailable',result.stderr)
        self.env.pop('YOYO_FAKE_MIN_POINTS')
        self.image(ok=False,approve=False)
        review=self.root/'job.json.credits.json';mcp.approve_credits(review,'同意5积分')
        data=json.loads(review.read_text());data['plan']['estimatedPoints']=0
        review.write_text(json.dumps(data))
        result=self.image(ok=False,approve=False)
        self.assertIn('大约需要消耗 5 积分',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)

    def test_credit_gate_cannot_reuse_approval_with_new_request_id(self):
        self.bind();self.image()
        (self.root/'out.png').unlink();(self.root/'job.json').unlink()
        result=self.image(ok=False,approve=False)
        self.assertIn('already used by another request',result.stderr)
        self.assertEqual(len(self.server()['tasks']),1)

    def test_credit_gate_existing_task_can_resume_without_review(self):
        self.bind();self.env['YOYO_FAKE_PENDING']='1'
        self.image('--max-polls','1',ok=False)
        (self.root/'job.json.credits.json').unlink()
        self.image('--max-polls','1',approve=False)
        self.assertEqual(len(self.server()['tasks']),1)

    def test_credit_gate_lost_response_across_processes_reuses_approved_id(self):
        self.bind();self.env['YOYO_FAKE_LOST_SUBMIT_ALWAYS']='1'
        self.image(ok=False)
        saved=json.loads((self.root/'job.json').read_text())
        self.assertNotIn('taskId',saved)
        self.assertIn('creditAuthorization',saved)
        (self.root/'job.json.credits.json').unlink()
        self.env.pop('YOYO_FAKE_LOST_SUBMIT_ALWAYS')
        self.image(approve=False)
        submits=[c for c in self.server()['calls'] if c['name']=='submit_generation_task']
        self.assertEqual(len(submits),4)
        self.assertEqual(len({c['arguments']['clientRequestId'] for c in submits}),1)
        self.assertEqual(len(self.server()['tasks']),1)

    def test_credit_gate_new_output_is_not_covered_by_prior_approval(self):
        self.bind();self.image()
        result=self.image('--output',self.root/'different.png','--save-json',self.root/'different.json',
                          '--credit-review',self.root/'job.json.credits.json',ok=False,approve=False)
        self.assertIn('does not cover',result.stderr)
        self.assertEqual(len(self.server()['tasks']),1)

    def test_credit_gate_storyboard_and_video_are_separate_batches(self):
        self.bind();project=self.root/'story';script='script-to-storyboard-video/scripts/script_to_storyboard_video.py'
        command=['storyboard','--script','Hook, demo, CTA','--product-image',self.product,'--duration','16','--project-dir',project]
        result=self.run_cli(script,*command,ok=False,approve=False)
        self.assertIn('大约需要消耗 10 积分',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)
        mcp.approve_credits(project/'storyboard.credits.json','同意10积分')
        self.run_cli(script,*command,approve=False)
        video=['video','--project-dir',project,'--confirmed','--parallel','1']
        result=self.run_cli(script,*video,ok=False,approve=False)
        self.assertIn('大约需要消耗 80 积分',result.stderr)
        self.assertEqual(len(self.server()['tasks']),2)
        mcp.approve_credits(project/'video.credits.json','同意80积分')
        self.run_cli(script,*video,approve=False)
        self.assertEqual(len(self.server()['tasks']),4)

    def test_credit_gate_ugc_quotes_entire_chain_before_character_generation(self):
        self.bind();project=self.root/'ugc';script='product-to-ugc-video/scripts/product_to_ugc.py'
        command=['--product-image',self.product,'--description','A mug','--segment-count','2','--segment-duration','4',
                 '--heuristic-plan','--skip-merge','--project-dir',project,'--poll-interval','0']
        result=self.run_cli(script,*command,ok=False,approve=False)
        self.assertIn('大约需要消耗 70 积分',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)
        review=project/'generation.credits.json'
        self.assertEqual(len(json.loads(review.read_text())['plan']['jobs']),6)
        mcp.approve_credits(review,'同意本方案大约70积分')
        self.run_cli(script,*command,approve=False)
        self.assertEqual(len(self.server()['tasks']),6)
        self.run_cli(script,*command,approve=False)
        self.assertEqual(len(self.server()['tasks']),6)

    def test_credit_gate_batch_changes_invalidate_approval(self):
        self.bind();project=self.root/'story';script='script-to-storyboard-video/scripts/script_to_storyboard_video.py'
        command=['storyboard','--script','Hook','--product-image',self.product,'--duration','16','--project-dir',project]
        self.run_cli(script,*command,ok=False,approve=False)
        review=project/'storyboard.credits.json';original=json.loads(review.read_text())['reviewHash']
        changes=[['--script','New hook'], ['--image-model','2103'], ['--storyboard-size','1024x1024'], ['--duration','24']]
        for extra in changes:
            self.run_cli(script,*command,ok=False,approve=False)
            mcp.approve_credits(review,'同意10积分')
            self.run_cli(script,*command,*extra,ok=False,approve=False)
            updated=json.loads(review.read_text())
            self.assertNotEqual(original,updated['reviewHash'])
            self.assertNotIn('approval',updated)
        self.assertEqual(len(self.server()['tasks']),0)

    def test_credit_gate_source_content_change_invalidates_approval(self):
        self.bind();project=self.root/'story';script='script-to-storyboard-video/scripts/script_to_storyboard_video.py'
        command=['storyboard','--script','Hook','--product-image',self.product,'--duration','8','--project-dir',project]
        self.run_cli(script,*command,ok=False,approve=False)
        review=project/'storyboard.credits.json';mcp.approve_credits(review,'同意5积分')
        Image.new('RGB',(384,384),'purple').save(self.product)
        self.run_cli(script,*command,ok=False,approve=False)
        self.assertNotIn('approval',json.loads(review.read_text()))
        self.assertEqual(len(self.server()['tasks']),0)

    def test_missing_binding_fails_before_submission(self):
        result=self.image(ok=False)
        self.assertIn('Local reference is not bound',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)

    def test_image_resolves_model_default_and_preserves_it_on_resume(self):
        self.bind();self.env['YOYO_FAKE_RESOLUTION_DEFAULT']='4K'
        self.image()
        request=next(iter(self.server()['tasks'].values()))['request']
        self.assertEqual(request['parameters']['resolutionKey'],'4K')
        self.env['YOYO_FAKE_RESOLUTION_DEFAULT']='2K'
        self.image()
        self.assertEqual(len(self.server()['tasks']),1)

    def test_explicit_resolution_overrides_model_default(self):
        self.bind();self.image('--resolution','4K')
        request=next(iter(self.server()['tasks'].values()))['request']
        self.assertEqual(request['parameters']['resolutionKey'],'4K')

    def test_invalid_output_suffix_fails_before_submission(self):
        self.bind()
        result=self.run_cli('standard-product-image/scripts/image_tool.py','edit','--prompt','Preserve product',
            '--image',self.product,'--output',self.root/'invalid.gif',ok=False)
        self.assertIn('Image output must use',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)

    def test_ugc_merge_failure_returns_failure_and_keeps_segments(self):
        self.bind();bin_dir=self.root/'bin';bin_dir.mkdir();ffmpeg=bin_dir/'ffmpeg'
        ffmpeg.write_text('#!/bin/sh\nif [ "$1" = "-version" ]; then exit 0; fi\necho "simulated merge failure" >&2\nexit 17\n')
        ffmpeg.chmod(0o755);self.env['PATH']=str(bin_dir)+os.pathsep+self.env['PATH']
        self.run_cli('product-to-ugc-video/scripts/product_to_ugc.py','--product-image',self.product,
            '--description','A white mug','--segment-count','1','--segment-duration','4','--heuristic-plan',
            '--project-dir',self.root/'ugc','--poll-interval','0',ok=False)
        manifest=json.loads((self.root/'ugc/manifests/merge_manifest.json').read_text())
        self.assertIn('simulated merge failure',manifest['merge_error'])
        self.assertTrue(all(Path(p).is_file() for p in manifest['segment_files']))

    def test_ugc_same_basename_inputs_remain_distinct_and_can_be_reused(self):
        other=self.root/'other';other.mkdir();character=other/self.product.name
        Image.new('RGB',(384,384),'green').save(character)
        base=['--description','White mug','--heuristic-plan','--planner-only','--project-dir',self.root/'ugc']
        script='product-to-ugc-video/scripts/product_to_ugc.py'
        self.run_cli(script,'--product-image',self.product,'--character-reference',character,*base)
        project=json.loads((self.root/'ugc/project.json').read_text())
        self.assertEqual(Path(project['product_image']).read_bytes(),self.product.read_bytes())
        self.assertEqual(Path(project['character_reference_input']).read_bytes(),character.read_bytes())
        self.assertNotEqual(project['product_image'],project['character_reference_input'])
        self.run_cli(script,'--product-image',project['product_image'],'--character-reference',project['character_reference_input'],*base)

    def test_bind_by_source_and_copy_by_content_hash(self):
        self.run_cli('standard-product-image/scripts/aicreative_mcp.py','bind','--file',self.product,'--source-url','https://media.test/input.jpg')
        copied=self.root/'renamed.png';copied.write_bytes(self.product.read_bytes());self.product=copied
        self.image()
        imports=[c for c in self.server()['calls'] if c['name']=='upload_media']
        self.assertEqual(len(imports),1)

    def test_lost_response_resume_and_output_format(self):
        self.bind();self.env['YOYO_FAKE_LOST_SUBMIT']='1'
        self.image();self.image()
        state=self.server();self.assertEqual(len(state['tasks']),1)
        submits=[c for c in state['calls'] if c['name']=='submit_generation_task']
        self.assertEqual(len(submits),2)
        self.assertEqual(submits[0]['arguments']['clientRequestId'],submits[1]['arguments']['clientRequestId'])
        with Image.open(self.root/'out.png') as im:self.assertEqual(im.format,'PNG')
        with Image.open(self.root/'out.png.original') as im:self.assertEqual(im.format,'JPEG')
        journal=json.loads((self.root/'job.json').read_text())
        self.assertEqual(journal['lastTask']['status'],'SUCCESS')
        self.assertNotIn('test-private-token',(self.root/'job.json').read_text())

    def test_polling_limit_resume_ignores_transient_item_failure(self):
        self.bind();self.env['YOYO_FAKE_PENDING']='1'
        self.image('--max-polls','1',ok=False)
        self.image('--max-polls','1')
        self.assertEqual(len(self.server()['tasks']),1)
        submits=[c for c in self.server()['calls'] if c['name']=='submit_generation_task']
        self.assertEqual(len(submits),1)

    def test_changed_input_cannot_reuse_output_journal(self):
        self.bind();self.image()
        self.run_cli('standard-product-image/scripts/image_tool.py','edit','--prompt','Changed prompt','--image',self.product,
            '--output',self.root/'out.png','--save-json',self.root/'job.json',ok=False)
        self.assertEqual(len(self.server()['tasks']),1)

    def test_partial_results_are_preserved_without_resubmission(self):
        self.bind();self.env['YOYO_FAKE_PARTIAL']='1'
        self.image('--count','2',ok=False)
        self.assertTrue((self.root/'out.png').is_file())
        journal=json.loads((self.root/'job.json').read_text())
        self.assertEqual(len(journal['downloads']),1)
        self.image('--count','2',ok=False)
        self.assertEqual(len(self.server()['tasks']),1)

    def test_same_account_token_renewal_with_stable_scope(self):
        self.env['AICREATIVE_ACCOUNT_SCOPE']='same-test-account'
        self.bind();self.image()
        self.env['AICREATIVE_MCP_TOKEN']='renewed-test-token'
        self.image()
        self.assertEqual(len(self.server()['tasks']),1)

    def test_storyboard_then_approved_video(self):
        self.bind();project=self.root/'story'
        command=['storyboard','--script','Hook, demo, CTA','--product-image',self.product,'--duration','16','--project-dir',project]
        self.run_cli('script-to-storyboard-video/scripts/script_to_storyboard_video.py',*command)
        self.run_cli('script-to-storyboard-video/scripts/script_to_storyboard_video.py','video','--project-dir',project,ok=False)
        self.assertEqual(len(self.server()['tasks']),2)
        self.run_cli('script-to-storyboard-video/scripts/script_to_storyboard_video.py','video','--project-dir',project,'--confirmed','--parallel','1')
        tasks=list(self.server()['tasks'].values());self.assertEqual(len(tasks),4)
        videos=[t['request'] for t in tasks if t['request']['generationType']=='VIDEO']
        self.assertEqual([v['parameters']['duration'] for v in videos],[8,8])
        self.assertTrue(all(v.get('imageAssets') and not v.get('frame') for v in videos))
        self.run_cli('script-to-storyboard-video/scripts/script_to_storyboard_video.py',*command)
        self.assertEqual(len(self.server()['tasks']),4)

    def test_ugc_uses_three_image_refs_and_explicit_frame_anchors(self):
        self.bind()
        self.run_cli('product-to-ugc-video/scripts/product_to_ugc.py','--product-image',self.product,
            '--description','A red mug','--segment-count','1','--segment-duration','5','--heuristic-plan','--skip-merge',
            '--project-dir',self.root/'ugc','--poll-interval','0')
        tasks=[t['request'] for t in self.server()['tasks'].values()]
        self.assertEqual(len(tasks),4)
        self.assertEqual([len(t.get('imageAssets',[])) for t in tasks if t['generationType']=='IMAGE'],[1,2,3])
        self.assertTrue(all(t['parameters']['aspectRatioKey']=='9:16' for t in tasks if t['generationType']=='IMAGE'))
        video=next(t for t in tasks if t['generationType']=='VIDEO')
        self.assertEqual(set(video['frame']),{'firstFrame','lastFrame'})
        self.assertNotIn('imageAssets',video)
        self.assertEqual(video['parameters']['generateAudioKey'],'ON')

    def test_ugc_rejects_incompatible_person_model_before_image_generation(self):
        self.bind();self.env['YOYO_FAKE_NO_PERSON']='1'
        result=self.run_cli('product-to-ugc-video/scripts/product_to_ugc.py','--product-image',self.product,
            '--description','A mug','--segment-count','1','--heuristic-plan','--project-dir',self.root/'ugc',ok=False)
        self.assertIn('supports person references',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)

    def test_ugc_rejects_unsupported_audio_before_image_generation(self):
        self.bind()
        result=self.run_cli('product-to-ugc-video/scripts/product_to_ugc.py','--product-image',self.product,
            '--description','A mug','--segment-count','1','--heuristic-plan','--project-dir',self.root/'ugc',
            '--video-model','1108','--no-generate-audio',ok=False)
        self.assertIn('unsupported generateAudioKey',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)

    def test_detail_page_approval_and_real_adapter(self):
        pack=self.root/'pack.json'
        pack.write_text(json.dumps({'screens':[{'screen_id':1,'final_prompt_en':'A faithful product image',
            'text_to_render':{'verbatim':True,'language':'English','headline':'Simple'},
            'backend_params':{'aspect_ratio':'1:1','reference_images':[]},'assembly_plan':{'order':1}},
            {'screen_id':2,'final_prompt_en':'Product details','text_to_render':{'verbatim':True,'headline':'Details'},
             'backend_params':{'aspect_ratio':'1:1','reference_images':[]},'assembly_plan':{'order':2}}]}))
        scripts='product-detail-page-pipeline/scripts/'
        output=self.root/'detail';review=self.root/'review';approval=review/'approval.json'
        self.run_cli(scripts+'run_image_generation.py','--prompt-pack',pack,'--output-dir',output,ok=False)
        self.assertFalse(self.state.exists())
        self.run_cli(scripts+'prepare_generation_review.py','--prompt-pack',pack,'--output-dir',review)
        self.run_cli(scripts+'record_generation_approval.py','--prompt-pack',pack,'--review',review/'generation_review.json',
            '--output',approval,'--confirmation','开始生图')
        command=['--prompt-pack',pack,'--output-dir',output,'--approval-file',approval,'--skip-backend-check']
        blocked=self.run_cli(scripts+'run_image_generation.py',*command,ok=False,approve=False)
        self.assertIn('大约需要消耗 10 积分',blocked.stderr)
        self.assertEqual(len(self.server()['tasks']),0)
        mcp.approve_credits(output/'generation.credits.json','同意所选两页大约10积分')
        self.run_cli(scripts+'run_image_generation.py',*command,approve=False)
        self.assertEqual(len(self.server()['tasks']),2)
        self.assertTrue((output/'images/screen_01.png').is_file())
        self.assertTrue((output/'images/screen_01.png.original').is_file())


if __name__=='__main__':unittest.main()
