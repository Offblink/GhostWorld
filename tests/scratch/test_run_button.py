"""Test: editor save → runner render (walls away from spawn)."""
import sys, os, tempfile, numpy as np, pygame
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from editor.window import EditorWindow

w = EditorWindow(tempfile.gettempdir())
# Walls AWAY from spawn (2.5, 2.5)  
w.state.grid[0,0] = 5; w.state.grid[0,1] = 5; w.state.grid[1,0] = 5
w.state.grid[0,14] = 3; w.state.grid[14,0] = 3
w.state.player_spawn = (7.5, 7.5, 0.0)  # spawn in open center
w.state.modified = True

p = os.path.join(tempfile.gettempdir(), 'test_walls.json')
w._save_to(p)

pygame.init()
from ghostengine import load_raw, build_colors, build_entities, Frame, PlayerView, FirstPersonController, render

raw = load_raw(p)
colors = build_colors(raw, None); ents = build_entities(raw, None)
grid = np.array(raw['grid'], dtype=int)
ctrl = FirstPersonController(x=7.5, y=7.5, angle=0, pitch=0, walls=grid)
ctrl.set_screen_height(600)
frame = Frame(player=ctrl.player_view(), walls=grid, entities=list(ents), colors=colors, fov=80, ray_count=100)
surf = pygame.Surface((400,300))
render(frame, surf)

arr = pygame.surfarray.array3d(surf)
wp = sum(1 for x in range(30,350) for y in range(30,250) if arr[x,y,0] < 130)
print(f'Wall pixels: {wp}')
os.unlink(p)
print('PASS' if wp > 50 else f'FAIL - only {wp} wall pixels')
