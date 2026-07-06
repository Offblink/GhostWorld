"""Test: editor → save → runner round trip."""
import sys, os, tempfile
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from editor.window import EditorWindow

w = EditorWindow(tempfile.gettempdir())
w.state.grid[3,3] = 5; w.state.grid[7,7] = 3
w.state.entities = [{'x':4.5,'y':4.5,'texture':'','size_3d':150,'width_3d':0.2,'anim':{},'occlusion':'center'}]
w.state.modified = True
p = os.path.join(tempfile.gettempdir(), 'test_runner.json')
w._save_to(p)
print('Saved:', p)

# Load as runner would
import pygame; pygame.init()
from ghostengine import load_raw, build_colors, build_entities, FogConfig, Frame, PlayerView, EntityView, ColorConfig, FirstPersonController, render
import numpy as np

raw = load_raw(p)
colors = build_colors(raw, None)
ents = build_entities(raw, None)
grid = np.array(raw['grid'], dtype=int)
ps = raw.get('player_spawn', {'x':7.5,'y':7.5,'angle':0})

print(f'grid[3,3]={grid[3,3]} grid[7,7]={grid[7,7]} entities={len(ents)}')
assert grid[3,3]==5, f'FAIL: grid[3,3]={grid[3,3]}'
assert grid[7,7]==3, f'FAIL: grid[7,7]={grid[7,7]}'

ctrl = FirstPersonController(x=ps['x'], y=ps['y'], angle=ps.get('angle',0), pitch=0, walls=grid)
frame = Frame(player=ctrl.player_view(), walls=grid, entities=list(ents), colors=colors, fov=80, ray_count=100)
surf = pygame.Surface((400,300))
render(frame, surf)
print('Rendered OK')
os.unlink(p)
print('PASS: full round-trip')
