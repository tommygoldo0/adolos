"""
ADOLOS – globo 3D di notte (Blender)
====================================
Si lancia DENTRO Blender, da engine/reel_globo.py (non a mano):

    blender -b -P engine/blender_globo.py -- scena.json

scena.json:
  {"fotogrammi": 150, "fps": 30, "larghezza": 1080, "altezza": 1920, "uscita": "cartella/",   (JPEG numerati)
   "texture": "~/.adolos/mappe/notte_8k.jpg", "oro": [1.0, 0.83, 0.0],
   "punti": [{"lon": 114.06, "lat": 22.54, "da": 0.2}, ...],      "da" = secondo in cui il punto si accende
   "archi": [{"a": 0, "b": 1, "da": 0.6, "durata": 1.0}, ...],    indici dei punti
   "camera": {"da": {"lon": 20, "lat": 25, "distanza": 4.4}, "a": {"lon": 100, "lat": 30, "distanza": 3.0}}}

Terra di notte = foto NASA Black Marble (pubblico dominio). Niente testo e niente loghi: le scritte le mette
engine/reel_anim.py. Gli archi sono linee dorate che si disegnano da un punto all'altro.
"""

import json
import math
import sys
from pathlib import Path

import bpy
import mathutils

ORO = (1.0, 0.78, 0.05, 1.0)
LON0 = 0.0          # taratura della mappa sulla sfera (si controlla con un punto noto, vedi reel_globo.py --prova)


def dati():
    argv = sys.argv
    return json.loads(Path(argv[argv.index("--") + 1]).read_text(encoding="utf-8"))


def posizione(lon, lat, r=1.0):
    a, b = math.radians(lon + LON0), math.radians(lat)
    # sfera UV di Blender: la longitudine 0 guarda verso -Y, quella a est verso +X
    return mathutils.Vector((r * math.cos(b) * math.sin(a), -r * math.cos(b) * math.cos(a), r * math.sin(b)))


def facile(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def materiale_emissivo(nome, colore, forza):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = colore
    em.inputs["Strength"].default_value = forza
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def terra(texture):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=128, ring_count=64, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "Terra"
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("Notte")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    tex, em, base, mix, out = (nt.nodes.new(t) for t in ("ShaderNodeTexImage", "ShaderNodeEmission", "ShaderNodeBsdfDiffuse",
                                                         "ShaderNodeAddShader", "ShaderNodeOutputMaterial"))
    tex.image = bpy.data.images.load(str(Path(texture).expanduser()))
    tex.interpolation = "Linear"
    base.inputs["Color"].default_value = (0.012, 0.02, 0.05, 1)
    em.inputs["Strength"].default_value = 2.6
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], mix.inputs[0])
    nt.links.new(base.outputs["BSDF"], mix.inputs[1])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    g.data.materials.append(m)
    # alone leggero attorno alla Terra
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.025, segments=96, ring_count=48, location=(0, 0, 0))
    a = bpy.context.active_object
    a.name = "Alone"
    bpy.ops.object.shade_smooth()
    ma = bpy.data.materials.new("Alone")
    ma.use_nodes = True
    n = ma.node_tree
    n.nodes.clear()
    fr, em2, tr, mx, out2 = (n.nodes.new(t) for t in ("ShaderNodeLayerWeight", "ShaderNodeEmission", "ShaderNodeBsdfTransparent",
                                                      "ShaderNodeMixShader", "ShaderNodeOutputMaterial"))
    fr.inputs["Blend"].default_value = 0.5
    em2.inputs["Color"].default_value = (0.25, 0.45, 1.0, 1)
    em2.inputs["Strength"].default_value = 3.2
    pot = n.nodes.new("ShaderNodeMath")                   # potenza: l'alone resta solo sul bordo, il centro è limpido
    pot.operation = "POWER"
    pot.inputs[1].default_value = 4.0
    n.links.new(fr.outputs["Facing"], pot.inputs[0])
    n.links.new(pot.outputs["Value"], mx.inputs[0])
    n.links.new(em2.outputs["Emission"], mx.inputs[2])
    n.links.new(tr.outputs["BSDF"], mx.inputs[1])
    n.links.new(mx.outputs["Shader"], out2.inputs["Surface"])
    a.data.materials.append(ma)
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):   # niente puntini (dither)
        try:
            setattr(ma, attr, val)
        except Exception:
            pass
    g.rotation_euler[2] = math.radians(-90.0)           # taratura della foto sulla sfera: Roma e Shenzhen cadono giusti
    return g


def punto(p, i, fps):
    if p.get("nascosto"):                               # serve solo come estremo di un arco
        return None
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=24, ring_count=12, location=posizione(p["lon"], p["lat"], 1.004))
    o = bpy.context.active_object
    o.name = f"Punto{i}"
    o.data.materials.append(materiale_emissivo(f"Punto{i}", ORO, 2.6))
    f0 = int(p.get("da", 0) * fps)
    for f, s in ((max(0, f0 - 1), 0.0), (f0 + 6, 1.7), (f0 + 14, 1.0)):
        o.scale = (s, s, s)
        o.keyframe_insert("scale", frame=f)
    # respiro lento
    for k in range(1, 40):
        s = 1.0 + 0.22 * math.sin(k * 0.5)
        o.scale = (s, s, s)
        o.keyframe_insert("scale", frame=f0 + 14 + k * 8)
    return o


