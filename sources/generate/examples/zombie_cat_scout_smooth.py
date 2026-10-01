"""Cat scout: designed silhouette and broad polygon planes, with markings in the same surface.
Smooth variant: build with stylized, finish none, --pbr --texture 2k. Coordinates are metres, front is -Y, height about one metre.
"""
import math
from mathutils import Vector


def build(mg):
    fur = mg.color("fur_grey", "#988781", rough=0.9)
    cream = mg.color("fur_cream", "#dec8ab", rough=0.9)
    stripe = mg.color("fur_stripe", "#756661", rough=0.9)
    pink = mg.color("ear_pink", "#b96765", rough=0.9)
    olive = mg.tile("shirt_olive", "fabric", "#737859", size=.08, rough=.95)
    faded = mg.color("shirt_faded", "#999c7c", rough=0.95)
    brown = mg.tile("shorts_brown", "fabric", "#604b40", size=.08, rough=.94)
    leather = mg.tile("leather", "leather", "#926747", size=.10, rough=.84)
    dark = mg.color("socket", "#4e413f", rough=0.95)
    red = mg.tile("bandana", "fabric", "#a74745", size=.065, rough=.94)
    nose_pink = mg.color("nose_pink", "#a74745", rough=.8)
    gold = mg.color("brass", "#bea16d", rough=0.75)
    lime = mg.color("eye_lime", "#d4ef53", rough=0.7, glow=0.18)
    milk = mg.color("eye_milky", "#c4bdad", rough=0.7)
    parts = []
    clothing=[]
    body_skin = []
    head_skin = []
    limb_skin = []
    ear_inner=[]
    ear_shells=[]
    def near_triangle(point,triangle):
        a,b,c=triangle
        ab,ac=b-a,c-a
        normal=ab.cross(ac).normalized()
        distance=(point-a).dot(normal)
        if abs(distance)>.003:
            return False
        delta=point-normal*distance-a
        aa,bb,cc=ab.dot(ab),ab.dot(ac),ac.dot(ac)
        denom=aa*cc-bb*bb
        if abs(denom)<1e-12:
            return False
        u=(cc*delta.dot(ab)-bb*delta.dot(ac))/denom
        v=(aa*delta.dot(ac)-bb*delta.dot(ab))/denom
        return u>=0 and v>=0 and u+v<=1
    socket_outlines=[]
    ear_yaw=mg.param("ear_yaw",22,0,65,label="Ear outward angle")
    ear_pitch=mg.param("ear_pitch",10,0,20,label="Ear forward tilt")
    cheek_width=mg.param("cheek_width",1.0,.88,1.12,label="Cheek width")
    head_depth=mg.param("head_depth",.95,.85,1.15,label="Head depth")

    # A ring loft gives a continuous silhouette with deliberately chosen large planes.
    def loft(name, rings, outline, color, bands=None):
        if name=="head":
            rings=[(x,y,z,w*cheek_width,d*head_depth) for x,y,z,w,d in rings]
            rings=[tuple(a[j]+(b[j]-a[j])*k/4 for j in range(5)) for a,b in zip(rings,rings[1:]) for k in range(4)]+[rings[-1]]
            outline=[tuple(a[j]+(b[j]-a[j])*k/6 for j in range(2)) for a,b in zip(outline,outline[1:]+outline[:1]) for k in range(6)]
            bands=[color]*len(outline)
        obj = mg.loft(rings, outline, color, name=name, bands=bands, smooth=True,
                      subdiv=0 if name in {"head", "muzzle"} else 1, support=0 if name in {"head", "muzzle"} else .006)
        parts.append(obj)
        return obj

    octagon = [(-.7,-1),(.7,-1),(1,-.55),(1,.55),(.7,1),(-.7,1),(-1,.55),(-1,-.55)]

    def panel(name, outline, y, color, depth=.004):
        obj = mg.extrude(outline, depth, color, loc=(0,y,0), bevel=min(.003,depth*.30), smooth=True)
        parts.append(obj)
        return obj

    def block(color, loc, size, bevel=.006, rot=(0,0,0)):
        obj = mg.part("cube", color, loc=loc, scale=size, bevel=bevel, bevel_segments=3, rot=rot, smooth=True)
        parts.append(obj)
        return obj

    def limb(a, b, radii, color, sides=8):
        obj = mg.tube([a,b], 0, color, radii=radii, sides=max(16,sides), exact=True, smooth=True)
        parts.append(obj)
        return obj

    def disk(color, center, size):
        obj = mg.part("cyl", color, loc=center, scale=(size[0],size[1],.005),
                      rot=(math.pi/2,0,0), vertices=48, exact=True, smooth=True)
        parts.append(obj)
        return obj

    def connected(obj):
        links=[set() for v in obj.data.vertices]
        for edge in obj.data.edges:
            a,b=edge.vertices
            links[a].add(b)
            links[b].add(a)
        reached=set()
        todo=[0]
        while todo:
            i=todo.pop()
            if i not in reached:
                reached.add(i)
                todo.extend(links[i]-reached)
        if len(reached)!=len(links):
            sizes=[len(reached)]
            remaining=set(range(len(links)))-reached
            while remaining:
                group=set()
                pending=[min(remaining)]
                while pending:
                    i=pending.pop()
                    if i not in group:
                        group.add(i)
                        pending.extend(links[i]-group)
                sizes.append(len(group))
                remaining-=group
            raise ValueError("disconnected skin components: "+str(sorted(sizes,reverse=True)))

    with mg.section("legs"):
        for s in (-1,1):
            x = s*.09
            leg=loft("leg", [(x,.008,.050,.034,.037),(x,.008,.085,.033,.035),
                              (x,.005,.125,.042,.039),(x,0,.170,.047,.044),(x,0,.20,.048,.048)],
                 octagon, cream)
            # Bands replace colour on the surface instead of raised bracelet geometry.
            mg.paint(leg,stripe,above=.108,below=.124)
            # Broad heel and instep, with a flat sole rather than a rounded shoe.
            paw=mg.loft_path([(x,.038,.034,.036,.030),(x,.005,.036,.045,.034),
                              (x,-.035,.038,.057,.035),(x,-.070,.029,.063,.026)],
                             cream,axis=(1,0,0),outline=octagon,smooth=True,name="paw_instep")
            toes=[]
            for k in (-1,0,1):
                tx=x+k*.040
                ty=-.110-(.009 if k==0 else 0)
                toe=mg.loft_path([(tx,-.057,.028,.026,.026),
                                  (tx,-.083,.027,.025,.025),
                                  (tx,ty,.022,.021,.021)],cream,axis=(1,0,0),
                                 outline=octagon,smooth=True,name="paw_digit")
                toes.append(toe)
                claw=mg.loft_path([(tx,ty+.010,.023,.017,.018),
                                   (tx,ty-.005,.019,.015,.013),
                                   (tx,ty-.025,.010,.006,.003)],brown,axis=(1,0,0),
                                  outline=octagon,smooth=False,name="toe_tip")
                parts.append(claw)
            parts=[p for p in parts if p is not leg]
            foot=mg.union([leg,paw]+toes,fillet=.002,detail=.16,relax=False,surface="voxel")
            connected(foot)
            # Keep the contact surface planar; toe tops retain their broad bevelled planes.
            for vertex in foot.data.vertices:
                point=foot.matrix_world@vertex.co
                if point.z<.008:
                    point.z=.008
                    vertex.co=foot.matrix_world.inverted()@point
            for edge in foot.data.edges:
                edge.use_edge_sharp=False
            for polygon in foot.data.polygons:
                polygon.use_smooth=True
            mg.paint(foot,cream)
            mg.paint(foot,stripe,above=.108,below=.124)
            parts.append(foot)
            limb_skin.append(foot)
            thigh=limb((x,0,.180),(x,0,.335),[.044,.046],cream)
            limb_skin.append(thigh)

    with mg.section("shorts"):
        # Tailored volume: fuller seat/thighs, a narrower waist and a ragged 3D hem.
        # The tear silhouette belongs to the trouser mesh on every side, not a front card.
        waist=loft("waist", [(0,0,.265,.140,.085),(0,0,.305,.132,.084),
                              (0,0,.330,.128,.081)],octagon,brown)
        trousers=[]
        count=16
        hem_offsets=[.002,-.010,.006,-.004,-.013,.008,-.004,.003,
                     -.007,.005,-.012,.003,-.005,.009,-.011,.001]
        for s in (-1,1):
            x=s*.083
            vertices=[]
            rings=[(.168,.071,.082),(.195,.073,.087),
                   (.239,.073,.087),(.277,.065,.082)]
            for row,(z,rx,ry) in enumerate(rings):
                for i in range(count):
                    angle=2*math.pi*i/count
                    co,si=math.cos(angle),math.sin(angle)
                    px=math.copysign(abs(co)**.64,co)
                    py=math.copysign(abs(si)**.64,si)
                    fold=.003*math.sin(angle*2)*math.sin(math.pi*row/(len(rings)-1))
                    vertices.append((x+(rx+fold)*px,(ry+fold)*py,z+(hem_offsets[i] if row==0 else 0)))
            faces=[tuple(reversed(range(count)))]
            for row in range(len(rings)-1):
                for i in range(count):
                    a=row*count+i;b=row*count+(i+1)%count
                    faces.append((a,b,b+count,a+count))
            faces.append(tuple((len(rings)-1)*count+i for i in range(count)))
            trouser=mg.mesh(vertices,faces,brown,name="tailored_trouser",smooth=False)
            trousers.append(trouser)
        crotch=loft("shorts_bridge", [(0,0,.201,.036,.075),
                                     (0,0,.241,.075,.083),
                                     (0,0,.280,.110,.085)],octagon,brown)
        garment=[waist,crotch]+trousers
        parts=[part for part in parts if part not in garment]
        shorts=mg.union(garment,surface="boolean")
        connected(shorts)
        parts.append(shorts)
        clothing.append((shorts,2))
        # A continuous belt follows the waist around the sides and back.
        belt_vertices=[]
        for rx,ry,z in ((.137,.089,.293),(.135,.088,.315),
                         (.129,.080,.293),(.127,.079,.315)):
            for i in range(count):
                angle=2*math.pi*i/count
                co,si=math.cos(angle),math.sin(angle)
                belt_vertices.append((rx*math.copysign(abs(co)**.64,co),
                                      ry*math.copysign(abs(si)**.64,si),z))
        belt_faces=[]
        for i in range(count):
            j=(i+1)%count
            belt_faces.extend([(i,j,j+count,i+count),
                               (i+2*count,i+3*count,j+3*count,j+2*count),
                               (i,i+2*count,j+2*count,j),
                               (i+count,j+count,j+3*count,i+3*count)])
        parts.append(mg.mesh(belt_vertices,belt_faces,dark,name="waist_belt",smooth=False))
        block(gold,(0,-.094,.304),(.045,.009,.031),bevel=.002)
        block(brown,(0,-.100,.304),(.025,.004,.016),bevel=.001)
        for s in (-1,1):
            # Softly bevelled pouches sit partly inside the outer thigh surface.
            block(leather,(s*.148,-.011,.252),(.026,.065,.059),bevel=.005)
            block(brown,(s*.151,-.011,.276),(.028,.068,.012),bevel=.002)
            cx=s*.083
            pocket=panel("front_pocket",[(cx-.027,.265),(cx+.025,.265),
                                          (cx+.023,.231),(cx-.022,.227)],
                         -.086,brown,.009)
            mg.paint(pocket,leather,at=(cx,-.092,.250),radius=.032,facing=(0,-1,0))
        mg.paint(shorts,leather,at=(.112,-.087,.209),radius=.038,facing=(0,-1,0))

    with mg.section("torso"):
        core=mg.part("cyl",cream,loc=(0,0,.355),scale=(.226,.108,.300),
                     vertices=32,exact=True,smooth=True,bevel=.010)
        limb_skin.append(core)
        chest=loft("chest",[(0,0,.31,.113,.070),(0,0,.43,.121,.073),(0,0,.505,.130,.067)],octagon,cream)
        body_skin.append(chest)
        # Thick curved front leaves wrap around the ribs, with an open belly and torn hem.
        fronts=[]
        for side in (-1,1):
            rows=[(.294,.143,.095,.035),(.325,.146,.099,.044),
                  (.375,.149,.100,.048),(.410,.151,.101,.059),
                  (.459,.156,.095,.041),(.497,.144,.083,.075)]
            columns=9
            verts=[]
            for inside in (False,True):
                for row,(z,rx,ry,opening) in enumerate(rows):
                    inner_angle=-math.acos(opening/rx)
                    for col in range(columns):
                        t=col/(columns-1)
                        angle=inner_angle+(-.15-inner_angle)*t
                        hem=[.004,.011,-.018,.007,-.015,.009,-.009,.005,0][col] if row==0 else 0
                        # A broad soft fold beside the opening; the sides remain fitted to the back.
                        fold=.006*math.sin(math.pi*t)*math.sin(math.pi*row/(len(rows)-1))
                        thickness=.008 if inside else 0
                        verts.append((side*(rx-thickness)*math.cos(angle),
                                      (ry-thickness)*math.sin(angle)-fold,z+hem))
            faces=[]
            n=len(rows)*columns
            for row in range(len(rows)-1):
                for col in range(columns-1):
                    a=row*columns+col;b=a+1;c=b+columns;d=a+columns
                    faces.extend([(a,b,c,d),(a+n,d+n,c+n,b+n)])
            for row in (0,len(rows)-1):
                for col in range(columns-1):
                    a=row*columns+col;b=a+1
                    faces.append((a,a+n,b+n,b) if row==0 else (a,b,b+n,a+n))
            for row in range(len(rows)-1):
                for col in (0,columns-1):
                    a=row*columns+col;b=a+columns
                    faces.append((a,b,b+n,a+n) if col==0 else (a,a+n,b+n,b))
            if side<0:
                faces=[tuple(reversed(face)) for face in faces]
            jacket=mg.mesh(verts,faces,olive,name="jacket_front",smooth=True)
            fronts.append(jacket)
            mg.paint(jacket,faded,at=(side*.101,-.077,.375),radius=.025,facing=(0,-1,0))
            # Repairs are colour on the fitted fabric, so they cannot float in front of it.
            for x,z in ((.110,.343),(.128,.410)):
                y=-.100*math.sqrt(1-(x/.151)**2)
                mg.paint(jacket,leather,at=(side*x,y,z),radius=.012,facing=(0,-1,0))
        # A continuous curved back and side shell follows the torso instead of a box panel.
        coat_vertices=[]
        coat_rows=[(.295,.143,.095),(.325,.146,.099),(.410,.151,.101),
                   (.470,.157,.094),(.497,.144,.083)]
        count=15
        for inside in (False,True):
            for row,(z,rx,ry) in enumerate(coat_rows):
                for i in range(count):
                    angle=-.20+(math.pi+.40)*i/(count-1)
                    hem=(.009 if i%3==1 else -.005) if row==0 else 0
                    coat_vertices.append(((rx-(.009 if inside else 0))*math.cos(angle),
                                          (ry-(.009 if inside else 0))*math.sin(angle),z+hem))
        coat_faces=[]
        offset=len(coat_rows)*count
        for row in range(len(coat_rows)-1):
            for i in range(count-1):
                a=row*count+i;b=a+1;c=a+count+1;d=a+count
                coat_faces.extend([(a,b,c,d),(a+offset,d+offset,c+offset,b+offset)])
        for row in (0,len(coat_rows)-1):
            for i in range(count-1):
                a=row*count+i;b=a+1
                coat_faces.append((a,a+offset,b+offset,b) if row==0 else (a,b,b+offset,a+offset))
        for row in range(len(coat_rows)-1):
            for i in (0,count-1):
                a=row*count+i;b=a+count
                coat_faces.append((a,b,b+offset,a+offset) if i==0 else (a,a+offset,b+offset,b))
        back=mg.mesh(coat_vertices,coat_faces,olive,name="jacket_back_sides",smooth=True)
        parts.append(back)
        mg.paint(back,faded,at=(.109,.070,.429),radius=.044)
        mg.paint(back,dark,at=(-.079,.080,.325),radius=.020)
        # The overlaps at the flanks become one closed garment, not three detached boards.
        parts.remove(back)
        jacket=mg.union(fronts+[back],surface="boolean")
        connected(jacket)
        parts.append(jacket)
        clothing.append((jacket,1))
        for s in (-1,1):
            strap_rows=[]
            for z in (.338,.375,.412,.448,.477,.492):
                point,normal=mg.surface_point(jacket,(s*.09,-1,z),(0,1,0))
                point=Vector(point)+Vector(normal)*.002
                strap_rows.append((*point,.0165,.0045))
            # Continue the same strap across the shoulder and down onto the back shell.
            strap_rows.extend([(s*.09,-.023,.513,.0165,.0045),
                               (s*.09,.023,.513,.0165,.0045)])
            for z in (.492,.477,.448,.412):
                point,normal=mg.surface_point(jacket,(s*.09,1,z),(0,-1,0))
                point=Vector(point)+Vector(normal)*.002
                strap_rows.append((*point,.0165,.0045))
            strap=mg.loft_path(strap_rows,leather,axis=(1,s*.60,0),outline=octagon,
                               smooth=True,name="fitted_backpack_strap")
            parts.append(strap)
            clothing.append((strap,4))
            point,normal=mg.surface_point(jacket,(s*.09,-1,.448),(0,1,0))
            normal=Vector(normal)
            angle=math.atan2(normal.x,-normal.y)
            buckle=Vector(point)+normal*.009
            inset=Vector(point)+normal*.013
            block(gold,tuple(buckle),(.037,.006,.029),.002,rot=(0,0,angle))
            block(leather,tuple(inset),(.023,.003,.017),0,rot=(0,0,angle))

    with mg.section("arms"):
        for s in (-1,1):
            sh=(s*.124,0,.478)
            el=(s*.214,-.005,.388)
            wrist=(s*.282,-.009,.318)
            hand=(s*.305,-.013,.293)
            sleeve=mg.loft_path([(*sh,.068,.061),
                                 (s*.167,0,.444,.066,.059),
                                 (s*.208,-.003,.402,.055,.050)],olive,
                                axis=(0,-1,0),sides=8,smooth=True,subdiv=0,cap=False,name="sleeve")
            mg.modify(sleeve,"solidify",thickness=.004,offset=1)
            clothing.append((sleeve,1))
            parts.append(sleeve)
            # Real asymmetric tears in the garment, with skin behind the opening.
            tear=mg.part("cube",olive,loc=(s*.199,-.043,.409),
                         scale=(.035,.035,.045),rot=(0,s*.32,.12),exact=True)
            mg.cut(sleeve,tear)
            mg.paint(sleeve,faded,at=(s*.170,-.051,.442),radius=.025,facing=(0,-1,0))
            upper_arm=limb(sh,el,[.038,.036],cream)
            limb_skin.append(upper_arm)
            axis=(Vector(wrist)-Vector(el)).normalized()
            width=Vector((0,-1,0)).cross(axis).normalized()
            profiles=[(-.10,.034,.030),(0,.037,.032),(.25,.042,.033),
                      (.55,.036,.028),(.86,.026,.021),(1.12,.027,.021)]
            sections=[(*Vector(el).lerp(Vector(wrist),t),rx,ry) for t,rx,ry in profiles]
            forearm=mg.loft_path(sections,cream,axis=tuple(width),sides=12,smooth=True)
            parts.append(forearm)
            # The wrap follows the forearm profile, without a rigid round cuff.
            if s == -1:
                wrap_sections=[(*Vector(el).lerp(Vector(wrist),t),rx,ry)
                               for t,rx,ry in ((.48,.0475,.0395),(.56,.0455,.038),(.63,.043,.036))]
                wrap=mg.loft_path(wrap_sections,red,axis=tuple(width),sides=12,
                                  smooth=True,cap=False,name="arm_wrap")
                mg.modify(wrap,"solidify",thickness=.003,offset=1)
                parts.append(wrap)
                clothing.append((wrap,3))
            forward=Vector((s*.025,0,-.03)).normalized()
            spread=Vector((0,-1,0)).cross(forward).normalized()
            # Flattened palm and three tapered digit pads share one skin volume.
            palm=mg.loft_path([(*Vector(wrist),.027,.022),
                               (*Vector(hand),.043,.025),
                               (*Vector(hand)+forward*.012,.037,.021)],cream,
                              axis=tuple(spread),sides=10,smooth=True,name="palm")
            fingers=[]
            for k in (-1,0,1):
                root=Vector(hand)+spread*(k*.029)+forward*.008
                reach=.053 if k==0 else .041
                middle=root+forward*(reach*.50)+spread*(k*.003)
                tip=root+forward*reach+spread*(k*.008)
                finger=mg.loft_path([(*root,.021,.022),
                                     (*middle,.018,.019),
                                     (*tip,.013,.015)],cream,axis=tuple(spread),
                                    sides=10,smooth=True,name="finger_pad")
                fingers.append(finger)
                claw=mg.loft_path([(*tip-forward*.011,.014,.016),
                                   (*tip+forward*.006,.012,.012),
                                   (*tip+forward*.019,.005,.003)],brown,
                                  axis=tuple(spread),outline=octagon,smooth=False,name="finger_tip")
                parts.append(claw)
            parts=[p for p in parts if p is not forearm]
            arm=mg.union([forearm,palm]+fingers,fillet=.002,detail=.16,relax=False,surface="voxel")
            connected(arm)
            for edge in arm.data.edges:
                edge.use_edge_sharp=False
            for polygon in arm.data.polygons:
                polygon.use_smooth=True
            mg.paint(arm,cream)
            parts.append(arm)
            limb_skin.append(arm)

    with mg.section("neck"):
        neck=mg.part("cyl",cream,loc=(0,0,.526),scale=(.120,.106,.128),smooth=True,
                     vertices=32,exact=True,bevel=.008)
        parts.append(neck)
        body_skin.append(neck)
        # A softly folded thin wrap, with an off-centre knot and unequal tails.
        collar_vertices=[]
        count=48
        for row,z in enumerate((.508,.520,.532)):
            for i in range(count):
                angle=2*math.pi*i/count
                wave=math.sin(3*angle+.45)*.0025+math.sin(5*angle)*.0012
                collar_vertices.append((math.cos(angle)*(.098-.003*row+wave),
                                        math.sin(angle)*(.090-.0035*row+wave),z+wave*(.3 if row==0 else .6 if row==1 else 1)))
        collar_faces=[(row*count+i,row*count+(i+1)%count,(row+1)*count+(i+1)%count,(row+1)*count+i)
                      for row in range(2) for i in range(count)]
        collar=mg.mesh(collar_vertices,collar_faces,red,name="scarf_wrap",smooth=True)
        mg.modify(collar,"solidify",thickness=.003,offset=1)
        parts.append(collar);clothing.append((collar,3))
        scarf_vertices=[];rows=8;columns=12
        for row in range(rows):
            t=row/rows
            left=-.097*(1-t)-.019*t
            right=.083*(1-t)-.019*t
            for column in range(columns+1):
                u=column/columns
                x=left+(right-left)*u
                y=-.107-.026*math.sin(math.pi*t)-.012*math.sin(3*math.pi*u+.8*t)*math.sin(math.pi*t)
                z=.530-.064*t+.004*math.sin(math.pi*u)*math.sin(math.pi*t)
                scarf_vertices.append((x,y,z))
        tip=len(scarf_vertices);scarf_vertices.append((-.019,-.119,.466))
        scarf_faces=[(row*(columns+1)+i,row*(columns+1)+i+1,(row+1)*(columns+1)+i+1,(row+1)*(columns+1)+i)
                     for row in range(rows-1) for i in range(columns)]
        scarf_faces.extend(((rows-1)*(columns+1)+i,(rows-1)*(columns+1)+i+1,tip) for i in range(columns))
        scarf=mg.mesh(scarf_vertices,scarf_faces,red,name="scarf_drape",smooth=True)
        mg.modify(scarf,"solidify",thickness=.003,offset=1)
        parts.append(scarf);clothing.append((scarf,3))
        knot=mg.part("sphere",red,loc=(-.077,-.114,.530),scale=(.030,.016,.022),segments=20,ring_count=12,exact=True,smooth=True)
        parts.append(knot);clothing.append((knot,3))
        for path in [[(-.088,-.112,.526),(-.113,-.121,.509),(-.129,-.116,.481)],
                     [(-.081,-.121,.527),(-.101,-.135,.509),(-.116,-.128,.500)]]:
            tail=mg.loft_path([(*point,.002,.010) for point in path],red,axis=(0,-1,0),sides=8,
                              smooth=True,name="scarf_tail")
            parts.append(tail);clothing.append((tail,3))

    for obj in parts:
        inverse=obj.matrix_world.inverted()
        for vertex in obj.data.vertices:
            point=obj.matrix_world@vertex.co
            if .160<point.z<.525 and abs(point.x)>.160:
                point.x=math.copysign(.160+(abs(point.x)-.160)*.70,point.x)
                vertex.co=inverse@point
        obj.data.update()

    hz=.706
    # Explicit broad front planes and diagonal cheek planes; preserve them through exact union.
    head_outline=[(-.72,-1),(.72,-1),(.96,-.65),(1,-.10),(.90,.55),(.48,.98),(-.48,.98),(-.90,.55),(-1,-.10),(-.96,-.65)]
    with mg.section("head",anchor=(0,0,.526)):
        cols=[fur]*len(head_outline)
        head=loft("head",[(0,.005,.544,.105,.080),(0,.003,.563,.132,.098),
                          (0,.002,.593,.153,.110),(0,.006,.624,.183,.120),(0,.011,.641,.208,.123),
                          (0,.015,.656,.195,.126),(0,.018,.722,.184,.128),
                          (0,.019,.784,.164,.111),(0,.012,.823,.127,.086),
                          (0,.009,.848,.080,.060),(0,.009,.858,.035,.032)],head_outline,fur,cols)
        head_skin.append(head)
        for polygon in head.data.polygons:
            polygon.use_smooth=False
        neck_lo,neck_hi=mg.bounds(neck)
        head_lo,head_hi=mg.bounds(head)
        chest_lo,chest_hi=mg.bounds(chest)
        assert neck_hi[2]>head_lo[2]+.010 and neck_lo[2]<chest_hi[2]-.010, "neck must overlap head and torso"
        # One continuous, shallow muzzle wedge; no separate spherical cheeks.
        lo,hi=mg.bounds(head)
        face=lo[1]
        muzzle=loft("muzzle",[(0,-.085,.566,.048,.022),(0,-.095,.580,.080,.027),
                             (0,-.102,.601,.106,.028),(0,-.098,.623,.115,.025),
                             (0,-.085,.642,.095,.018)],octagon,cream)
        # Exact union below preserves the designed muzzle planes after organic skin smoothing.
        for polygon in muzzle.data.polygons:
            polygon.use_smooth=False
        muzzle_front=-.136
        for s in (-1,1):
            x=s*.095
            # Dark socket colour belongs to the skin texture, not a plate over the eye.
            # Socket rim is coloured on the final skin after exact union.
            # An irregular six-sided opening, with a rounder eyeball seated behind its rim.
            opening=[(x+s*dx*.84,z+.025) for dx,z in [(-.061,.632),(.047,.631),(.065,.651),
                     (.060,.746),(-.048,.759),(-.063,.733)]]
            if s < 0:
                opening.reverse()
            socket_outlines.append(opening)
            cutter=mg.extrude(opening,.085,dark,loc=(0,face-.008,0),bevel=.001,smooth=False)
            mg.cut(head,cutter)
            seat,_=mg.surface_point(head,(x,-1,.709),(0,1,0))
            ey=seat[1]+.010
            eye=mg.part("sphere",lime if s == -1 else milk,loc=(x,ey,.709),rot=(0,s*.065,0),
                        scale=(.087 if s==-1 else .083,.048,.101 if s==-1 else .096),segments=40,ring_count=24,exact=True,smooth=True)
            parts.append(eye)
            if s == -1:
                pupil=mg.part("sphere",dark,loc=(x,ey-.028,.709),scale=(.013,.004,.061),
                              segments=24,ring_count=12,exact=True,smooth=True)
                parts.append(pupil)

    with mg.section("ears"):
        for s in (-1,1):
            # A welded fleshy root carries the shell; the bottom rim is embedded in it.
            # The broad ear base is embedded directly in the narrower skull.
            # A recessed ear bowl with a thick lip and crisp, asymmetric torn edges.
            # Broad, shorter ears: large stepped tears, rather than a long needle tip.
            contour=[(.070,.775),(.230,.766),(.251,.808),(.223,.812),
                     (.225,.828),(.260,.837),(.262,.850),(.239,.853),
                     (.244,.870),(.276,.881),(.279,.901),(.261,.904),
                     (.270,.920),(.281,.932),(.258,.929)]
            if s==1:
                contour=[(.070,.775),(.230,.766),(.252,.816),(.226,.820),
                         (.232,.840),(.267,.853),(.269,.870),(.248,.875),
                         (.256,.896),(.278,.910),(.280,.932),(.258,.929)]
            n=len(contour)
            front=[(s*x,-.047+.055*(z-.763)/.242,z) for x,z in contour]
            # The inner surface sits behind the rim, forming an actual cavity.
            inner=[(s*( .175+(x-.175)*.95),y+.018,.850+(z-.850)*.95)
                   for (x,z),(_,y,_) in zip(contour,front)]
            # Torn edges belong to the thin front lip; the rear hull has a continuous silhouette.
            rear=[]
            for i,(x,y,z) in enumerate(front):
                if 1<i<n-1:
                    t=(z-contour[1][1])/(contour[-1][1]-contour[1][1])
                    outer=contour[1][0]+t*(contour[-1][0]-contour[1][0])
                    x=s*outer
                rear.append((x,y+.090-.070*max(0,min(1,(z-.760)/.245)),z))
            vertices=front+inner+rear
            # Triangulate the torn outline before adding depth: concentric rings
            # overlap at concave notches and leave non-manifold boolean seams.
            inner_triangles=[]
            for tri in mg.triangulate_polygon(inner):
                corners=[n+i for i in tri]
                centre_inner=sum((Vector(vertices[i]) for i in corners),Vector())/3
                centre_inner.y+=.012
                centre_index=len(vertices)
                vertices.append(tuple(centre_inner))
                inner_triangles.extend((corners[i],corners[(i+1)%3],centre_index) for i in range(3))
            # A regular ring patch gives one coherent convex rear surface. Per-triangle
            # displacement made skinny triangles into visible wrinkles after exact union.
            centre=sum((Vector(p) for p in rear),Vector())/n
            previous=list(range(2*n,3*n))
            rear_triangles=[]
            for radius in (.88,.70,.50,.30,.12):
                ring=[]
                for point in rear:
                    v=centre+(Vector(point)-centre)*radius
                    v.y+=.026*math.sqrt(1-radius*radius)
                    ring.append(len(vertices));vertices.append(tuple(v))
                for i in range(n):
                    j=(i+1)%n
                    rear_triangles.extend(((previous[i],previous[j],ring[j]),
                                           (previous[i],ring[j],ring[i])))
                previous=ring
            tip=len(vertices);vertices.append(tuple(centre+Vector((0,.026,0))))
            rear_triangles.extend((previous[i],previous[(i+1)%n],tip) for i in range(n))
            yaw=s*math.radians(ear_yaw)
            pivot_x=s*.173
            vertices=[(pivot_x+math.cos(yaw)*(x-pivot_x)-math.sin(yaw)*(y-.020),
                       .020+math.sin(yaw)*(x-pivot_x)+math.cos(yaw)*(y-.020),z)
                      for x,y,z in vertices]
            pitch=math.radians(ear_pitch)
            vertices=[(x,.020+math.cos(pitch)*(y-.020)-math.sin(pitch)*(z-.790),
                       .790+math.sin(pitch)*(y-.020)+math.cos(pitch)*(z-.790)) for x,y,z in vertices]
            vertices=[(x*.82,y,z) for x,y,z in vertices]
            ear_inner.extend(tuple(Vector(vertices[i]) for i in tri) for tri in inner_triangles)
            faces=[]
            colors=[]
            for i in range(n):
                j=(i+1)%n
                faces.append((i,j,n+j,n+i)); colors.append(fur)
            for tri in inner_triangles:
                faces.append(tri); colors.append(pink)
            for tri in rear_triangles:
                faces.append(tuple(reversed(tri))); colors.append(fur)
            for i in range(n):
                j=(i+1)%n
                faces.append((i,2*n+i,2*n+j,j)); colors.append(fur)
            if s==-1:
                faces=[tuple(reversed(f)) for f in faces]
            ear=mg.mesh(vertices,faces,fur,face_colors=colors,name="ear_bowl",smooth=False)
            # Keep the front lip crisp while the continuous rear volume receives smooth normals.
            for polygon in ear.data.polygons:
                polygon.use_smooth=polygon.index>=n+len(inner_triangles)
            # Weld the shell after the root is smoothed, preserving the upper hull.
            ear_shells.append(ear)

    with mg.section("forehead_tuft"):
        # Short overlapping tapered tufts follow the crown rather than floating above it.
        for x,tip in [(-.031,.869),(0,.883),(.028,.866)]:
            tuft=mg.mesh([(x-.024,-.029,.826),(x+.024,-.029,.826),(x+.014,-.020,tip),
                          (x-.017,.035,.826),(x+.018,.035,.826)],
                         [(0,1,2),(2,4,3),(0,3,4,1),(1,4,2),(2,3,0)],cream,name="crown_tuft",smooth=True)
            parts.append(tuft)
            head_skin.append(tuft)

    with mg.section("backpack"):
        pack=block(leather,(0,.113,.403),(.202,.09,.204),.014)
        block(brown,(0,.163,.404),(.154,.01,.152),.006)
        for s in (-1,1):
            block(dark,(s*.066,.174,.405),(.025,.012,.184),.003)
            block(gold,(s*.066,.182,.473),(.03,.008,.014),.002)
        disk(cream,(0,.181,.407),(.078,.088))
        for s in (-1,1):
            disk(dark,(s*.017,.186,.415),(.021,.026))
        block(dark,(0,.187,.393),(.012,.004,.012),.003)

    with mg.section("tail",anchor=(0,.075,.26)):
        points=[(0,.08,.26),(.035,.15,.19),(.092,.225,.126),(.151,.29,.125),
                (.197,.319,.190),(.205,.310,.275)]
        radii=[.037,.039,.042,.040,.035,.017]
        tail=mg.curve(points,0,fur,radii=radii,sides=20,smooth=True)
        for i in (1,3,5):
            mg.paint(tail,cream,at=points[i],radius=.057)
        parts.append(tail)
        limb_skin.append(tail)
        tail_points=[Vector(point) for point in points]

    # Weld the skin after proportions are established; clothing remains a layer over it.
    parts=[p for p in parts if p not in body_skin and p not in head_skin and p not in limb_skin and p != muzzle]
    body=mg.union(body_skin,fillet=.007,detail=.34,relax=True,surface="voxel")
    connected(body)
    # Broad cheek planes are geometry, rather than flat shading on tiny voxel polygons.
    inverse=body.matrix_world.inverted()
    for vertex in body.data.vertices:
        point=body.matrix_world@vertex.co
        x,y,z=point
        if .577<z<.680 and abs(x)>.162 and y<-.045:
            weight=min(1,(abs(x)-.162)/.028)*min(1,(z-.577)/.018,(.680-z)/.018)
            plane=max(y-.012,min(y+.012,-.158+.45*(abs(x)-.170)+.12*(z-.620)))
            point.y=y*(1-weight)+plane*weight
            vertex.co=inverse@point
        elif .578<z<.650 and abs(x)<.142 and y<-.160:
            weight=min(1,(.650-z)/.010,(z-.578)/.010,(.142-abs(x))/.020)
            plane=-.184+.14*abs(x)+.28*(z-.612)
            plane=max(y-.018,min(y+.018,plane))
            point.y=y*(1-weight)+plane*weight
            vertex.co=inverse@point
    body.data.update()
    for edge in body.data.edges:
        edge.use_edge_sharp=False
    for polygon in body.data.polygons:
        polygon.use_smooth=True
    def paint_surface(obj,color,point,radius,facing=None):
        target=Vector(point)
        candidates=[v for v in obj.data.vertices if facing is None or v.normal.dot(Vector(facing))>.15]
        nearest=min(candidates,key=lambda v: (obj.matrix_world@v.co-target).length)
        mg.paint(obj,color,at=tuple(obj.matrix_world@nearest.co),radius=radius,facing=facing)

    body=mg.union([body,muzzle]+head_skin+ear_shells+limb_skin,surface="boolean")
    # Close exact-union junctions at 2.5mm while retaining the authored planar silhouette.
    mg.modify(body,"remesh",size=.0025)
    links=[set() for v in body.data.vertices]
    for edge in body.data.edges:
        a,b=edge.vertices;links[a].add(b);links[b].add(a)
    remaining=set(range(len(links)));groups=[]
    while remaining:
        group=set();pending=[min(remaining)]
        while pending:
            index=pending.pop()
            if index not in group:
                group.add(index);pending.extend(links[index]-group)
        remaining-=group;groups.append(group)
    groups.sort(key=len,reverse=True)
    if len(groups)>1:
        assert all(len(g)<=100 and max(max(body.data.vertices[i].co[a] for i in g)-min(body.data.vertices[i].co[a] for i in g) for a in range(3))<.010 for g in groups[1:]), "remesh detached meaningful skin: "+str([len(g) for g in groups])
        keep=sorted(groups[0]);mapping={old:new for new,old in enumerate(keep)}
        points=[tuple(body.data.vertices[i].co) for i in keep]
        faces=[tuple(mapping[i] for i in p.vertices) for p in body.data.polygons if p.vertices[0] in groups[0]]
        body.data.clear_geometry();body.data.from_pydata(points,[],faces);body.data.update()
    for polygon in body.data.polygons:
        polygon.use_smooth=True
    connected(body)
    mg.modify(body,"decimate",ratio=.12)
    # Zero displacement refines long flat edges before vertex-colour stencils.
    for z in (.650,.700,.750,.800,.840):
        for x in (-.085,0,.085):
            mg.sculpt(body,"inflate",at=(x,-.115,z),radius=.065,amount=0)
    connected(body)
    mg.preserve_surface(body)
    neighbours=[[] for _ in body.data.vertices]
    for edge in body.data.edges:
        a,b=edge.vertices
        neighbours[a].append(b)
        neighbours[b].append(a)
    root_indices=[v.index for v in body.data.vertices
                  if .755<(body.matrix_world@v.co).z<.870 and abs((body.matrix_world@v.co).x)>.160 and (body.matrix_world@v.co).y>-.025]
    for _ in range(12):
        positions=[v.co.copy() for v in body.data.vertices]
        for index in root_indices:
            average=sum((positions[j] for j in neighbours[index]),Vector())/max(1,len(neighbours[index]))
            delta=(average-positions[index])*.35
            if delta.length>.0010:
                delta=delta.normalized()*.0010
            body.data.vertices[index].co=positions[index]+delta
    body.data.update()
    # Paint after welding: old palette coordinates on boolean seams must not become texture colours.
    mg.paint(body,fur)
    mg.paint(body,cream,below=.566)
    for s in (-1,1):
        paint_surface(body,cream,(s*.065,muzzle_front,.614),.070,(0,-1,0))

    # Restore markings on the final connected skin instead of floating rings.
    for i,point in enumerate(tail_points):
        mg.paint(body,fur,at=tuple(point),radius=.050)
    for i in (1,3,5):
        mg.paint(body,cream,at=tuple(tail_points[i]),radius=.045)
    # The central stripe is a clean stencil in the colour layer, not overlapping circular brush stamps.
    layer=body.data.color_attributes.get("mg_paint")
    if layer:
        dark_linear=[((c+.055)/1.055)**2.4 for c in (78/255,65/255,63/255)]
        cream_linear=[((c+.055)/1.055)**2.4 for c in (222/255,200/255,171/255)]
        stripe_linear=[((c+.055)/1.055)**2.4 for c in (117/255,102/255,97/255)]
        fur_linear=[((c+.055)/1.055)**2.4 for c in (152/255,135/255,129/255)]
        tail_lengths=[0.0]
        for a,b in zip(tail_points,tail_points[1:]):
            tail_lengths.append(tail_lengths[-1]+(b-a).length)
        def segment_distance(x,z,a,b):
            dx,dz=b[0]-a[0],b[1]-a[1]
            t=max(0,min(1,((x-a[0])*dx+(z-a[1])*dz)/(dx*dx+dz*dz)))
            return math.hypot(x-a[0]-t*dx,z-a[1]-t*dz)
        def socket_distance(x,z,outline):
            inside=False
            distance=1.0
            for a,b in zip(outline,outline[1:]+outline[:1]):
                distance=min(distance,segment_distance(x,z,a,b))
                if (a[1]>z)!=(b[1]>z) and x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0]:
                    inside=not inside
            return -distance if inside else distance
        stitches=[]
        for side in (-1,1):
            x=side*.086
            stitches.append(((x-side*.010,.770),(x+side*.008,.812),.0045))
            for z in (.782,.800):
                stitches.append(((x-.013,z+.003),(x+.013,z-.003),.003))
        stitches.extend([((-.205,.650),(-.191,.663),.0025),((-.204,.663),(-.191,.650),.0025)])
        for vertex in body.data.vertices:
            point=body.matrix_world@vertex.co
            if .108<point.z<.124 and .035<abs(point.x)<.155 and point.y<.065:
                layer.data[vertex.index].color=stripe_linear+[1]
            if point.y>.100 and point.z<.320:
                best=(1.0,0.0)
                for i,(a,b) in enumerate(zip(tail_points,tail_points[1:])):
                    edge=b-a
                    t=max(0,min(1,(point-a).dot(edge)/edge.length_squared))
                    distance=(point-a-edge*t).length
                    if distance<best[0]:
                        best=(distance,tail_lengths[i]+edge.length*t)
                if best[0]<.050:
                    layer.data[vertex.index].color=(cream_linear if int(best[1]/.065)%2 else fur_linear)+[1]
            if .325<point.z<.480 and point.y<-.060 and abs(point.x)<.044:
                if (.359<point.z<.375 and abs(point.x-.010)<.014) or (.440<point.z<.460 and abs(point.x+.014)<.012):
                    layer.data[vertex.index].color=stripe_linear+[1]
            if point.y < -.065 and vertex.normal.y < -.3:
                distance=min(socket_distance(point.x,point.z,outline) for outline in socket_outlines)
                weight=max(0,min(1,(.003-distance)/.002))
                if weight and point.y>-.172 and not (point.z<.664 and point.y<-.145):
                    old=layer.data[vertex.index].color
                    layer.data[vertex.index].color=[old[i]*(1-weight)+dark_linear[i]*weight for i in range(3)]+[1]
                scar=min(segment_distance(point.x,point.z,a,b)/width for a,b,width in stitches)
                if scar<1.25:
                    weight=max(0,min(1,(1.25-scar)/.25))
                    old=layer.data[vertex.index].color
                    layer.data[vertex.index].color=[old[i]*(1-weight)+dark_linear[i]*weight for i in range(3)]+[1]
            stripe_width=.031 + (.007 if int((point.z-.61)/.032)%2==0 else 0)
            alpha=max(0,min(1,(stripe_width-abs(point.x))/.002))*max(0,min(1,(point.z-.612)/.008))
            if alpha:
                old=layer.data[vertex.index].color
                layer.data[vertex.index].color=[old[i]*(1-alpha)+cream_linear[i]*alpha for i in range(3)]+[1]
    else:
        for point in [(0,-.143,.641),(0,-.151,.686),(0,-.144,.732),(0,-.123,.778),
                      (0,-.075,.815),(0,0,.838),(0,.075,.815),(0,.125,.770),
                      (0,.140,.723),(0,.135,.677),(0,.113,.630)]:
            paint_surface(body,cream,point,.043)
    # Seat fine details on the FINAL welded surface, never on an assumed front plane.
    pink_linear=[((c+.055)/1.055)**2.4 for c in (185/255,103/255,101/255)]
    for vertex in body.data.vertices:
        point=body.matrix_world@vertex.co
        if point.z>.800 and any(near_triangle(point,triangle) for triangle in ear_inner):
            layer.data[vertex.index].color=pink_linear+[1]

    def on_face(x,z,offset=.0006):
        point,normal=mg.surface_point(body,(x,-1,z),(0,1,0))
        return Vector(point)+Vector(normal)*offset
    triangle=[on_face(-.021,.620),on_face(.021,.620),on_face(0,.601)]
    rear=[p+Vector((0,.008,0)) for p in triangle]
    nose_y=min(p.y for p in triangle+[on_face(0,.612)])-.003
    triangle=[Vector((p.x,nose_y,p.z)) for p in triangle]
    nose=mg.mesh([tuple(p) for p in triangle+rear],
                 [(0,1,2),(5,4,3),(0,3,4,1),(1,4,5,2),(2,5,3,0)],nose_pink,name="nose",smooth=True)
    parts.append(nose)
    paths=[[(0,.602),(0,.595),(0,.588)]]
    paths.extend([[(0,.588),(side*.015,.585),(side*.031,.582)] for side in (-1,1)])
    for path in paths:
        points=[tuple(on_face(x,z)) for x,z in path]
        parts.append(mg.curve(points,.0013,dark,sides=8,smooth=True))
    for side in (-1,1):
        for z,tip in ((.618,.636),(.606,.597),(.592,.555)):
            point,normal=mg.surface_point(body,(side*.054,-1,z),(0,1,0))
            seat,normal=Vector(point),Vector(normal)
            root=seat-normal*.006
            exit_point=seat+normal*.004+Vector((side*.018,0,0))
            whisker=mg.curve([tuple(root),tuple(exit_point),
                              (side*.164,seat.y-.012,z+.004),(side*.225,seat.y+.006,tip)],0,cream,
                             radii=[.0014,.0012,.0009,.00035],sides=6,smooth=True)
            parts.append(whisker)
        point,_=mg.surface_point(body,(side*.028,-1,.589),(0,1,0))
        x,y,z=point
        tooth=mg.mesh([(x-.006,y+.007,z+.007),(x+.006,y+.007,z+.007),
                       (x+.006,y-.004,z+.004),(x-.006,y-.004,z+.004),(x,y-.005,z-.015)],
                      [(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)],cream,name="fang",smooth=True)
        parts.append(tooth)
    # Replace the old guessed shells with fitted, hollow body-derived garments.
    for obj,role in clothing:
        if role in (1,2,4):
            parts.remove(obj)
            mg.discard(obj)
    clothing=[(obj,role) for obj,role in clothing if role==3]
    jacket=mg.garment(body,olive,above=.294,below=.505,gap=.009,thickness=.004,refine=1,open_front=.075,
        regions=[((-.15,-.11,.29),(.15,.11,.505)),((.13,-.11,.390),(.24,.11,.505)),((-.24,-.11,.390),(-.13,.11,.505))])
    shorts=mg.garment(body,brown,above=.160,below=.309,gap=.003,thickness=.002,refine=1,
        regions=[((-.172,-.13,.15),(.172,.13,.32))])
    parts.extend([jacket,shorts]);clothing.extend([(jacket,1),(shorts,2)])
    for sign in (-1,1):
        path=[(sign*.09,-.15,z) for z in (.338,.375,.412,.448,.477,.492)]
        path.extend([(sign*.09,-.023,.513),(sign*.09,.023,.513)])
        path.extend((sign*.09,.15,z) for z in (.492,.477,.448,.412))
        strap=mg.strap(jacket,leather,path,width=.033,thickness=.0045)
        parts.append(strap);clothing.append((strap,4))
    for obj in parts+[body]:
        layer=obj.data.attributes.get("cat_cloth_role") or obj.data.attributes.new("cat_cloth_role","INT","POINT")
        for item in layer.data:item.value=0
    for obj,role in clothing:
        mg.preserve_surface(obj)
        layer=obj.data.attributes.get("cat_cloth_role")
        for item in layer.data:item.value=role
    parts.append(body)
    result=mg.join("zombie_cat_scout_v15",parts)
    # Keep local shading: smooth skin, deliberate flat planes on claw wedges and ear shell.
    # The complete ear and its root are welded skin, with continuous shading.
