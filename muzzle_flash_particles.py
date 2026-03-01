"""
muzzle_flash_particles.py
NukeX 13.2v1 — Muzzle Flash Particle System
============================================================
Creates four distinct muzzle flash looks using Nuke's built-in
particle system nodes.  All effects share a single Axis node
('MuzzleFlash_Origin') as their world-space parent, so the
entire rig can be repositioned or animated by moving one node.

Flash types
-----------
  1. STAR FLASH     — 8-ray starburst (camera iris artifact look)
  2. HOT GAS FLASH  — Layered expanding fireball (core/mid/outer)
  3. SPARK FLASH    — Fast streaking sparks with gravity arcs
  4. SMOKE PUFF     — Diffuse post-flash smoke cloud (delayed)

Usage
-----
  Window > Script Editor → paste this file → Ctrl+Enter
  Nuke will build the node graph in the current project.

Requires NukeX (particle nodes are NukeX-only).
"""

import nuke
import math

# ─────────────────────────────────────────────────────────────────
#  USER SETTINGS  —  tweak these to match your shot
# ─────────────────────────────────────────────────────────────────

FLASH_START  = 1    # frame on which the gun fires
FLASH_FRAMES = 2    # how many frames of particle emission
FLASH_END    = FLASH_START + FLASH_FRAMES

# HDR colour tuples  (R, G, B)  — values > 1.0 simulate bright light
COL_WHITE_HOT = (4.0, 4.0, 4.0)
COL_YELLOW    = (4.0, 3.6, 0.4)
COL_ORANGE    = (4.0, 1.8, 0.2)
COL_SPARK     = (5.0, 3.2, 0.4)
COL_SMOKE     = (0.16, 0.13, 0.10)


# ─────────────────────────────────────────────────────────────────
#  LOW-LEVEL HELPERS
# ─────────────────────────────────────────────────────────────────

def _xy(node, x, y):
    """Position a node in the DAG."""
    node['xpos'].setValue(x)
    node['ypos'].setValue(y)


def _set(node, knob, value):
    """Set a knob by name, silently ignoring missing knobs."""
    try:
        node[knob].setValue(value)
    except Exception:
        pass


def _label(node, text):
    _set(node, 'label', text)


def _make_backdrop(label, x, y, w, h, r=0.18, g=0.18, b=0.18):
    """Create a labelled backdrop behind a section of the graph."""
    bd = nuke.createNode('BackdropNode', inpanel=False)
    _set(bd, 'label', label)
    _set(bd, 'note_font_size', 28)
    bd['xpos'].setValue(x)
    bd['ypos'].setValue(y)
    _set(bd, 'bdwidth',  w)
    _set(bd, 'bdheight', h)
    _set(bd, 'tile_color', int('%02x%02x%02x%02x' % (
        int(r * 255), int(g * 255), int(b * 255), 255), 16))
    return bd


# ─────────────────────────────────────────────────────────────────
#  PARTICLE NODE FACTORIES
# ─────────────────────────────────────────────────────────────────

def make_axis(name, parent, rotate_xyz=(0, 0, 0), x=0, y=0):
    """Create an Axis2 node, optionally parented to another Axis."""
    a = nuke.createNode('Axis2', inpanel=False)
    a.setName(name)
    if parent is not None:
        a.setInput(0, parent)
    _set(a, 'rotate', list(rotate_xyz))
    _xy(a, x, y)
    return a


def make_camera(name='MuzzleFlash_Cam', x=0, y=-300):
    """Perspective camera for ParticleToImage projection."""
    cam = nuke.createNode('Camera2', inpanel=False)
    cam.setName(name)
    _set(cam, 'translate', [0.0, 0.0, 500.0])
    _set(cam, 'focal', 50.0)
    _xy(cam, x, y)
    return cam


