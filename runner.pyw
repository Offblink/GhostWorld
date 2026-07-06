"""GhostEngine launcher — minimal single-player viewer."""
import sys, math, os
import numpy as np, pygame
from ghostengine import (
    Frame, PlayerView, EntityView, ColorConfig, WallDef,
    FirstPersonController, render, TextureLoader,
    load_raw, build_colors, build_entities, draw_minimap, FogConfig,
)
from metaverse._shared import fix_ime, chinese_font


def run(path):
    fix_ime(); pygame.init()
    screen = pygame.display.set_mode((1068,801), pygame.RESIZABLE)
    pygame.display.set_caption("GhostEngine")
    pygame.event.set_grab(True); pygame.mouse.set_visible(False)

    raw = load_raw(path)
    _bd = os.path.dirname(os.path.abspath(path))
    loader = TextureLoader(os.path.join(_bd, "assets") if os.path.isdir(os.path.join(_bd, "assets")) else _bd)
    colors = build_colors(raw, loader)
    entities = build_entities(raw, loader)

    grid = np.array(raw["grid"], dtype=int).T
    # Validate: entities must not overlap walls
    from ghostengine.mapfile import validate_entities_on_walls
    val_errors = validate_entities_on_walls(grid, raw.get("entities", []), raw.get("player_spawn"))
    for err in val_errors:
        print(f"[runner] ⚠ {err}")
    ps = raw.get("player_spawn", {"x":7.5,"y":7.5,"angle":0})
    ctrl = FirstPersonController(x=ps["x"], y=ps["y"], angle=ps.get("angle",0), pitch=0, walls=grid)
    mm_cfg = raw.get("minimap", {"mode": "always", "duration": 0})
    mm_granted = mm_cfg.get("mode") == "always"
    mm_timer = 0.0
    W,H=1068,801; ctrl.set_screen_height(H)
    test_cfg = raw.get("test", {})
    fog_on = test_cfg.get("g_enabled", True)
    sens = 2.5
    full, mm, paused = False, False, False
    clock = pygame.time.Clock(); running = True
    while running:
        dt=clock.tick(120)/1000.0
        if dt>0.1: dt=0.016
        mr=(0,0)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: running=False
            elif e.type==pygame.KEYDOWN:
                if paused:
                    if e.key==pygame.K_SPACE: paused=False; pygame.event.set_grab(True); pygame.mouse.set_visible(False)
                    elif e.key==pygame.K_q: running=False
                    continue
                if e.key==pygame.K_ESCAPE: running=False
                elif e.key==pygame.K_SPACE: paused=True; pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                elif e.key==pygame.K_f: full=not full; screen=pygame.display.set_mode((0,0),pygame.FULLSCREEN) if full else pygame.display.set_mode((W,H),pygame.RESIZABLE); ctrl.set_screen_height(screen.get_height())
                elif e.key==pygame.K_m and mm_granted: mm=not mm
                elif e.key==pygame.K_g and test_cfg.get("g_enabled", False): fog_on = not fog_on
            elif e.type==pygame.MOUSEMOTION: mr=e.rel

        if paused:
            s=pygame.display.get_surface()
            if s:
                sw,sh=s.get_size(); o=pygame.Surface((sw,sh),pygame.SRCALPHA); o.fill((0,0,0,160)); s.blit(o,(0,0))
                fl=chinese_font(48)
                s.blit(fl.render("PAUSED",1,(255,255,255)), fl.render("PAUSED",1,(255,255,255)).get_rect(center=(sw//2,sh//2-40)))
            pygame.display.flip(); continue

        k=pygame.key.get_pressed()
        fw=st=0.0
        if k[pygame.K_w]: fw+=1.0
        if k[pygame.K_s]: fw-=1.0
        if k[pygame.K_a]: st+=1.0
        if k[pygame.K_d]: st-=1.0
        ctrl.move(fw*2.5*dt, st*2.5*dt, dt)

        # minimap trigger
        if not mm_granted and mm_cfg.get("mode") == "trigger":
            for ent in entities:
                if not ent.mm_trigger: continue
                if abs(ctrl.x - ent.x) < 1.5 and abs(ctrl.y - ent.y) < 1.5:
                    mm_granted = True; mm_timer = mm_cfg.get("duration", 0)
                    break
        if mm_granted and mm_cfg.get("duration", 0) > 0:
            mm_timer -= dt
            if mm_timer <= 0: mm_granted = False

        # pickup
        to_remove = []
        new_pickups: list[str] = []
        for i, ent in enumerate(entities):
            if not ent.pickup: continue
            if ent.kind not in ("item", "prop"): continue
            # Respect capture_for restriction
            cf = ent.capture_for
            if cf and cf not in ("*", ""):
                continue  # restricted to someone else
            dist = ((ctrl.x - ent.x)**2 + (ctrl.y - ent.y)**2)**0.5
            if dist < 1.0:
                to_remove.append(i)
                label = ent.pickup_label or "物品"
                new_pickups.append(label)
        for i in reversed(to_remove):
            del entities[i]
        # Track inventory counts
        if not hasattr(run, '_inventory'):
            run._inventory = {}
        for label in new_pickups:
            run._inventory[label] = run._inventory.get(label, 0) + 1

        yk=pk=0.0
        if k[pygame.K_LEFT]: yk-=2.5*sens
        if k[pygame.K_RIGHT]: yk+=2.5*sens
        if k[pygame.K_UP]: pk+=80*sens
        if k[pygame.K_DOWN]: pk-=80*sens
        ctrl.rotate(mr[0]*sens*dt+yk*dt, -mr[1]*sens*80*dt+pk*dt, dt)

        frame = Frame(player=ctrl.player_view(), walls=grid, entities=list(entities), colors=colors, fov=80, ray_count=300, fog=FogConfig(enabled=fog_on), minimap_config=mm_cfg)
        s=pygame.display.get_surface()
        if s is None: continue
        render(frame, s)

        if mm and mm_granted:
            ep=[(e.x,e.y,(255,100,100)) for e in entities]
            wc={int(k):tuple(wd.color) if wd and wd.color else(100,100,150) for k,wd in colors.walls.items()}
            draw_minimap(s, grid, ctrl.x, ctrl.y, ctrl.angle, ep, wall_colors=wc)
        # ── HUD: persistent inventory (top-left) ──
        if hasattr(run, '_inventory') and run._inventory:
            inv_font = chinese_font(20)
            y = 10
            for label, count in sorted(run._inventory.items()):
                surf = inv_font.render(f"{label}: {count}", True, (220, 220, 255))
                s.blit(surf, (10, y))
                y += 22
        pygame.display.flip()

    pygame.mouse.set_visible(True); pygame.quit()

if __name__=="__main__":
    _last = os.path.join(os.path.dirname(__file__), "examples", ".last_map")
    if len(sys.argv) > 1:
        p = sys.argv[1]
    elif os.path.isfile(_last):
        try:
            with open(_last) as f:
                p = f.read().strip() or "examples/demo_metaverse.json"
        except: p = "examples/demo_metaverse.json"
    else:
        p = "examples/demo_metaverse.json"
    if not os.path.isabs(p): p = os.path.join(os.path.dirname(__file__), p)
    run(p)
