"""Build source without finalization and trace ear union quality; diagnostic only."""
import sys,runpy,json
from pathlib import Path
import bpy
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'sources'/'blender'))
from meshgate_blender import modeling
from meshgate_blender.live import _mesh_quality
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
class TraceComplete(Exception):
 pass
original=modeling.Kit.union
def union(self,parts,**kwargs):
 parts=list(parts)
 isear=any('ear_bowl' in p.name for p in parts)
 if isear:
  print('EAR_INPUTS',json.dumps([{'name':p.name,'quality':_mesh_quality(p)['counts']} for p in parts]),flush=True)
 result=original(self,parts,**kwargs)
 if isear:
  print('EAR_UNION',json.dumps(_mesh_quality(result)),flush=True)
  raise TraceComplete
 return result
modeling.Kit.union=union
kit=modeling.Kit('pc',name='debug',colors='vertex',finish='none')
try:
 runpy.run_path(str(root/'sources/generate/examples/zombie_cat_scout_smooth.py'))['build'](kit)
except TraceComplete:
 print('TRACE_FINISHED',flush=True)
