"""Read-only saved-model diagnostics: Blender -b model.blend -P this.py -- report.json."""
import json
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sources' / 'blender'))
from meshgate_blender.live import _mesh_quality

report = []
for obj in list(bpy.context.scene.objects):
    if obj.type != 'MESH':
        continue
    quality = _mesh_quality(obj)
    entry = {'name': obj.name, 'vertices': len(obj.data.vertices), 'quality': quality}
    # Export joins accessories, so inspect connected components separately.
    neighbors = [[] for _ in obj.data.vertices]
    for edge in obj.data.edges:
        a, b = edge.vertices
        neighbors[a].append(b)
        neighbors[b].append(a)
    unseen = set(range(len(neighbors)))
    components = []
    while unseen:
        seed = unseen.pop()
        group, stack = {seed}, [seed]
        while stack:
            for other in neighbors[stack.pop()]:
                if other in unseen:
                    unseen.remove(other)
                    group.add(other)
                    stack.append(other)
        components.append(group)
    entry['largest_components'] = []
    for group in sorted(components, key=len, reverse=True)[:8]:
        ids = sorted(group)
        mapping = {old: new for new, old in enumerate(ids)}
        mesh = bpy.data.meshes.new('diagnostic_component')
        mesh.from_pydata([obj.data.vertices[i].co for i in ids],
                         [tuple(mapping[i] for i in e.vertices) for e in obj.data.edges if e.vertices[0] in group],
                         [tuple(mapping[i] for i in p.vertices) for p in obj.data.polygons if p.vertices[0] in group])
        component = bpy.data.objects.new('diagnostic_component', mesh)
        component.matrix_world = obj.matrix_world.copy()
        entry['largest_components'].append({'vertices': len(ids), 'quality': _mesh_quality(component)})
        bpy.data.objects.remove(component)
        bpy.data.meshes.remove(mesh)
    report.append(entry)
output = Path(sys.argv[sys.argv.index('--') + 1])
output.write_text(json.dumps(report, indent=2))
print(json.dumps([{'name': row['name'], 'counts': row['quality']['counts'],
                   'component_count': row['quality']['component_count'],
                   'largest_component': row['largest_components'][0]} for row in report]))