def arco(a, b, da, durata, fps, i, altezza=0.075, quota_fine=0.0):
    va, vb = posizione(a["lon"], a["lat"]), posizione(b["lon"], b["lat"])
    ang = va.angle(vb)
    pts = []
    for k in range(64):
        t = k / 63
        v = (va * math.sin((1 - t) * ang) + vb * math.sin(t * ang)) / max(1e-6, math.sin(ang)) if ang > 1e-4 else va
        pts.append(v.normalized() * (1.004 + altezza * ang * math.sin(math.pi * t) + quota_fine * t))
    cu = bpy.data.curves.new(f"Arco{i}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.0042
    cu.bevel_resolution = 3
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p_, v in zip(sp.points, pts):
        p_.co = (v.x, v.y, v.z, 1)
    o = bpy.data.objects.new(f"Arco{i}", cu)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(materiale_emissivo(f"Arco{i}", ORO, 2.0))
    f0, f1 = int(da * fps), int((da + durata) * fps)
    for f, v in ((max(0, f0 - 1), 0.0), (f0, 0.0), (f1, 1.0)):
        cu.bevel_factor_end = v
        cu.keyframe_insert("bevel_factor_end", frame=f)
    return o


def sciame(c, fps):
    """Tanti puntini dorati che si staccano da un punto e si disperdono (es. i satelliti persi): schema, non una traiettoria vera."""
    import random
    rnd = random.Random(7)
    centro = posizione(c["lon"], c["lat"], c.get("quota", 1.07))
    f0, durata = int(c["da"] * fps), max(6, int(c["durata"] * fps))
    for i in range(int(c.get("n", 40))):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.009, segments=12, ring_count=6, location=centro)
        o = bpy.context.active_object
        o.name = f"Sciame{i}"
        o.data.materials.append(materiale_emissivo(f"Sciame{i}", ORO, 2.6))
        u = mathutils.Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
        v = (u + centro.normalized() * 0.5).normalized() * rnd.uniform(0.12, 0.34)
        ritardo = rnd.randint(0, 6)
        for f in range(max(0, f0 - 1), f0 + durata + 1, 3):
            q = min(1.0, max(0.0, (f - f0 - ritardo) / durata))
            o.location = centro + v * (q ** 0.8) + centro.normalized() * (-0.05 * q * q)
            sc = 0.0 if q <= 0 else (1.0 - max(0.0, (q - 0.6) / 0.4)) * min(1.0, q * 12)
            o.scale = (sc, sc, sc)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("scale", frame=f)


def telecamera(cfg, tot, w, h):
    bpy.ops.object.empty_add(location=(0, 0, 0))
    bersaglio = bpy.context.active_object
    cam = bpy.data.cameras.new("Cam")
    cam.lens = 50
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = 36
    cam.shift_y = float(cfg.get("spostamento_y", 0.0))     # negativo = il globo sale (lascia posto al titolo o ai numeri)
    o = bpy.data.objects.new("Cam", cam)
    bpy.context.collection.objects.link(o)
    c = o.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = bersaglio, "TRACK_NEGATIVE_Z", "UP_Y"
    bpy.context.scene.camera = o
    da, a = cfg["da"], cfg["a"]
    for f in range(tot + 1):
        k = facile(f / max(1, tot))
        lon = da["lon"] + (a["lon"] - da["lon"]) * k
        lat = da["lat"] + (a["lat"] - da["lat"]) * k
        d = da["distanza"] + (a["distanza"] - da["distanza"]) * k
        o.location = posizione(lon, lat, d)
        o.keyframe_insert("location", frame=f)
    return o


def main():
    global ORO
    d = dati()
    if d.get("oro"):                                    # il colore viene da engine/stile_reel.py (GIALLO)
        ORO = tuple(d["oro"]) + (1.0,)
    fps, tot = int(d.get("fps", 30)), int(d["fotogrammi"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 0, tot - 1
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = d["larghezza"], d["altezza"], 100
    motori = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    sc.render.engine = next(m for m in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if m in motori)
    try:
        sc.eevee.taa_render_samples = int(d.get("campioni", 24))
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 94
    sc.world = bpy.data.worlds.new("Nero")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.005, 0.012, 1)
    terra(d["texture"])
    punti = [punto(p, i, fps) for i, p in enumerate(d.get("punti", []))]
    for i, r in enumerate(d.get("archi", [])):
        arco(d["punti"][r["a"]], d["punti"][r["b"]], r.get("da", 0), r.get("durata", 1.0), fps, i,
             r.get("altezza", 0.075), r.get("quota_fine", 0.0))
    if d.get("sciame"):
        sciame(d["sciame"], fps)
    telecamera(d["camera"], tot, d["larghezza"], d["altezza"])
    uscita = Path(d["uscita"]).expanduser()
    uscita.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(uscita / "f_")
    if d.get("solo_fotogramma") is not None:
        sc.frame_set(int(d["solo_fotogramma"]))
        sc.render.filepath = str(uscita / "prova.jpg")
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


main()