def make_emitter(name, parent, x, y,
                 birth_rate=50,
                 life=6,         life_var=0.35,
                 speed=100,      speed_var=0.35,
                 size=4,         size_var=0.5,
                 spread=1.0,
                 color=COL_WHITE_HOT,
                 start=FLASH_START,
                 end=FLASH_END):
    """
    Create and configure a ParticleEmitter.

    spread  — emission cone half-angle normalised 0-1
              0.0 = pencil-thin directional beam
              1.0 = full sphere
    color   — (R, G, B) tuple
    """
    e = nuke.createNode('ParticleEmitter', inpanel=False)
    e.setName(name)
    e.setInput(0, parent)
    _xy(e, x, y)

    _set(e, 'birth_rate',     birth_rate)
    _set(e, 'rate',           birth_rate)       # alternate knob name

    _set(e, 'life',           life)
    _set(e, 'life_variance',  life_var)

    _set(e, 'speed',          speed)
    _set(e, 'speed_variance', speed_var)

    _set(e, 'size',           size)
    _set(e, 'size_variance',  size_var)

    _set(e, 'spread',         spread)
    _set(e, 'emission_angle', spread * 180.0)   # alternate knob name

    # particle colour (RGBA)
    _set(e, 'color', list(color) + [1.0])

    _set(e, 'start_frame', start)
    _set(e, 'end_frame',   end)

    return e


def add_gravity(src, x, y, magnitude=150, direction=(0.0, -1.0, 0.0)):
    """Connect a ParticleGravity modifier."""
    g = nuke.createNode('ParticleGravity', inpanel=False)
    g.setName(src.name() + '_Grav')
    g.setInput(0, src)
    _xy(g, x, y)
    _set(g, 'magnitude', magnitude)
    _set(g, 'strength',  magnitude)   # alternate knob name
    _set(g, 'direction', list(direction))
    _set(g, 'force',     list(d * magnitude for d in direction))
    return g


def add_turbulence(src, x, y, intensity=20.0, frequency=0.5, octaves=2):
    """Connect a ParticleTurbulence modifier."""
    t = nuke.createNode('ParticleTurbulence', inpanel=False)
    t.setName(src.name() + '_Turb')
    t.setInput(0, src)
    _xy(t, x, y)
    _set(t, 'intensity',  intensity)
    _set(t, 'frequency',  frequency)
    _set(t, 'octaves',    octaves)
    return t


def add_wind(src, x, y, direction=(0.0, 1.0, 0.0), strength=12.0):
    """Connect a ParticleWind modifier (NukeX 13+)."""
    try:
        w = nuke.createNode('ParticleWind', inpanel=False)
        w.setName(src.name() + '_Wind')
        w.setInput(0, src)
        _xy(w, x, y)
        _set(w, 'direction', list(direction))
        _set(w, 'strength',  strength)
        _set(w, 'magnitude', strength)
        return w
    except Exception:
        return src   # graceful fallback if node doesn't exist


def to_image(src, name, x, y, camera=None):
    """
    Create a ParticleToImage node to render a particle stream.
    camera — optional Camera2 node; set as input 1 for projection.
    """
    p = nuke.createNode('ParticleToImage', inpanel=False)
    p.setName(name)
    p.setInput(0, src)
    if camera is not None:
        try:
            p.setInput(1, camera)
        except Exception:
            pass
    _xy(p, x, y)
    return p


def add_glow(src, name, x, y, size=25.0, intensity=0.6):
    """Optional soft glow on a rendered particle layer."""
    g = nuke.createNode('Glow2', inpanel=False)
    g.setName(name)
    g.setInput(0, src)
    _set(g, 'size',      size)
    _set(g, 'intensity', intensity)
    _xy(g, x, y)
    return g


def plus_merge(a, b, x, y, label=''):
    """Additive Merge (plus operation) for light-emitting particles."""
    m = nuke.createNode('Merge2', inpanel=False)
    _set(m, 'operation', 'plus')
    m.setInput(0, a)
    m.setInput(1, b)
    if label:
        _label(m, label)
    _xy(m, x, y)
    return m


def chain_merge(renders, base_x, base_y):
    """Reduce a list of render nodes into a single additive merge tree."""
    valid = [n for n in renders if n is not None]
    if not valid:
        return None
    result = valid[0]
    for i, r in enumerate(valid[1:], 1):
        result = plus_merge(result, r,
                            base_x + i * 90,
                            base_y,
                            label=f'+{i}')
    return result


# ─────────────────────────────────────────────────────────────────
#  FLASH TYPE 1 — STAR FLASH
#  Classic 8-ray starburst (camera iris diffraction artifact)
# ─────────────────────────────────────────────────────────────────

