from __future__ import annotations
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('describe_analyzer', ROOT/'scripts/analyze_video.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
FULL = '\n\n'.join(f'## {i}. {topic}\n- Observed content.' for i, topic in enumerate(api.TOPICS,1))


class Response(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data)
        self.status=status
        self.headers={'Content-Type':'application/json','X-Request-Id':'fixture-id'}


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.video=self.root/'测试视频.mp4';self.video.write_bytes(b'video-fixture')
        self.output=self.root/'analysis.md'
        self.calls=[];self.status=200;self.response={'result':FULL,'input_token':10,'output_token':20,'total_token':30}
        self.env=patch.dict(os.environ,{'VIDEO_ANALYSIS_API_KEY':'private-test-key','PATH':os.environ.get('PATH','')},clear=True);self.env.start()
        self.skill=patch.object(api,'SKILL_DIR',self.root);self.skill.start()
        class Opener:
            def open(inner,req,timeout):
                chunks=list(req.data);body=b''.join(chunks)
                self.calls.append((req,body,timeout,chunks))
                raw=self.response if isinstance(self.response,bytes) else json.dumps(self.response).encode()
                return Response(raw,self.status)
        self.transport=patch.object(api.request,'build_opener',return_value=Opener());self.transport.start()

    def tearDown(self):
        self.transport.stop();self.skill.stop();self.env.stop();self.tmp.cleanup()

    def run_analysis(self,*extra):
        args=['--video',str(self.video),'--prompt','中文 analysis request','--environment','local','--output',str(self.output),*extra]
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            return api.main(args)

    def test_local_auth_and_file_multipart(self):
        self.run_analysis('--profile','tiktok')
        req,body,_,_=self.calls[0]
        self.assertEqual(req.full_url,'https://agentapi.spotmaxtech.com/api/v1/describe_video')
        self.assertEqual(req.get_header('X-api-key'),'private-test-key')
        self.assertNotIn('Authorization',req.headers)
        self.assertIn('中文 analysis request'.encode(),body)
        self.assertIn(b'name="video_file"',body);self.assertNotIn(b'name="video_url"',body)
        self.assertIn(self.video.read_bytes(),body)
        self.assertEqual(int(req.get_header('Content-length')),len(body))
        self.assertEqual(self.output.read_text().strip(),FULL)
        meta=json.loads(Path(str(self.output)+'.run.json').read_text())
        self.assertEqual(meta['status'],'success');self.assertEqual(meta['usage']['total_token'],30)
        self.assertEqual(meta['requestId'],'fixture-id');self.assertGreaterEqual(meta['elapsedSeconds'],meta['requestSeconds'])
        self.assertNotIn('private-test-key',json.dumps(meta))

    def test_production_omits_all_credential_headers_even_with_leftover_key(self):
        self.run_analysis('--environment','production','--base-url','http://video-service.internal:8080')
        req=self.calls[0][0]
        self.assertEqual(req.full_url,'http://video-service.internal:8080/api/v1/describe_video')
        for header in ('X-api-key','Authorization','X-goog-api-key'):self.assertNotIn(header,req.headers)

    def test_local_requires_key_but_does_not_inherit_old_gateway_key(self):
        os.environ.pop('VIDEO_ANALYSIS_API_KEY');os.environ['AI_GATEWAY_API_KEY']='old-secret'
        with self.assertRaisesRegex(api.AnalysisError,'requires VIDEO_ANALYSIS_API_KEY'):self.run_analysis()
        self.assertEqual(self.calls,[])

    def test_env_overrides_local_dotenv_without_evaluating_values(self):
        (self.root/'.env').write_text('VIDEO_ANALYSIS_ENV=local\nVIDEO_ANALYSIS_API_KEY="from-file"\nAI_GATEWAY_API_KEY=ignore\n')
        self.assertEqual(api.settings()['VIDEO_ANALYSIS_API_KEY'],'private-test-key')
        self.assertEqual(api.settings()['VIDEO_ANALYSIS_ENV'],'local')
        self.assertNotIn('AI_GATEWAY_API_KEY',api.settings())

    def test_url_request_sends_only_video_url(self):
        with contextlib.redirect_stdout(io.StringIO()):
            api.main(['--video-url','https://media.example/video.mp4?signature=temporary','--prompt','Describe video'])
        req,body,_,_=self.calls[0]
        self.assertIn(b'name="video_url"',body);self.assertNotIn(b'name="video_file"',body)
        self.assertNotIn('X-api-key',req.headers)

    def test_url_metadata_omits_signed_query(self):
        with contextlib.redirect_stderr(io.StringIO()):
            api.main(['--video-url','https://media.example/video.mp4?signature=temporary','--prompt','Describe','--output',str(self.output)])
        meta=json.loads(Path(str(self.output)+'.run.json').read_text())
        self.assertNotIn('signature',meta['source']['url'])

    def test_two_inputs_or_no_input_rejected(self):
        for args in [[],['--video',str(self.video),'--video-url','https://media.example/v.mp4']]:
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                api.parse_args([*args,'--prompt','Describe'])
        self.assertFalse(self.calls)

    def test_legacy_controls_are_not_silently_ignored(self):
        for extra in [('--model','flash'),('--resolution=medium',),('--fps','1'),('--auth-mode','both'),('--allow-large-inline',)]:
            with self.assertRaisesRegex(api.AnalysisError,'legacy Gemini'):self.run_analysis(*extra)
        self.assertFalse(self.calls)

    def test_endpoint_and_media_validation(self):
        self.assertEqual(api.endpoint(api.DEFAULT_BASE_URL+api.ENDPOINT_PATH),api.DEFAULT_BASE_URL+api.ENDPOINT_PATH)
        for value in ['http://example.com','https://user:pass@example.com','https://example.com?key=secret']:
            with self.assertRaises(api.AnalysisError):api.endpoint(value)
        for value in ['http://media.example/v.mp4','https://user:pass@media.example/v.mp4','https://vm.tiktok.com/abc/']:
            with self.assertRaises(api.AnalysisError):api.media_url(value)
        self.assertTrue(api.endpoint('http://127.0.0.1:1234').endswith(api.ENDPOINT_PATH))

    def test_empty_missing_and_nonvideo_input(self):
        self.video.write_bytes(b'')
        with self.assertRaises(api.AnalysisError):self.run_analysis()
        self.video.unlink()
        with self.assertRaises(api.AnalysisError):self.run_analysis()
        self.video.write_bytes(b'data')
        with self.assertRaises(api.AnalysisError):self.run_analysis('--mime-type','text/plain')
        self.assertFalse(self.calls)

    def test_large_upload_is_streamed_without_old_20mb_restriction(self):
        with self.video.open('wb') as f:f.truncate(21*1024*1024)
        body=api.Multipart('Describe',file=self.video)
        chunks=list(body)
        self.assertEqual(sum(map(len,chunks)),body.length)
        self.assertLessEqual(max(map(len,chunks)),1024*1024)

    def test_newlines_cannot_inject_upload_headers(self):
        with self.assertRaises(api.AnalysisError):api.Multipart('Describe',file=self.video,mime='video/mp4\r\nX-Test: value')
        odd=self.root/'evil\r\nInjected:header.mp4';odd.write_bytes(b'video')
        self.assertNotIn(b'Injected',b''.join(api.Multipart('Describe',file=odd)))

    def test_offline_preview_needs_no_key_no_http_or_ffmpeg(self):
        os.environ.clear()
        self.run_analysis('--dry-run','--start','1','--end','2')
        self.assertFalse(self.calls);self.assertFalse(self.output.exists())

    def test_full_prompt_file_and_general_response(self):
        prompt=self.root/'prompt.md';prompt.write_text('中文\n'+('Long prompt. '*500))
        self.response={'result':'A concise summary.'}
        with contextlib.redirect_stdout(io.StringIO()):
            api.main(['--video',str(self.video),'--prompt-file',str(prompt)])
        self.assertIn(prompt.read_bytes(),self.calls[0][1])

    def test_unknown_empty_and_business_errors_do_not_become_analysis(self):
        for response in [{},{'result':''},{'result':{'text':'wrong shape'}},{'error':'failed','result':'text'},
                         {'code':500,'result':'text'},[],{'success':False,'result':'text'}]:
            self.response=response
            with self.assertRaises(api.AnalysisError):self.run_analysis()
            self.assertFalse(self.output.exists())

    def test_http_and_non_json_failures_are_saved_without_retry(self):
        for status in [401,403,413,429,500,502]:
            before=len(self.calls);self.status=status;self.response={'message':'failed'}
            with self.assertRaisesRegex(api.AnalysisError,f'HTTP {status}'):self.run_analysis()
            self.assertEqual(len(self.calls),before+1)
            self.assertFalse(self.output.exists())
        self.status=200;self.response=b'<html>unexpected</html>'
        with self.assertRaisesRegex(api.AnalysisError,'not valid JSON'):self.run_analysis()
        self.assertIn('unparsedBody',json.loads(Path(str(self.output)+'.response.json').read_text()))

    def test_incomplete_eight_dimensions_and_observed_whitespace_failure(self):
        for text in ['## 1. 前2秒钩子分析\nOnly one section',FULL+' '*1000+'Unrelated content']:
            self.response={'result':text};self.output.write_text('previous valid result')
            with self.assertRaises(api.AnalysisError):self.run_analysis('--profile','tiktok')
            self.assertEqual(self.output.read_text(),'previous valid result')
            self.assertEqual(json.loads(Path(str(self.output)+'.run.json').read_text())['status'],'failed')
            self.assertEqual(json.loads(Path(str(self.output)+'.response.json').read_text())['result'],text)

    def test_response_and_error_logs_redact_test_key(self):
        os.environ['VIDEO_ANALYSIS_API_KEY']='  private-test-key\n'
        self.response={'result':'secret echoed: private-test-key','headers':{'X-API-Key':'private-test-key'}}
        self.run_analysis()
        for p in self.root.glob('analysis.md*'):self.assertNotIn('private-test-key',p.read_text())

    def test_response_size_limit(self):
        self.response=b'x'*(api.MAX_RESPONSE_BYTES+1)
        with self.assertRaisesRegex(api.AnalysisError,'response exceeds'):self.run_analysis()

    def test_transport_timeout_has_no_automatic_retry(self):
        opener=api.request.build_opener.return_value
        opener.open=lambda *a,**kw:(_ for _ in ()).throw(URLError('failed private-test-key'))
        with self.assertRaisesRegex(api.AnalysisError,'No automatic retry'):self.run_analysis()
        meta=Path(str(self.output)+'.run.json').read_text()
        self.assertNotIn('private-test-key',meta)

    def test_redirect_refuses_credential_forwarding(self):
        with self.assertRaisesRegex(api.AnalysisError,'redirect refused'):
            api.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example/')

    def test_output_and_input_collisions_fail_before_request(self):
        for extra in [('--response-json',str(self.output)),('--output',str(self.video)),('--metadata-json',str(self.output))]:
            with self.assertRaisesRegex(api.AnalysisError,'must not overlap'):self.run_analysis(*extra)
        self.assertFalse(self.calls)

    def test_clip_offsets_and_url_restrictions(self):
        for extra in [('--start','-1'),('--start','3','--end','1'),('--end','nan'),('--start-offset','00:02:00')]:
            with self.assertRaises(api.AnalysisError):self.run_analysis(*extra)
        with self.assertRaisesRegex(api.AnalysisError,'local --video'):
            api.main(['--video-url','https://media.example/v.mp4','--prompt','Describe','--start','1'])
        self.assertFalse(self.calls)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'ffmpeg/ffprobe unavailable')
    def test_real_local_clip_preserves_audio_and_cleans_up(self):
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=64x64:d=3',
                        '-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','libx264','-c:a','aac','-y',str(self.video)],check=True)
        with api.prepared_video(self.video,1,2) as clip:
            data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(clip)]))
            self.assertAlmostEqual(float(data['format']['duration']),1,delta=0.1)
            self.assertEqual({s['codec_type'] for s in data['streams']},{'video','audio'})
            self.assertNotEqual(clip,self.video)
        self.assertFalse(clip.exists());self.assertTrue(self.video.exists())
        self.run_analysis('--start','1','--end','2','--mime-type','video/quicktime')
        self.assertIn(b'Content-Type: video/mp4',self.calls[0][1])
        metadata=json.loads(Path(str(self.output)+'.run.json').read_text())
        self.assertEqual(metadata['clip']['startSeconds'],1)
        self.assertTrue(metadata['clip']['timestampsRelativeToClip'])
        with self.assertRaises(api.AnalysisError):
            with api.prepared_video(self.video,2,5):pass


if __name__=='__main__':unittest.main()
