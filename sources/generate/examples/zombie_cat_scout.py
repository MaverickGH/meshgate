"""Cat scout: designed silhouette and broad polygon planes, with markings in the same surface.
Build with lowpoly, finish faceted. Coordinates are metres, front is -Y, height about one metre.
"""
import math
from mathutils import Vector


def build(mg):
    fur = mg.color("fur_grey", "#988781", rough=0.9)
    cream = mg.color("fur_cream", "#dec8ab", rough=0.9)
    stripe = mg.color("fur_stripe", "#756661", rough=0.9)
    pink = mg.color("ear_pink", "#b96765", rough=0.9)
    olive = mg.color("shirt_olive", "#808364", rough=0.95)
    faded = mg.color("shirt_faded", "#999c7c", rough=0.95)
    brown = mg.color("shorts_brown", "#685247", rough=0.95)
    leather = mg.color("leather", "#926747", rough=0.85)
    dark = mg.color("socket", "#4e413f", rough=0.95)
    red = mg.color("bandana", "#a74d49", rough=0.95)
    gold = mg.color("brass", "#bea16d", rough=0.75)
    lime = mg.color("eye_lime", "#d4ef53", rough=0.7, glow=0.18)
    milk = mg.color("eye_milky", "#c4bdad", rough=0.7)
    parts = []

    # A ring loft gives a continuous silhouette with deliberately chosen large planes.
    def loft(name, rings, outline, color, bands=None):
        obj = mg.loft(rings, outline, color, name=name, bands=bands)
        parts.append(obj)
        return obj

    octagon = [(-.7,-1),(.7,-1),(1,-.55),(1,.55),(.7,1),(-.7,1),(-1,.55),(-1,-.55)]

    def panel(name, outline, y, color, depth=.004):
        obj = mg.extrude(outline, depth, color, loc=(0,y,0))
        parts.append(obj)
        return obj

    def block(color, loc, size, bevel=.006, rot=(0,0,0)):
        obj = mg.part("cube", color, loc=loc, scale=size, bevel=bevel, bevel_segments=1, rot=rot)
        parts.append(obj)
        return obj

    def limb(a, b, radii, color, sides=8):
        obj = mg.tube([a,b], 0, color, radii=radii, sides=sides, exact=True, smooth=False)
        parts.append(obj)
        return obj

    def disk(color, center, size):
        obj = mg.part("cyl", color, loc=center, scale=(size[0],size[1],.005),
                      rot=(math.pi/2,0,0), vertices=24, exact=True)
        parts.append(obj)
        return obj

    with mg.section("legs"):
        for s in (-1,1):
            x = s*.09
            loft("leg", [(x,0,.055,.044,.045),(x,0,.14,.041,.042),(x,0,.20,.048,.048)],
                 octagon, cream)
            # Bands replace colour on the surface instead of raised bracelet geometry.
            block(stripe,(x,-.044,.118),(.076,.003,.016),bevel=0)
            loft("paw", [(x,-.029,.008,.061,.083),(x,-.029,.054,.065,.085),
                         (x,-.013,.080,.044,.055)], octagon, cream)
            for k in (-1,0,1):
                panel("toe", [(x+k*.038-.015,.008),(x+k*.038+.015,.008),
                              (x+k*.038+.012,.041),(x+k*.038,.050),(x+k*.038-.012,.041)], -.117, cream, .018)

    with mg.section("shorts"):
        loft("waist", [(0,0,.27,.132,.082),(0,0,.33,.125,.077)],octagon,brown)
        for s in (-1,1):
            x=s*.082
            loft("trouser", [(x,0,.164,.066,.078),(x,0,.27,.058,.074)],octagon,brown)
            panel("ragged_hem",[(x-.060,.182),(x+.061,.182),(x+.064,.151),
                                (x+.035,.151),(x+.030,.164),(x+.008,.148),
                                (x-.012,.160),(x-.040,.149),(x-.059,.151)],-.079,brown)
        block(dark,(0,-.083,.302),(.24,.008,.025),bevel=0)
        block(gold,(0,-.092,.302),(.045,.006,.031),bevel=0)
        block(brown,(0,-.097,.302),(.025,.004,.016),bevel=0)
        for s in (-1,1):
            block(leather,(s*.141,-.010,.251),(.032,.067,.062))
        panel("shorts_patch",[(.096,.187),(.123,.184),(.128,.213),(.101,.222),(.089,.211)],-.083,leather)

    with mg.section("torso"):
        loft("chest",[(0,0,.31,.11,.074),(0,0,.43,.113,.078),(0,0,.505,.133,.070)],octagon,cream)
        # Single broad jacket panels. Only a few large tears interrupt the contour.
        for s in (-1,1):
            coords=[(.035,.315),(.13,.302),(.15,.321),(.131,.361),(.151,.444),
                    (.125,.494),(.073,.504),(.041,.459),(.057,.403)]
            panel("jacket_front",[(s*x,z) for x,z in coords],-.085,olive,.009)
            panel("jacket_patch",[(s*.082,.359),(s*.126,.350),(s*.116,.392),(s*.074,.397)],-.092,faded,.001)
        back=block(olive,(0,.060,.406),(.250,.035,.177),.014)
        for s in (-1,1):
            block(dark,(s*.09,-.099,.412),(.025,.009,.152),.002)
            block(gold,(s*.09,-.106,.448),(.037,.005,.029),.002)
            block(leather,(s*.09,-.110,.448),(.023,.003,.017),0)
            limb((s*.09,-.087,.484),(s*.09,.087,.484),[.012,.012],dark,4)

    with mg.section("arms"):
        for s in (-1,1):
            sh=(s*.124,0,.478)
            el=(s*.214,-.005,.388)
            wrist=(s*.282,-.009,.318)
            hand=(s*.305,-.013,.293)
            limb(sh,el,[.054,.046],olive)
            limb(el,wrist,[.038,.032],cream)
            # One clean bandage, inset red turn, instead of several overlapping wraps.
            if s == -1:
                a=Vector(el).lerp(Vector(wrist),.47)
                b=Vector(el).lerp(Vector(wrist),.80)
                limb(tuple(a),tuple(b),[.038,.035],cream)
                a=Vector(el).lerp(Vector(wrist),.53)
                b=Vector(el).lerp(Vector(wrist),.62)
                limb(tuple(a),tuple(b),[.0385,.0375],red)
            limb(wrist,hand,[.033,.042],cream,6)
            # Start each finger inside the palm, along the hand's own direction.
            forward=Vector((s*.025,0,-.03)).normalized()
            spread=Vector((0,-1,0)).cross(forward).normalized()
            for k in (-1,0,1):
                root=Vector(hand)-forward*.016+spread*(k*.018)
                tip=Vector(hand)+forward*.027+spread*(k*.018)
                limb(tuple(root),tuple(tip),[.015,.005],stripe,4)

    with mg.section("neck"):
        loft("scarf",[(0,0,.477,.123,.079),(0,0,.521,.110,.072)],octagon,red)
        panel("scarf_front",[(-.123,.504),(.120,.504),(.085,.463),(.015,.407),(-.075,.461)],-.110,red,.014)
        panel("scarf_fold",[(-.112,.498),(.108,.498),(.037,.473),(-.053,.465)],-.119,red,.003)
        panel("scarf_knot",[(-.075,.505),(-.146,.517),(-.110,.487),(-.158,.465),(-.080,.477)],.080,red,.01)

    hz=.706
    head_outline=[(-.72,-1),(-.18,-1),(.18,-1),(.72,-1),(1,-.5),(1,.35),
                  (.65,1),(.18,1),(-.18,1),(-.65,1),(-1,.35),(-1,-.5)]
    with mg.section("head",anchor=(0,0,.526)):
        cols=[fur,cream,fur,fur,fur,fur,fur,cream,fur,fur,fur,fur]
        head=loft("head",[(0,0,.544,.135,.100),(0,0,.586,.216,.146),
                          (0,0,.706,.242,.182),(0,0,.803,.194,.154),
                          (0,0,.858,.104,.092)],head_outline,fur,cols)
        # The cheeks and muzzle have few large faces and a real projection in profile.
        for s in (-1,1):
            panel("cheek",[(s*.145,.676),(s*.213,.682),(s*.250,.642),(s*.224,.632),
                           (s*.238,.608),(s*.160,.577),(s*.115,.594)],-.110,fur,.095)
        panel("muzzle",[(-.136,.624),(-.065,.646),(0,.636),(.065,.646),(.136,.624),
                         (.084,.588),(0,.575),(-.084,.588)],-.170,cream,.053)
        for s in (-1,1):
            x=s*.110
            eye_outline=[(x-.062,.745),(x+.059,.741),(x+.059,.643),
                    (x+.032,.625),(x-.057,.633)]
            parts.append(mg.mesh([(vx,-.188,z) for vx,z in eye_outline],
                                 [tuple(reversed(range(5)))],dark,name="socket"))
            n=24
            vertices=[(x,-.196,.682)]
            for k in range(n):
                a=2*math.pi*k/n
                z=.682+.049*math.sin(a)
                vertices.append((x+.043*math.cos(a),-.196,z))
            faces=[(0,k+1,(k+1)%n+1) for k in range(n)]
            parts.append(mg.mesh(vertices,faces,lime if s == -1 else milk,name="iris"))
        panel("pupil",[(-.116,.708),(-.106,.708),(-.105,.656),(-.115,.656)],-.200,dark,.001)
        panel("nose",[(-.023,.622),(.023,.622),(0,.601)],-.205,red,.009)
        limb((0,-.205,.601),(0,-.206,.587),[.0017,.0017],dark,4)
        for s in (-1,1):
            limb((0,-.206,.587),(s*.033,-.201,.581),[.0017,.0017],dark,4)
            panel("fang",[(s*.028-.006,.588),(s*.028+.006,.588),(s*.028,.568)],-.198,cream,.008)
            # Forehead scars stay flat and sparse.
            limb((s*.106,-.160,.788),(s*.113,-.174,.754),[.004,.004],dark,4)
            for z in (.764,.779):
                limb((s*.105-.009,-.177,z),(s*.105+.009,-.177,z-.002),[.002,.002],dark,4)
            for z,tip in ((.622,.627),(.605,.581)):
                limb((s*.095,-.205,z),(s*.280,-.195,tip),[.0012,.0005],cream,4)

    with mg.section("ears"):
        for s in (-1,1):
            # A shared tip makes a tapered volume, rather than a plate of constant thickness.
            vertices=[(s*.063,-.024,.774),(s*.207,-.014,.786),(s*.245,.010,.987),
                      (s*.063,.066,.774),(s*.207,.071,.786)]
            faces=[(0,1,2),(2,4,3),(0,3,4,1),(1,4,2),(2,3,0)]
            if s == -1:
                faces=[tuple(reversed(f)) for f in faces]
            ear=mg.mesh(vertices,faces,fur,name="ear",smooth=False)
            mg.modify(ear,"bevel",width=.002,segments=1)
            parts.append(ear)
            base=Vector(vertices[0])
            normal=(Vector(vertices[1])-base).cross(Vector(vertices[2])-base)
            inner=[]
            for x,z in [(s*.105,.814),(s*.180,.819),(s*.226,.946)]:
                y=base.y-(normal.x*(x-base.x)+normal.z*(z-base.z))/normal.y-.001
                inner.append((x,y,z))
            parts.append(mg.mesh(inner,[(0,1,2) if s==1 else (2,1,0)],pink,name="inner_ear"))

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
        radii=[.039,.043,.045,.043,.038,.031]
        for i in range(len(points)-1):
            limb(points[i],points[i+1],[radii[i],radii[i+1]],cream if i%2==0 else stripe,6)

    mg.join("zombie_cat_scout",parts)
