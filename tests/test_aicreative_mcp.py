from __future__ import annotations
import copy
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

    def run_cli(self,script,*args,ok=True):
        result=subprocess.run([sys.executable,str(ROOT/script),*map(str,args)],env=self.env,text=True,capture_output=True)
        if ok:self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        else:self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertNotIn('test-private-token',result.stdout+result.stderr)
        return result

    def server(self):return json.loads(self.state.read_text()) if self.state.exists() else {'tasks':{},'calls':[]}

    def bind(self):
        self.run_cli('standard-product-image/scripts/aicreative_mcp.py','bind','--file',self.product,'--asset-id','42')

    def image(self,*extra,ok=True):
        return self.run_cli('standard-product-image/scripts/image_tool.py','edit','--prompt','Preserve the product','--image',self.product,
            '--output',self.root/'out.png','--save-json',self.root/'job.json','--poll-interval','0',*extra,ok=ok)

    def test_offline_preview_does_not_connect_or_require_binding(self):
        self.image('--dry-run')
        self.assertFalse(self.state.exists())
        self.assertFalse((self.root/'job.json').exists())

    def test_missing_binding_fails_before_submission(self):
        result=self.image(ok=False)
        self.assertIn('Local reference is not bound',result.stderr)
        self.assertEqual(len(self.server()['tasks']),0)

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
        video=next(t for t in tasks if t['generationType']=='VIDEO')
        self.assertEqual(set(video['frame']),{'firstFrame','lastFrame'})
        self.assertNotIn('imageAssets',video)
        self.assertEqual(video['parameters']['generateAudioKey'],'OFF')

    def test_detail_page_approval_and_real_adapter(self):
        pack=self.root/'pack.json'
        pack.write_text(json.dumps({'screens':[{'screen_id':1,'final_prompt_en':'A faithful product image',
            'text_to_render':{'verbatim':True,'language':'English','headline':'Simple'},
            'backend_params':{'aspect_ratio':'1:1','reference_images':[]},'assembly_plan':{'order':1}}]}))
        scripts='product-detail-page-pipeline/scripts/'
        output=self.root/'detail';review=self.root/'review';approval=review/'approval.json'
        self.run_cli(scripts+'run_image_generation.py','--prompt-pack',pack,'--output-dir',output,ok=False)
        self.assertFalse(self.state.exists())
        self.run_cli(scripts+'prepare_generation_review.py','--prompt-pack',pack,'--output-dir',review)
        self.run_cli(scripts+'record_generation_approval.py','--prompt-pack',pack,'--review',review/'generation_review.json',
            '--output',approval,'--confirmation','开始生图')
        self.run_cli(scripts+'run_image_generation.py','--prompt-pack',pack,'--output-dir',output,'--approval-file',approval)
        self.assertEqual(len(self.server()['tasks']),1)
        self.assertTrue((output/'images/screen_01.png').is_file())
        self.assertTrue((output/'images/screen_01.png.original').is_file())


if __name__=='__main__':unittest.main()