def build_star_flash(origin, camera, cx, cy):
    """
    Eight sub-axes are each rotated a further 45° around Z.
    A tight-spread emitter on each sub-axis fires a bright beam
    of white particles outward.  The beams form the star pattern.
    A central bloom emitter adds the overexposed core.

    Tip: increase NUM_RAYS to 12 for an anamorphic look;
         decrease to 4 for a simple cross-hair flash.
    """
    NUM_RAYS = 8
    renders  = []

    for i in range(NUM_RAYS):
        angle_z = (360.0 / NUM_RAYS) * i   # 0, 45, 90 … 315 degrees

        # Sub-axis oriented along this ray direction
        ray_ax = make_axis(
            f'Star_RayAxis_{i:02d}', origin,
            rotate_xyz=(0.0, 0.0, angle_z),
            x=cx + i * 110,
            y=cy + 60,
        )

        # Tight beam emitter — almost zero spread
        e = make_emitter(
            f'Star_Emit_{i:02d}', ray_ax,
            x=cx + i * 110, y=cy + 200,
            birth_rate = 18,
            life       = 4,   life_var  = 0.08,
            speed      = 420, speed_var = 0.07,
            size       = 1.8, size_var  = 0.25,
            spread     = 0.02,          # nearly zero = laser-tight beam
            color      = COL_WHITE_HOT,
        )

        r = to_image(e, f'Star_P2I_{i:02d}',
                     cx + i * 110, cy + 360, camera)
        renders.append(r)

    # Central overexposed bloom burst
    bloom = make_emitter(
        'Star_Bloom_Core', origin,
        x=cx + 420, y=cy + 200,
        birth_rate = 90,
        life       = 3,   life_var  = 0.15,
        speed      = 18,  speed_var = 0.5,
        size       = 14,  size_var  = 0.4,
        spread     = 1.0,
        color      = COL_WHITE_HOT,
    )
    bloom_r = to_image(bloom, 'Star_Bloom_P2I',
                       cx + 420, cy + 360, camera)
    bloom_g = add_glow(bloom_r, 'Star_Bloom_Glow',
                       cx + 420, cy + 490, size=40, intensity=0.8)
    renders.append(bloom_g)

    merged = chain_merge(renders, cx + 100, cy + 620)
    if merged:
        merged.setName('StarFlash_MERGE')
    return merged


# ─────────────────────────────────────────────────────────────────
#  FLASH TYPE 2 — HOT GAS FLASH
#  Three concentric shells build a convincing fireball
# ─────────────────────────────────────────────────────────────────

def build_hot_gas_flash(origin, camera, cx, cy):
    """
    Three emitter layers at increasing radii give the flash depth:
      • Core   — white-hot, fast, tight
      • Mid    — yellow, spherical, medium speed
      • Outer  — orange, turbulent, slow

    All three are merged additively to build an HDR fireball.
    """
    # ── Core ────────────────────────────────────────────────────
    core = make_emitter(
        'HotGas_Core', origin,
        x=cx, y=cy,
        birth_rate = 130, life = 3,   life_var  = 0.2,
        speed      = 75,  speed_var = 0.4,
        size       = 5,   size_var  = 0.5,
        spread     = 0.75,
        color      = COL_WHITE_HOT,
    )
    core_r = to_image(core, 'HotGas_Core_P2I', cx, cy + 160, camera)

    # ── Mid shell ───────────────────────────────────────────────
    mid = make_emitter(
        'HotGas_Mid', origin,
        x=cx + 190, y=cy,
        birth_rate = 85,  life = 5,   life_var  = 0.3,
        speed      = 48,  speed_var = 0.5,
        size       = 9,   size_var  = 0.5,
        spread     = 1.0,
        color      = COL_YELLOW,
    )
    mid_grav = add_gravity(mid, cx + 190, cy + 140, magnitude=35)
    mid_r = to_image(mid_grav, 'HotGas_Mid_P2I',
                     cx + 190, cy + 300, camera)

    # ── Outer fringe ────────────────────────────────────────────
    outer = make_emitter(
        'HotGas_Outer', origin,
        x=cx + 380, y=cy,
        birth_rate = 65,  life = 7,   life_var  = 0.4,
        speed      = 24,  speed_var = 0.6,
        size       = 15,  size_var  = 0.7,
        spread     = 1.0,
        color      = COL_ORANGE,
    )
    outer_turb = add_turbulence(outer,      cx + 380, cy + 140,
                                intensity=18, frequency=0.3)
    outer_grav = add_gravity(outer_turb, cx + 380, cy + 300,
                             magnitude=22)
    outer_r = to_image(outer_grav, 'HotGas_Outer_P2I',
                       cx + 380, cy + 460, camera)

    renders = [core_r, mid_r, outer_r]
    merged  = chain_merge(renders, cx + 60, cy + 610)
    if merged:
        merged.setName('HotGasFlash_MERGE')
    return merged


