"""The cat scout's full v15 base (built from zombie_cat_scout_smooth.py) reduced for a game and given its six
Appearance sliders as morphs; the path is relative to the MeshGate folder."""
def build(mg):
    base=mg.load_base("samples/bases/cat_scout_v15.blend", ratio=.09)
    # Keep the back shoulder strap clear of the chest after this candidate's collapse.
    roles=base.data.attributes.get("cat_cloth_role")
    for vertex in base.data.vertices:
        x,y,z=vertex.co
        if roles.data[vertex.index].value==4 and .065<x<.120 and -.030<y<.030 and .480<z<.520:
            weight=max(0,min(1,(x-.065)/.015,(.120-x)/.015,(y+.030)/.015,(.030-y)/.015,(z-.480)/.015,(.520-z)/.005))
            vertex.co.z+=.012*weight
    base.data.update()
    mg.morph("head_width", "Ширина головы", at=(0,0,.550), scale=(1.16,1,1), above=.565, blend=.035)
    mg.morph("head_depth", "Глубина головы", at=(0,0,.550), scale=(1,1.12,1), above=.565, blend=.035)
    mg.morph("body_width", "Ширина тела", at=(0,0,.390), scale=(1.12,1,1), above=.100, below=.560, blend=.040)
    mg.morph("leg_length", "Длина ног", at=(0,0,0), stretch=(.090,.290,.035))
    mg.morph("paw_size", "Размер стоп", at=(.090,-.035,.008), radius=.150, scale=(1.12,1.12,1.10), below=.085, blend=.040, mirror=True)
    mg.morph("hand_size", "Размер кистей", at=(.265,-.010,.285), radius=.105, scale=1.12, below=.355, blend=.020, mirror=True)
