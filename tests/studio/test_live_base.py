"""Studio validates model ownership and keeps base revisions scoped to its library."""
import sys,tempfile
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'apps/studio'))
import server,mcp_server
with tempfile.TemporaryDirectory() as tmp:
 folder=Path(tmp)/'cat';folder.mkdir();(folder/'cat.blend').write_bytes(b'BLENDER')
 studio=server.Studio(Path(tmp),'test')
 for request in [{'name':'../other','action':'load'},{'name':'cat','action':'save'}]:
  try:studio.live_base(request)
  except ValueError:pass
  else:raise AssertionError('unsafe request accepted')
 def respond(req):
  if req['cmd']=='save_base':
   target=Path(req['path']);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'BLENDER')
  return {'ok':True}
 with patch.object(mcp_server,'ensure_blender'),patch.object(mcp_server,'_send',side_effect=respond) as send:
  studio.live_base({'name':'cat','action':'load'})
  studio.live_base({'name':'cat','action':'save'})
  target=Path(send.call_args.args[0]['path']);assert target.parent==folder/'bases'
  assert send.call_args.args[0]['cmd']=='save_base'
  import json,types
  state=json.loads((folder/'base.json').read_text())
  source=folder/state['code'];assert 'morphs=True' in source.read_text()
  restarted=server.Studio(Path(tmp),'new')
  restarted.live_base({'name':'cat','action':'load'})
  assert str(target) in send.call_args.args[0]['code']
  (folder/'cat.py').write_text('def build(mg):\n    pass\n')
  (folder/'gen.json').write_text(json.dumps({'name':'cat','engine':'kit','code':'cat.py','tiers':['pc']}))
  with patch.object(server,'Job',side_effect=lambda jid,cmd,name:types.SimpleNamespace(id=jid,cmd=cmd,name=name,code=0)):
   job=restarted.refine({'name':'cat'})
   selected=Path(job.cmd[job.cmd.index('--code')+1])
   assert str(target) in selected.read_text(), 'restart rebuild ignored saved geometry'
  restarted.jobs['busy']=types.SimpleNamespace(name='cat',code=None)
  for req in ({'name':'cat','action':'save'},{'name':'cat','action':'load'}):
   try:restarted.live_base(req)
   except ValueError:pass
   else:raise AssertionError('live base changed during build')
  (folder/'base.json').write_text(json.dumps({'path':'../escape.blend','code':state['code']}))
  try:server.Studio(Path(tmp),'test').live_base({'name':'cat','action':'load'})
  except ValueError:pass
  else:raise AssertionError('unsafe saved source accepted')
  (folder/'base.json').write_text(json.dumps(state))
 (folder/'reference-review-v3.png').write_bytes(b'image')
 assert studio.live_base({'name':'cat','action':'compare'})['image']=='reference-review-v3.png'
print('PASS: model ownership, revision path and report lookup.')
