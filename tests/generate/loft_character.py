"""Check measured profiles, closed topology, colour bands and input rejection in real Blender."""
def build(mg):
    fur=mg.color('fur','#988781')
    cream=mg.color('cream','#dec8ab')
    outline=[(-1,-1),(1,-1),(1,1),(-1,1)]
    rings=[(0,0,0,.1,.08),(.02,0,.2,.15,.10),(0,0,.4,.08,.06)]
    for rows, contour, opts in [
        (rings[::-1],outline,{}),
        ([(0,0,0,0,.1),(0,0,.2,.1,.1)],outline,{}),
        (rings,outline[::-1],{}),
        (rings,outline,{'bands':[fur]}),
        (rings,outline,{'subdiv':4}),
        (rings,outline,{'support':-1}),
    ]:
        try:
            mg.loft(rows,contour,fur,**opts)
        except Exception:
            pass
        else:
            raise AssertionError('invalid profile was accepted')
    obj=mg.loft(rings,outline,fur,bands=[cream,fur,fur,fur])
    assert len(obj.data.vertices)==12 and len(obj.data.polygons)==10
    assert abs(max(v.co.x for v in obj.data.vertices)-.17)<1e-6
    def closed_positive(obj):
        edges={}
        volume=0
        for face in obj.data.polygons:
            ids=list(face.vertices)
            for a,b in zip(ids,ids[1:]+ids[:1]):
                key=tuple(sorted((a,b)))
                edges[key]=edges.get(key,0)+1
            origin=obj.data.vertices[ids[0]].co
            for i in range(1,len(ids)-1):
                volume+=origin.dot(obj.data.vertices[ids[i]].co.cross(obj.data.vertices[ids[i+1]].co))/6
        assert all(count==2 for count in edges.values())
        assert volume>0
    hit, normal=mg.surface_point(obj,(0,-1,.2),(0,1,0))
    assert abs(hit[1]+.1)<1e-5 and normal[1]<-.9
    try:
        mg.surface_point(obj,(1,-1,.2),(0,1,0))
    except Exception:
        pass
    else:
        raise AssertionError('missed ray must be rejected')
    closed_positive(obj)
    assert len(set(tuple(obj.data.uv_layers.active.data[p.loop_start].uv) for p in obj.data.polygons))==2
    other=mg.loft([(0,0,.35,.08,.06),(0,0,.55,.07,.05)],outline,fur,smooth=True,subdiv=1,support=.005)
    joined=mg.union([obj,other],fillet=.004,detail=.3,relax=True,surface="voxel")
    closed_positive(joined)
    mg.shade(joined,'smooth')
    assert joined.get('meshgate_shading')=='smooth'
    assert all(p.use_smooth for p in joined.data.polygons)
    mg.join('loft_character_check',[joined])
