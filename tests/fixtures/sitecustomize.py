"""Offline MCP transport for subprocess integration tests only.

Activated solely by the tests' temporary PYTHONPATH and YOYO_FAKE_MCP_STATE.
No generation code has a fake-service switch.
"""
import io
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

if os.getenv('YOYO_FAKE_MCP_STATE'):
    from PIL import Image
    state_file=Path(os.environ['YOYO_FAKE_MCP_STATE'])
    time.sleep=lambda _:None
    buf=io.BytesIO()
    Image.new('RGB',(384,384),'red').save(buf,format='JPEG')
    media=buf.getvalue()

    def spec(kind):
        enum=lambda values:{'visibility':True,'values':[{'value':v} for v in values]}
        return {'modelType':kind.lower(),'inputSettings':{
            'text':{'minCount':1,'maxCount':5000},
            'image':{'visibility':True,'maxCount':14,'minWidth':300,'minHeight':300},
            'frame':{'visibility':True,'type':'FIRST_LAST','forbiddenInputs':['image'],'minWidth':300,'minHeight':300}},
            'outputSettings':{'count':{'visibility':False,'minCount':1,'maxCount':6},
                              'duration':{'visibility':True,'minCount':4,'maxCount':15},
                              'resolution':enum(['720P','1080P','2K']),
                              'aspectRatio':enum(['1:1','2:3','3:2','9:16','16:9']),
                              'generateAudio':{'visibility':True,'values':{'ON':True,'OFF':False}}},
            'businessSettings':{'publicVisibility':enum(['ON','OFF'])}}

    class Response(io.BytesIO):
        def __init__(self,body):
            super().__init__(body)
            self.headers={'Content-Type':'application/json'}

    class Opener:
        def open(self,request,timeout=None):
            state=json.loads(state_file.read_text()) if state_file.exists() else {'tasks':{},'calls':[]}
            def save():state_file.write_text(json.dumps(state))
            if isinstance(request,str):
                assert request.startswith('https://media.test/'),request
                return Response(media)
            assert request.full_url=='https://mcp.test/api/mcp',request.full_url
            payload=json.loads(request.data)
            method=payload['method']
            if method=='initialize':
                value={'protocolVersion':'2025-03-26','capabilities':{},'serverInfo':{'name':'fake','version':'1'}}
            elif method=='notifications/initialized':
                return Response(b'')
            else:
                name=payload['params']['name'];args=payload['params']['arguments']
                state['calls'].append({'name':name,'arguments':args})
                if name=='get_model_parameters':
                    value={'model':spec('IMAGE' if args['modelConfigId']>=2000 else 'VIDEO')}
                elif name=='list_models':
                    value={'models':[{'modelConfigId':2102,'modelType':'image','displayName':'Fake'}]}
                elif name=='upload_media':
                    value={'asset':{'assetId':9000,'url':args['sourceUrl'],'metadata':{'width':384,'height':384}}}
                elif name=='submit_generation_task':
                    cid=args['clientRequestId']
                    if cid not in state['tasks']:
                        state['tasks'][cid]={'taskId':'GT_'+str(len(state['tasks'])+1),'request':args,'polls':0}
                    task=state['tasks'][cid]
                    value={'task':{'taskId':task['taskId'],'status':'PROCESSING','items':[]}}
                    if os.getenv('YOYO_FAKE_LOST_SUBMIT') and not state.get('lost'):
                        state['lost']=True;save()
                        raise urllib.error.URLError('simulated response lost after acceptance')
                elif name=='get_generation_task':
                    task=next(t for t in state['tasks'].values() if t['taskId']==args['taskId'])
                    task['polls']+=1
                    pending=os.getenv('YOYO_FAKE_PENDING') and task['polls']==1
                    items=[] if pending else [{'assetId':10000+int(task['taskId'][3:])*10+i,
                        'url':'https://media.test/result.jpg','assetName':'fake'} for i in range(task['request']['parameters']['count'])]
                    partial=bool(os.getenv('YOYO_FAKE_PARTIAL'))
                    if partial:items=items[:1]
                    value={'task':{'taskId':task['taskId'],'status':'PARTIAL_SUCCESS' if partial else ('PROCESSING' if pending else 'SUCCESS'),'progress':99 if pending else 100,
                        'items':[{'itemId':'GI_1','status':'FAILED' if pending else 'SUCCESS','results':items,
                                  'errorCode':'RESULT_STORAGE_ERROR','errorMessage':'historical transient'}]}}
                else:
                    raise AssertionError(name)
                save()
                value={'content':[{'type':'text','text':json.dumps(value)}],'isError':False}
            return Response(json.dumps({'jsonrpc':'2.0','id':payload['id'],'result':value}).encode())
    urllib.request.build_opener=lambda *args:Opener()
