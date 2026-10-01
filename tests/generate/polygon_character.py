"""Run with meshgate.py gen --code tests/generate/polygon_character.py --tiers pc --colors texture or vertex.
Checks explicit surface colours and validation before constructing geometry.
"""
def build(mg):
    fur=mg.color("fur","#887976")
    cream=mg.color("cream","#dec8ab")
    vertices=[(-.1,-.1,0),(.1,-.1,0),(.1,.1,0),(-.1,.1,0),
              (-.1,-.1,.2),(.1,-.1,.2),(.1,.1,.2),(-.1,.1,.2)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    for bad_faces, bad_colors in [([(0,1,8)],None),(faces,[cream]),([(0,0,1)],None), ([(0,1,2,3,2,1)],None)]:
        rejected=False
        try:
            mg.mesh(vertices,bad_faces,fur,face_colors=bad_colors)
        except Exception:
            rejected=True
        assert rejected
    obj=mg.mesh(vertices,faces,fur,face_colors=[fur,cream,fur,cream,fur,cream])
    assert len(obj.data.polygons)==6
    uv=obj.data.uv_layers.active.data
    cells=set(tuple(uv[p.loop_start].uv) for p in obj.data.polygons)
    assert len(cells)==2
    if obj.data.color_attributes.get("Col"):
        colors=obj.data.color_attributes["Col"].data
        assert len(set(tuple(colors[p.loop_start].color) for p in obj.data.polygons))==2
    surface=mg.mesh(vertices,[(0,1,5,4)],cream,name="front_surface")
    assert surface.data.polygons[0].normal.y < -.99
    mg.join("polygon_character_check",[obj,surface])
