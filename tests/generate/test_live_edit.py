"""Real Blender/socket/MCP check. Run: python3 tests/generate/test_live_edit.py.
An isolated headless server is used; the user's Blender scene and connection stay untouched.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sources' / 'generate'))
import mcp_server as mcp

OUT = ROOT / 'out' / 'tests' / 'kit' / 'live_edit'
OUT.mkdir(parents=True, exist_ok=True)
CODE = '''def build(mg):
    fur=mg.color("fur","#988781")
    olive=mg.color("olive","#808364")
    head=mg.part("sphere",fur,loc=(0,0,.4),scale=(.4,.3,.35),segments=16,ring_count=8,exact=True)
    head.name="head"
    twin=mg.instance(head,at=(.6,0,.4))
    twin.name="head_copy"
    torso=mg.part("cube",olive,loc=(0,0,.15),scale=(.2,.16,.26),bevel=.01)
    torso.name="torso"
'''


def call(name, **args):
    return json.loads(mcp.call(name, args)[0]['text'])


def positions(rep):
    return {v['id']: v['position'] for v in rep['vertices']}


with tempfile.TemporaryDirectory(prefix='meshgate-edit-check-') as config:
    os.environ['MESHGATE_CONFIG_DIR'] = config
    try:
        built=call('blender_build',code=CODE)
        assert built['ok'], built
        head=call('blender_mesh',part='head',limit=500)
        torso=call('blender_mesh',part='torso',limit=500)
        twin=call('blender_mesh',part='head_copy',limit=500)
        original=positions(head)
        # Build-line labels still work; an instanced line is ambiguous and needs an exact name.
        by_line=call('blender_mesh',part='line 8',limit=500)
        assert by_line['ok'] and by_line['part']=='torso', by_line
        assert not call('blender_mesh',part='line 4')['ok']
        middle=(min(p[0] for p in original.values())+max(p[0] for p in original.values()))/2
        region={'min':[middle,-10,-10],'max':[10,10,10]}
        selection=call('blender_mesh',part='head',region=region,limit=500)
        assert selection.get("ok"), selection
        ids=set(positions(selection))
        assert 0<len(ids)<len(original)
        rendered=mcp._send({'cmd':'render','px':800,'samples':8})
        assert rendered['ok'], rendered
        shutil.copyfile(rendered['image'],OUT/'before.png')
        moved=call('blender_edit',part='head',revision=head['revision'],operation='move',region=region,delta=[.03,0,0])
        assert moved['ok'] and moved['changed']==len(ids), moved
        after=call('blender_mesh',part='head',limit=500)
        for i, point in positions(after).items():
            expected=original[i][0]+(.03 if i in ids else 0)
            assert abs(point[0]-expected)<1e-6
            assert all(abs(point[a]-original[i][a])<1e-6 for a in (1,2))
        assert positions(call('blender_mesh',part='torso',limit=500))==positions(torso)
        assert positions(call('blender_mesh',part='head_copy',limit=500))==positions(twin)
        # Invalid edits and stale IDs must preserve both mesh and last undo snapshot.
        for args in [
            {'revision':head['revision'],'operation':'move','delta':[1,0,0]},
            {'revision':after['revision'],'operation':'scale','factors':[0,1,1]},
            {'revision':after['revision'],'operation':'move','delta':[float('nan'),0,0]},
            {'revision':after['revision'],'operation':'move','vertices':[999999],'delta':[1,0,0]},
            {'revision':after['revision'],'operation':'move','region':{'min':[2,2,2],'max':[3,3,3]},'delta':[1,0,0]},
        ]:
            rejected=call('blender_edit',part='head',**args)
            assert not rejected['ok'], rejected
            assert positions(call('blender_mesh',part='head',limit=500))==positions(after)
        undo=call('blender_edit_undo')
        assert undo['ok'] and undo['revision']>after['revision'], undo
        restored=call('blender_mesh',part='head',limit=500)
        assert positions(restored)==original
        assert not call('blender_edit_undo')['ok']
        scaled=call('blender_edit',part='head',revision=restored['revision'],operation='scale',factors=[1.2,1,1],pivot=[0,0,.4])
        assert scaled['ok'], scaled
        scaled_mesh=call('blender_mesh',part='head',limit=500)
        assert scaled_mesh['vertex_count']==head['vertex_count'] and scaled_mesh['face_count']==head['face_count']
        for i,point in positions(scaled_mesh).items():
            assert abs(point[0]-original[i][0]*1.2)<1e-6
        softened=call('blender_edit',part='head',revision=scaled_mesh['revision'],operation='smooth',
                     vertices=sorted(ids),strength=.2,iterations=2)
        assert softened['ok'], softened
        soft_mesh=call('blender_mesh',part='head',limit=500)
        for i,p in positions(soft_mesh).items():
            if i not in ids:
                assert p==positions(scaled_mesh)[i]
        assert positions(call('blender_mesh',part='head_copy',limit=500))==positions(twin)
        page=call('blender_mesh',part='head',limit=10)
        assert len(page['vertices'])==10 and page['next_offset']==10
        rendered=mcp._send({'cmd':'render','px':800,'samples':8})
        assert rendered['ok'], rendered
        shutil.copyfile(rendered['image'],OUT/'after.png')
        topology_code='def build(mg):\n    o=mg.part("cube",mg.color("test","#988781"),scale=(.2,.2,.2),exact=True)\n    o.name="Topology"'
        assert call('blender_build',code=topology_code)['ok']
        mesh=call('blender_mesh',part='line 2')
        assert mesh['ok'],mesh
        face=max(mesh['faces'],key=lambda f:f['normal'][2])['id']
        inset=call('blender_edit',part='line 2',revision=mesh['revision'],operation='inset',faces=[face],thickness=.02)
        assert inset['ok'],inset
        extruded=call('blender_edit',part='line 2',revision=inset['revision'],operation='extrude',faces=inset['faces'],delta=[0,0,.03])
        assert extruded['ok'] and extruded['face_count']>inset['face_count'],extruded
        assert call('blender_edit_undo')['ok']
        inspected=call('blender_mesh',part='line 2')
        subdivided=call('blender_edit',part='line 2',revision=inspected['revision'],operation='subdivide',faces=[0],cuts=1)
        assert subdivided['ok'],subdivided
        symmetric=call('blender_edit',part='line 2',revision=subdivided['revision'],operation='symmetrize',keep='+x',plane=0)
        assert symmetric['ok'],symmetric
        assert call('blender_edit_undo')['ok']
        # A rebuild invalidates the last local edit's undo slot.
        assert call('blender_build',code=CODE)['ok']
        assert not call('blender_edit_undo')['ok']
        assert not call('blender_edit',part='head',revision=soft_mesh['revision'],operation='move',delta=[1,0,0])['ok']
        (OUT/'result.json').write_text(json.dumps({'ok':True,'selected_vertices':len(ids),
            'checks':['line labels','world-space region','move','scale','smooth','unselected geometry unchanged',
                      'shared instance unchanged','invalid edits atomic','stale revision rejected','undo','pagination','rebuild resets undo']},indent=2))
        print('Live edit checks passed: real Blender, socket transport and MCP; previews in '+str(OUT))
    finally:
        proc=mcp._headless['proc']
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
                proc.wait()
