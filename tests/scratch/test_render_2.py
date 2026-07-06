"""Test: does runner actually render walls from 2.json?"""
import sys, os, numpy as np, pygame
pygame.init()
from ghostengine import (
    Frame, PlayerView, EntityView, ColorConfig, WallDef,
    FirstPersonController, render,
    TextureLoader, load_raw, build_colors, build_entities,
)

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "2.json")
raw = load_raw(path)
loader = TextureLoader(os.path.dirname(path))
colors = build_colors(raw, loader)
ents = build_entities(raw, loader)
grid = np.array(raw["grid"], dtype=int)
ps = raw.get("player_spawn", {"x":7.5,"y":7.5,"angle":0})
ctrl = FirstPersonController(x=ps["x"], y=ps["y"], angle=ps.get("angle",0), pitch=0, walls=grid)
ctrl.set_screen_height(600)

frame = Frame(player=ctrl.player_view(), walls=grid, entities=list(ents), colors=colors, fov=80, ray_count=200)
surf = pygame.Surface((800,600))

# Render and check
render(frame, surf)

# Count non-sky-colored pixels (sky should be mostly bluish)
import numpy as np2
arr = pygame.surfarray.array3d(surf)
# Check if walls exist in middle columns
mid = arr[200:600, 400, :]  # vertical line in center
non_sky = sum(1 for p in mid if p[0] < 120 and p[1] < 200)  # not sky-blue
print(f"Non-sky pixels in center column: {non_sky}")

# Check a few scan lines for wall pixels  
wall_pixels = 0
for y in range(200, 500):
    r, g, b = arr[y, 400]
    if r < 120 and g < 120:  # dark wall pixel
        wall_pixels += 1
print(f"Dark wall pixels in center col: {wall_pixels}")

if wall_pixels > 10:
    print("PASS: walls are visible")
else:
    print("FAIL: no walls visible - view is empty")
    print("grid shape:", grid.shape)
    print("grid[7,7]:", grid[7,7])
    print("colors.walls:", colors.walls.keys() if colors.walls else "EMPTY")