# ─────────────────────────────────────────────────────────────────
#  FLASH TYPE 3 — SPARK FLASH
#  High-velocity sparks with ballistic gravity arcs
# ─────────────────────────────────────────────────────────────────

def build_spark_flash(origin, camera, cx, cy):
    """
    Two emitter groups create the spark look:
      • Main sparks   — fast, tight forward cone, long life
      • Scatter sparks — slower, wide spread, shorter life

    Gravity bends their trajectories into realistic arcs.
    A forward-pointing sub-axis biases the main sparks along the
    barrel direction (default +X world; rotate the sub-axis to
    match your barrel orientation).
    """
    # Sub-axis pointing along barrel direction (+X by default)
    fwd_axis = make_axis(
        'Spark_BarrelAxis', origin,
        rotate_xyz=(0.0, 0.0, 0.0),   # rotate Y to aim the barrel
        x=cx, y=cy,
    )
    _label(fwd_axis, 'Rotate to aim barrel')

    # ── Main sparks: tight forward cone ─────────────────────────
    main = make_emitter(
        'Spark_Main', fwd_axis,
        x=cx, y=cy + 140,
        birth_rate = 45,
        life       = 14,  life_var  = 0.5,
        speed      = 720, speed_var = 0.38,
        size       = 1.6, size_var  = 0.8,
        spread     = 0.18,              # mostly forward with slight fan
        color      = COL_SPARK,
    )
    main_grav = add_gravity(main, cx, cy + 290, magnitude=120)
    main_r    = to_image(main_grav, 'Spark_Main_P2I',
                         cx, cy + 450, camera)

    # ── Scatter sparks: chaotic wide burst ──────────────────────
    scatter = make_emitter(
        'Spark_Scatter', origin,
        x=cx + 210, y=cy + 140,
        birth_rate = 38,
        life       = 9,   life_var  = 0.6,
        speed      = 290, speed_var = 0.6,
        size       = 1.1, size_var  = 1.0,
        spread     = 0.55,
        color      = COL_ORANGE,
    )
    scatter_grav = add_gravity(scatter, cx + 210, cy + 290, magnitude=95)
    scatter_r    = to_image(scatter_grav, 'Spark_Scatter_P2I',
                            cx + 210, cy + 450, camera)

    renders = [main_r, scatter_r]
    merged  = chain_merge(renders, cx + 60, cy + 610)
    if merged:
        merged.setName('SparkFlash_MERGE')
    return merged


# ─────────────────────────────────────────────────────────────────
#  FLASH TYPE 4 — SMOKE PUFF
#  Diffuse billowing cloud that trails the flash
# ─────────────────────────────────────────────────────────────────

def build_smoke_puff(origin, camera, cx, cy):
    """
    Starts a couple of frames after FLASH_END so the smoke appears
    to trail the burst.  Large, semi-transparent particles with
    turbulence and an upward wind give a natural billow.
    """
    smoke_start = FLASH_END + 2
    smoke_end   = smoke_start + 8

    smoke = make_emitter(
        'Smoke_Emit', origin,
        x=cx, y=cy,
        birth_rate = 22,
        life       = 28,  life_var  = 0.45,
        speed      = 8,   speed_var = 0.7,
        size       = 38,  size_var  = 0.65,
        spread     = 0.9,
        color      = COL_SMOKE,
        start      = smoke_start,
        end        = smoke_end,
    )

    turb = add_turbulence(smoke, cx, cy + 150,
                          intensity=24, frequency=0.18, octaves=3)
    wind = add_wind(turb,  cx, cy + 300,
                   direction=(0.0, 1.0, 0.0), strength=14.0)

    smoke_r = to_image(wind, 'Smoke_P2I', cx, cy + 460, camera)

    if smoke_r:
        smoke_r.setName('SmokePuff_MERGE')
    return smoke_r


