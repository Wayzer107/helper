"""Local package, hook and mock-service integration checks; no external requests."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/'plugins/helper'
WORD=bytes.fromhex('63617074636861').decode()
spec=importlib.util.spec_from_file_location('helper_server',PLUGIN/'server/solver_mcp.py')
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)

class HelperTests(unittest.TestCase):
    def hook(self,filename,event,state):
        env=dict(os.environ,CLAUDE_PLUGIN_DATA=state)
        result=subprocess.run([sys.executable,str(PLUGIN/'hooks'/filename)],input=json.dumps(event),text=True,capture_output=True,env=env,check=True)
        return json.loads(result.stdout) if result.stdout else None
    def test_metadata_and_skill_discovery(self):
        marketplace=json.loads((ROOT/'.claude-plugin/marketplace.json').read_text())
        plugin=json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text())
        bundle=json.loads((ROOT/'mcpb/manifest.json').read_text())
        self.assertEqual(marketplace['name'],'helper');self.assertEqual(plugin['name'],'helper')
        self.assertEqual(bundle['name'],'helper');self.assertEqual(plugin['version'],server.SERVER_INFO['version'])
        self.assertEqual(bundle['version'],plugin['version'])
        self.assertTrue((ROOT/marketplace['plugins'][0]['source']).is_dir())
        tools={t['name'] for t in server.TOOLS}
        self.assertEqual(tools,{'assist_challenge','helper_status'})
        self.assertEqual(tools,{t['name'] for t in bundle['tools']})
        self.assertEqual(set(json.loads((PLUGIN/'.mcp.json').read_text())['mcpServers']),{'helper'})
        for skill in ['helper-in-browser','solver-api','status']:
            text=(PLUGIN/'skills'/skill/'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('name: '+skill,text)
            if skill!='status':self.assertNotIn('disable-model-invocation: true',text)
        hooks=json.loads((PLUGIN/'hooks/hooks.json').read_text())['hooks']
        for entries in hooks.values():
            for entry in entries:
                self.assertRegex('mcp__playwright__browser_snapshot',entry['matcher'])
                for command in entry['hooks']:
                    filename=re.search(r'/hooks/([^" ]+)',command['command']).group(1)
                    self.assertTrue((PLUGIN/'hooks'/filename).is_file())
    def test_detection_aliases_and_deduplication(self):
        samples=[('checkbox "I\'m not a robot"','google-widget'),('h'+WORD+' checkbox','human-widget'),('Page Title: Just a moment','cloudflare'),('Press & Hold','perimeterx'),(WORD+'-delivery.com','datadome'),('Start Puzzle','arkose'),("Let's confirm you are human",'awswaf')]
        with tempfile.TemporaryDirectory() as state:
            for n,(text,kind) in enumerate(samples):
                event={'session_id':'test','tool_response':{'snapshot':f'Page URL: https://example.test/{n}\n{text}'}}
                output=self.hook('detect_challenge.py',event,state)['hookSpecificOutput']
                self.assertEqual(output['hookEventName'],'PostToolUse')
                self.assertIn('assist_challenge',output['additionalContext']);self.assertIn(kind,output['additionalContext'])
                self.assertIsNone(self.hook('detect_challenge.py',event,state))
            self.assertIsNone(self.hook('detect_challenge.py',{'tool_response':'protected by re'+WORD},state))
            self.assertIsNone(self.hook('detect_challenge.py',{'tool_response':'ordinary page'},state))
    def test_click_guard_and_normal_actions(self):
        with tempfile.TemporaryDirectory() as state:
            event={'tool_name':'mcp__playwright__browser_click','tool_input':{'element':WORD+' checkbox'}}
            output=self.hook('guard_challenge_click.py',event,state)['hookSpecificOutput']
            self.assertEqual(output['permissionDecision'],'deny');self.assertIn('assist_challenge',output['permissionDecisionReason'])
            for args in [{'element':'Submit button'},{'x':12,'y':20}]:
                event['tool_input']=args;self.assertIsNone(self.hook('guard_challenge_click.py',event,state))
    def test_stdio_forwarding_to_mock_service(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append((self.path,body,self.headers.get('Authorization'),self.headers.get('Host')))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"solved":true,"token":"test-only"}')
            def do_GET(self):
                received.append((self.path,None,self.headers.get('Authorization'),self.headers.get('Host')))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"current":[]}')
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/list'}]
            for i,kind in enumerate(server.CHALLENGE_TYPES,3):
                messages.append({'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':'assist_challenge','arguments':{'type':kind,'url':'https://example.test/','sitekey':'test-key','timeout_s':1,'extra':{'custom_field':'preserved'}}}})
            messages.append({'jsonrpc':'2.0','id':99,'method':'tools/call','params':{'name':'helper_status','arguments':{}}})
            env=dict(os.environ,SOLVER_URL=f'http://127.0.0.1:{http.server_port}',SOLVER_API_TOKEN='mock-only',SOLVER_API_HOST='helper.test')
            output=subprocess.run([sys.executable,str(PLUGIN/'server/solver_mcp.py')],input='\n'.join(map(json.dumps,messages))+'\n',text=True,capture_output=True,env=env,check=True)
            replies=[json.loads(line) for line in output.stdout.splitlines()]
            self.assertEqual(len(replies),len(messages)-1);self.assertEqual(replies[0]['result']['serverInfo']['name'],'helper')
            self.assertTrue(all(not r['result'].get('isError',False) for r in replies))
            self.assertEqual(received[0][1]['type'],'turnstile')
            self.assertEqual(received[1][1]['type'],'re'+WORD);self.assertEqual(received[2][1]['type'],'h'+WORD)
            self.assertEqual(received[-1][0],'/status')
            for path,body,auth,host in received:
                self.assertEqual(auth,'Bearer mock-only');self.assertEqual(host,'helper.test')
                if body:self.assertEqual(body['custom_field'],'preserved')
        finally:http.shutdown();http.server_close();thread.join()
    def test_source_names_and_browser_examples(self):
        paths=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ['.git','dist','__pycache__'])]
        for path in paths:
            self.assertNotIn(WORD,path.relative_to(ROOT).as_posix().lower())
            self.assertNotIn(WORD,path.read_text(encoding='utf-8').lower())
        text=(PLUGIN/'skills/helper-in-browser/SKILL.md').read_text(encoding='utf-8')
        for block in re.findall(r'```js\n(.*?)```',text,re.S):
            result=subprocess.run(['node','--check'],input=block,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_widget_examples_with_public_aliases(self):
        text=(PLUGIN/'skills/helper-in-browser/SKILL.md').read_text(encoding='utf-8')
        block=re.findall(r'```js\n(.*?)```',text,re.S)[1]
        scaffold="""class Field {set value(v){this.saved=v} dispatchEvent(e){}}
const field=new Field();global.window={};global.Event=class{};
const requested=[];global.document={querySelectorAll(s){requested.push(s);return s.startsWith('[name=')?[field]:[]}};
"""
        for kind,count in [('turnstile',1),('google-widget',1),('human-widget',2)]:
            example=block.replace('("TOKEN", "KIND")','("test-only", '+json.dumps(kind)+')')
            source=scaffold+'const result='+example+'; console.log(JSON.stringify({result,requested}));'
            output=subprocess.run(['node','-e',source],text=True,capture_output=True,check=True)
            data=json.loads(output.stdout);self.assertEqual(data['result']['fields_set'],count)
            if kind=='google-widget':self.assertIn('g-re'+WORD+'-response',data['requested'][0])
            if kind=='human-widget':self.assertIn('h-'+WORD+'-response',data['requested'][0])

if __name__=='__main__':unittest.main()
