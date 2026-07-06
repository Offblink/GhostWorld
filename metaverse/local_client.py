"""Local client — same-process, no-network connection to server."""
from __future__ import annotations
import asyncio, math, os, sys, time, numpy as np, pygame
from ghostengine import Frame, PlayerView, EntityView, ColorConfig, WallDef, FogConfig, render, TextureLoader, load_raw, build_colors, draw_minimap
from ._shared import fix_ime, chinese_font, process_agent_command


class LocalClient:
    def __init__(self, ws, ctx, avatar_name, map_path, texture=""):
        self.ws = ws; self.ctx = ctx; self.avatar_name = avatar_name; self.map_path = map_path; self._texture = texture
        from metaverse.server import handle_message, _build_snapshot
        self._handle_message = handle_message; self._build_snapshot = _build_snapshot
        self.entities = []; self.grid = np.zeros((1,1), dtype=int); self.colors = None; self.loader = None
        self.player_x = 0.0; self.player_y = 0.0; self.player_angle = 0.0; self.player_pitch = 0.0
        self._inventory = []
        self.sens = 2.5; self.fullscreen = False; self.show_minimap = True; self._flashlight = True; self.running = True
        self._agent_x = self._agent_y = self._agent_angle = None
        self._last_chat = []
        self._dialogue_text = ""; self._dialogue_time = 0.0


    def _init_pygame(self):
        # fix_ime() disabled — let pygame.TEXTINPUT handle IME
        pygame.init()
        self.screen = pygame.display.set_mode((1068,801), pygame.RESIZABLE)
        pygame.display.set_caption(f"GhostEngine Metaverse — {self.avatar_name}")
        pygame.event.set_grab(True); pygame.mouse.set_visible(False)
        self.W, self.H = 1068, 801
        self._reload_map_assets()

    def _reload_map_assets(self):
        raw = load_raw(self.ws.map_path); _bd = os.path.dirname(os.path.abspath(self.ws.map_path))
        assets = os.path.join(_bd, "assets")
        self.loader = TextureLoader(assets if os.path.isdir(assets) else _bd)
        self.colors = build_colors(raw, self.loader); self.grid = np.array(raw["grid"], dtype=int).T

    def _apply_snapshot(self, data):
        avatars = data.get("avatars",{}); remote = data.get("remote_avatars",{}); items = data.get("items",{})
        me = avatars.get(self.avatar_name) or remote.get(self.avatar_name)
        if me: self.player_x, self.player_y, self.player_angle = me["x"], me["y"], me["facing"]
        # sync grid with server (edit_map may have changed it)
        if hasattr(self, 'ws') and self.ws is not None:
            if self.grid.shape != self.ws.grid.shape or not (self.grid == self.ws.grid).all():
                self.grid = self.ws.grid.copy()
        # merge snapshot colors (from edit_map set_color)
        sc = data.get("colors", {})
        if sc and self.colors:
            for k in ("sky_top", "sky_bottom", "floor"):
                if k in sc: setattr(self.colors, k, tuple(sc[k]))
            if "walls" in sc:
                for wk, wv in sc["walls"].items():
                    if isinstance(wv, dict) and "color" in wv:
                        self.colors.walls[int(wk)] = WallDef(color=tuple(wv["color"]))
        self._inventory = me.get("inventory", []) if me else []
        # determine which map this client is on
        my_map = me.get("current_map") if me else ""
        if not my_map:
            my_map = os.path.basename(self.ws.map_path)
        self.entities = []
        agent_seen = False
        for aid, av in avatars.items():
            if aid == self.avatar_name: continue
            av_map = av.get("current_map") or os.path.basename(self.ws.map_path)
            if av_map != my_map:
                continue
            self._agent_x, self._agent_y, self._agent_angle = av["x"], av["y"], av.get("facing", 0)
            agent_seen = True
            self.entities.append(EntityView(x=av["x"], y=av["y"], texture=self._load_tex(av.get("texture_path","")),
                kind="avatar", name=av.get("name",aid), size_3d=150, width_3d=0.2, facing=av.get("facing",0)))
        if not agent_seen:
            self._agent_x = self._agent_y = self._agent_angle = None
        for iid, item in items.items():
            # filter items to only show those on the avatar's current map
            if item.get("map_name") and item["map_name"] != my_map:
                continue
            self.entities.append(EntityView(x=item["x"], y=item["y"], texture=self._load_tex(item.get("texture_path","")),
                kind=item.get("kind","item"), size_3d=item.get("size_3d",150), width_3d=item.get("width_3d",0.2),
                anim=item.get("anim",{}), occlusion=item.get("occlusion","center"), visible=item.get("visible",True),
                pickup=item.get("pickup",False), pickup_label=item.get("pickup_label",""),
                capture_for=item.get("capture_for",""), portal_target=item.get("portal_target"), dialogue=item.get("dialogue",""),
                name=item.get("name",""), facing=item.get("facing",0)))
    def _load_tex(self, path):
        if not path or not self.loader: return None
        try: ext = os.path.splitext(path)[1].lower(); return self.loader.load_frames(path) if ext==".gif" else self.loader.load(path)
        except: return None

    def _build_frame(self):
        # sync grid from server every frame (edit_map may have changed it)
        if hasattr(self, 'ws') and self.ws is not None:
            if not (self.grid == self.ws.grid).all():
                self.grid = self.ws.grid.copy()
        ents = list(self.entities)
        return Frame(player=PlayerView(x=self.player_x, y=self.player_y, angle=self.player_angle, pitch=self.player_pitch),
            walls=self.grid, entities=ents, colors=self.colors or ColorConfig(), fog=FogConfig(enabled=True))

    async def run(self):
        self._init_pygame()
        resp = self._handle_message(self.ws, self.avatar_name, {"type":"connect","owner":"human","texture":self._texture})
        self.player_x, self.player_y, self.player_angle = resp.get("x",0), resp.get("y",0), resp.get("facing",0)
        clock = pygame.time.Clock(); paused = False; chatting = False; chat_input = ""
        tick_counter = 0; font = chinese_font(20); big_font = chinese_font(48)

        while self.running:
            dt = clock.tick(120)/1000.0
            if dt > 0.1: dt = 0.016
            mr = (0,0)
            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.running = False
                elif e.type == pygame.KEYDOWN:
                    if chatting:
                        if e.key == pygame.K_RETURN:
                            if chat_input.strip():
                                cmd = chat_input.strip()
                                if cmd.startswith("/give "):
                                    parts = cmd[6:].strip().split()
                                    if len(parts) >= 2:
                                        self._handle_message(self.ws, self.avatar_name,
                                            {"type":"give","target":parts[0],"item_id":parts[1]})
                                else:
                                    self._handle_message(self.ws, self.avatar_name,
                                        {"type":"say","message":cmd,"channel":"global"})
                            chatting = False; chat_input = ""; pygame.event.set_grab(True); pygame.mouse.set_visible(False)
                        elif e.key == pygame.K_ESCAPE: chatting = False; chat_input = ""; pygame.event.set_grab(True); pygame.mouse.set_visible(False)
                        elif e.key == pygame.K_BACKSPACE: chat_input = chat_input[:-1]
                        continue
                elif e.type == pygame.TEXTINPUT and chatting:
                    chat_input += e.text
                    continue
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN: chatting = True; chat_input = ""; pygame.event.set_grab(False); pygame.mouse.set_visible(True); continue
                    elif e.key == pygame.K_e:
                        if not self._dialogue_text and self.entities:
                            for ent in self.entities:
                                if ent.kind == "avatar" and ent.dialogue:
                                    dist = ((self.player_x - ent.x)**2 + (self.player_y - ent.y)**2)**0.5
                                    if dist < 1.5:
                                        dx = ent.x - self.player_x; dy = ent.y - self.player_y
                                        diff = math.atan2(dy, dx) - self.player_angle
                                        while diff > math.pi: diff -= 2*math.pi
                                        while diff < -math.pi: diff += 2*math.pi
                                        if abs(diff) < math.radians(60):
                                            self._dialogue_text = ent.dialogue
                                            self._dialogue_time = 3.0
                                            break
                    if paused:
                        if e.key == pygame.K_SPACE: paused = False; pygame.event.set_grab(True); pygame.mouse.set_visible(False)
                        elif e.key == pygame.K_ESCAPE: self.running = False
                        continue
                    elif e.key == pygame.K_SPACE: paused = True; pygame.event.set_grab(False); pygame.mouse.set_visible(True)
                    elif e.key == pygame.K_f: self.fullscreen = not self.fullscreen; self.screen = pygame.display.set_mode((0,0),pygame.FULLSCREEN) if self.fullscreen else pygame.display.set_mode((self.W,self.H),pygame.RESIZABLE)
                    elif e.key == pygame.K_l: self._flashlight = not self._flashlight
                    elif e.key == pygame.K_m: self.show_minimap = not self.show_minimap
                elif e.type == pygame.MOUSEMOTION: mr = e.rel

            if paused:
                s = pygame.display.get_surface()
                if s:
                    sw, sh = s.get_size(); o = pygame.Surface((sw,sh), pygame.SRCALPHA); o.fill((0,0,0,160)); s.blit(o,(0,0))
                    txt = big_font.render("PAUSED",True,(255,255,255)); s.blit(txt, txt.get_rect(center=(sw//2, sh//2-20)))
                pygame.display.flip(); continue

            if chatting:
                # long-press backspace: 500ms initial delay, then 50ms repeat
                kp = pygame.key.get_pressed()
                if kp[pygame.K_BACKSPACE]:
                    if not hasattr(self, '_bs_acc'): self._bs_acc = 0.0; self._bs_fast = False
                    self._bs_acc += dt
                    threshold = 0.05 if self._bs_fast else 0.5
                    if self._bs_acc >= threshold:
                        if chat_input: chat_input = chat_input[:-1]
                        self._bs_acc = 0.0; self._bs_fast = True
                else:
                    self._bs_acc = 0.0; self._bs_fast = False
                frame = self._build_frame(); s = pygame.display.get_surface()
                if s:
                    render(frame, s)
                    # minimap while chatting too
                    if self.show_minimap:
                        ep=[(e.x,e.y,(255,100,100)) for e in self.entities]
                        wc={int(k):tuple(wd.color) if wd and wd.color else(100,100,150) for k,wd in self.colors.walls.items()} if self.colors else {}
                        draw_minimap(s, self.grid, self.player_x, self.player_y, self.player_angle, ep, wall_colors=wc, agent_x=self._agent_x, agent_y=self._agent_y, agent_angle=self._agent_angle, agent_flashlight=self._flashlight)
                    snapshot = self._build_snapshot(self.ws); chat = snapshot.get("chat", [])
                    if chat: self._last_chat = chat
                    now = time.time()
                    recent = [c for c in self._last_chat if now - c.get("time",0) < 10.0]
                    for i, c in enumerate(recent[-10:]):
                        txt = font.render(f"[{c['from']}] {c['message']}", True, (255,255,200))
                        s.blit(txt, (10, s.get_height() - 150 + i*18))
                    bar = pygame.Surface((s.get_width(), 30), pygame.SRCALPHA); bar.fill((0,0,0,200))
                    s.blit(bar, (0, s.get_height()-30))
                    txt = font.render(f"> {chat_input}_", True, (255,255,255)); s.blit(txt, (10, s.get_height()-25))
                pygame.display.flip(); await asyncio.sleep(0); continue

            tick_counter += 1
            if tick_counter % 6 == 0:
                from metaverse.server import _tick_loop_sync
                _tick_loop_sync(self.ctx, self.ws)
                # handle player map switch
                av = self.ws.avatars.get(self.avatar_name)
                if av and av.current_map and os.path.basename(av.current_map) != os.path.basename(self.ws.map_path) and av.current_map in self.ws.maps:
                    # save current items back to old map before switching
                    old_name = os.path.basename(self.ws.map_path)
                    if old_name in self.ws.maps:
                        self.ws.maps[old_name]["items"] = {k: type(v)(**v.__dict__) if hasattr(v, '__dict__') else v for k, v in self.ws.items.items()}
                        self.ws.maps[old_name]["grid"] = self.ws.grid.copy()
                        self.ws.maps[old_name]["colors"] = dict(self.ws.colors)
                    m = self.ws.maps[av.current_map]
                    self.ws.grid = m["grid"]
                    self.ws.items = {k: type(v)(**v.__dict__) if hasattr(v, '__dict__') else v for k, v in m["items"].items()}
                    self.ws.colors = m["colors"]
                    raw = {"grid": m["grid"].tolist(), "colors": m["colors"]}
                    self.colors = build_colors(raw, self.loader)
                    old_map = os.path.basename(self.ws.map_path)  # before update
                    target = os.path.basename(av.current_map)
                    self.ws.map_path = target
                    av.current_map = target  # track actual map, not ""
                self._apply_snapshot(self._build_snapshot(self.ws))
            self.grid = self.ws.grid.copy()
            await asyncio.sleep(0)

            k = pygame.key.get_pressed(); fw = st = 0.0
            if k[pygame.K_w]: fw += 1.0
            if k[pygame.K_s]: fw -= 1.0
            if k[pygame.K_a]: st -= 1.0
            if k[pygame.K_d]: st += 1.0

            if fw != 0 or st != 0:
                move_speed = 2.5 * dt; cos_a = math.cos(self.player_angle); sin_a = math.sin(self.player_angle)
                nx = self.player_x + (fw*cos_a - st*sin_a)*move_speed
                ny = self.player_y + (fw*sin_a + st*cos_a)*move_speed
                resp = self._handle_message(self.ws, self.avatar_name, {"type":"move","x":nx,"y":ny,"facing":self.player_angle})
                if resp.get("type") == "moved":
                    self.player_x, self.player_y = resp["x"], resp["y"]
            av = self.ws.avatars.get(self.avatar_name)
            if av: av.facing = self.player_angle

            for aid, av in self.ws.avatars.items():
                if aid == self.avatar_name: continue
                dx = self.player_x - av.x; dy = self.player_y - av.y; dist = (dx*dx+dy*dy)**0.5
                if dist < 0.5 and dist > 0.01:
                    push = (0.5 - dist) * 0.15; nx = self.player_x + (dx/dist)*push; ny = self.player_y + (dy/dist)*push
                    if self.ws.is_passable(nx, ny): self.player_x, self.player_y = nx, ny

            yk = pk = 0.0
            if k[pygame.K_LEFT]: yk -= 2.5*self.sens
            if k[pygame.K_RIGHT]: yk += 2.5*self.sens
            if k[pygame.K_UP]: pk += 80*self.sens
            if k[pygame.K_DOWN]: pk -= 80*self.sens
            self.player_angle += mr[0]*self.sens*dt + yk*dt
            self.player_pitch += (-mr[1]*self.sens*80*dt + pk*dt)
            self.player_pitch = max(-300, min(300, self.player_pitch))

            # NPC dialogue detection
            self._dialogue_npc = None
            if not self._dialogue_text:
                for e in self.entities:
                    if e.kind != "avatar" or not e.dialogue: continue
                    dist = ((self.player_x - e.x)**2 + (self.player_y - e.y)**2)**0.5
                    if dist < 1.5:
                        dx = e.x - self.player_x; dy = e.y - self.player_y
                        diff = math.atan2(dy, dx) - self.player_angle
                        while diff > math.pi: diff -= 2*math.pi
                        while diff < -math.pi: diff += 2*math.pi
                        if abs(diff) < math.radians(60):
                            self._dialogue_npc = e; break
            if self._dialogue_time > 0:
                self._dialogue_time -= dt
                if self._dialogue_time <= 0: self._dialogue_text = ""

            frame = self._build_frame(); s = pygame.display.get_surface()
            if s is None: continue
            render(frame, s)

            # ── inventory HUD (top-left) ──
            if self._inventory:
                inv_font = chinese_font(16)
                counts: dict[str, int] = {}
                for item in self._inventory:
                    label = item.get("label", item.get("id", "?"))
                    counts[label] = counts.get(label, 0) + 1
                for i, (label, count) in enumerate(counts.items()):
                    txt = inv_font.render(f"{label}: {count}", True, (200, 255, 200))
                    s.blit(txt, (10, 10 + i * 18))
            if self.show_minimap:
                ep = [(e.x,e.y,(255,100,100)) for e in self.entities]
                wc = {int(k):tuple(wd.color) if wd and wd.color else(100,100,150) for k,wd in self.colors.walls.items()} if self.colors else {}
                draw_minimap(s, self.grid, self.player_x, self.player_y, self.player_angle, ep, wall_colors=wc, agent_x=self._agent_x, agent_y=self._agent_y, agent_angle=self._agent_angle, agent_flashlight=self._flashlight)
            snapshot = self._build_snapshot(self.ws); chat = snapshot.get("chat", [])
            if chat: self._last_chat = chat
            now = time.time()
            recent = [c for c in self._last_chat if now - c.get("time",0) < 10.0]
            for i, c in enumerate(recent[-10:]):
                txt = font.render(f"[{c['from']}] {c['message']}", True, (255,255,200))
                s.blit(txt, (10, s.get_height() - 120 + i*18))

            if chatting:
                bar = pygame.Surface((s.get_width(), 30), pygame.SRCALPHA); bar.fill((0,0,0,200)); s.blit(bar, (0, s.get_height()-30))
                txt = font.render(f"> {chat_input}_", True, (255,255,255)); s.blit(txt, (10, s.get_height()-25))


            # ── NPC dialogue HUD ──
            if self._dialogue_text:
                dfont = chinese_font(28)
                sw = s.get_width()
                dsurf = dfont.render(self._dialogue_text, True, (255, 255, 200))
                bg = pygame.Surface((dsurf.get_width()+40, dsurf.get_height()+20), pygame.SRCALPHA)
                bg.fill((0,0,0,180))
                bx = (sw - bg.get_width())//2; by = s.get_height() - bg.get_height() - 60
                s.blit(bg, (bx, by)); s.blit(dsurf, (bx+20, by+10))
            if self._dialogue_time > 0:
                self._dialogue_time -= dt
                if self._dialogue_time <= 0: self._dialogue_text = ""
            # ── NPC dialogue HUD ──
            if self._dialogue_text:
                dfont = chinese_font(28)
                sw = s.get_width()
                dsurf = dfont.render(self._dialogue_text, True, (255, 255, 200))
                bg = pygame.Surface((dsurf.get_width()+40, dsurf.get_height()+20), pygame.SRCALPHA)
                bg.fill((0,0,0,180))
                bx = (sw - bg.get_width())//2; by = s.get_height() - bg.get_height() - 60
                s.blit(bg, (bx, by)); s.blit(dsurf, (bx+20, by+10))
            elif self._dialogue_npc:
                prompt = chinese_font(20)
                psurf = prompt.render("按 E 对话", True, (255, 255, 150))
                sx = (s.get_width() - psurf.get_width())//2
                s.blit(psurf, (sx, s.get_height() - 50))

            # ── map name HUD (bottom-right) ──
            map_name = os.path.basename(self.ws.map_path) if self.ws.map_path else "unknown"
            map_txt = chinese_font(14).render(map_name, True, (180, 180, 200))
            s.blit(map_txt, (s.get_width() - map_txt.get_width() - 10, s.get_height() - 25))
            pygame.display.flip()

        self._handle_message(self.ws, self.avatar_name, {"type":"disconnect"})
        pygame.mouse.set_visible(True); pygame.quit()