# ─────────────────────────────────────────────────────────────────
#  TOP-LEVEL ASSEMBLY
# ─────────────────────────────────────────────────────────────────

def create_muzzle_flash():
    """
    Build the entire muzzle flash rig in the current Nuke project.
    Returns (origin_axis, final_merge_node).
    """
    print("=" * 60)
    print("  NukeX 13.2v1 — Muzzle Flash Particle System")
    print("=" * 60)

    # ── Master origin Axis ──────────────────────────────────────
    origin = make_axis('MuzzleFlash_Origin', parent=None, x=0, y=0)
    _label(origin,
           '<b>MuzzleFlash_Origin</b>\n'
           'Animate/reparent this Axis\n'
           'to position the whole effect')

    # ── Shared camera ───────────────────────────────────────────
    cam = make_camera('MuzzleFlash_Cam', x=0, y=-250)

    # ── Column layout ───────────────────────────────────────────
    # Each flash type gets its own column so the graph stays tidy.
    ROW = 160
    C_STAR  = -1500
    C_GAS   =  -400
    C_SPARK =   450
    C_SMOKE =  1200

    # ── Star Flash ──────────────────────────────────────────────
    _make_backdrop('STAR FLASH\n(8-ray starburst)',
                   C_STAR - 60, ROW - 60, 1100, 820,
                   r=0.12, g=0.18, b=0.22)
    print("  [1/4] Star Flash …")
    star = build_star_flash(origin, cam, C_STAR, ROW)

    # ── Hot Gas Flash ───────────────────────────────────────────
    _make_backdrop('HOT GAS FLASH\n(layered fireball)',
                   C_GAS - 60, ROW - 60, 580, 760,
                   r=0.22, g=0.14, b=0.08)
    print("  [2/4] Hot Gas Flash …")
    gas = build_hot_gas_flash(origin, cam, C_GAS, ROW)

    # ── Spark Flash ─────────────────────────────────────────────
    _make_backdrop('SPARK FLASH\n(ballistic sparks)',
                   C_SPARK - 60, ROW - 60, 500, 760,
                   r=0.22, g=0.18, b=0.08)
    print("  [3/4] Spark Flash …")
    spark = build_spark_flash(origin, cam, C_SPARK, ROW)

    # ── Smoke Puff ──────────────────────────────────────────────
    _make_backdrop('SMOKE PUFF\n(post-flash cloud)',
                   C_SMOKE - 60, ROW - 60, 360, 680,
                   r=0.15, g=0.15, b=0.15)
    print("  [4/4] Smoke Puff …")
    smoke = build_smoke_puff(origin, cam, C_SMOKE, ROW)

    # ── Final composite ─────────────────────────────────────────
    print("  Compositing final output …")
    tops   = [n for n in [star, gas, spark, smoke] if n is not None]
    final  = chain_merge(tops, -200, 1650)
    if final:
        final.setName('MuzzleFlash_FINAL')
        _xy(final, 0, 1720)
        _label(final,
               '<b>MuzzleFlash_FINAL</b>\n'
               'Connect to your comp here')

    print("=" * 60)
    print("  Done!  Node graph built successfully.")
    print(f"  Flash fires on frame {FLASH_START}.")
    print(f"  Smoke trails from frame {FLASH_END + 2}.")
    print("  Reposition: animate 'MuzzleFlash_Origin' Axis.")
    print("  Aim sparks: rotate 'Spark_BarrelAxis' around Y.")
    print("=" * 60)

    return origin, final


# ─────────────────────────────────────────────────────────────────
#  RUN  (executes when pasted into Script Editor)
# ─────────────────────────────────────────────────────────────────

if __name__ == '__main__' or True:
    create_muzzle_flash()
