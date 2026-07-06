"""Diagnostic: what does pygame see for Ctrl+R?"""
import pygame
pygame.init()
screen = pygame.display.set_mode((400, 100))
pygame.display.set_caption("Press Ctrl+R — watch console")
font = pygame.font.Font(None, 24)

running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT: running = False
        elif e.type == pygame.KEYDOWN:
            print(f"KEYDOWN: key={e.key}({pygame.key.name(e.key)}) mod={e.mod} unicode={e.unicode!r}")
            if e.key == pygame.K_r:
                if e.mod & pygame.KMOD_CTRL:
                    print("  -> Ctrl+R DETECTED")
                else:
                    print("  -> just R, no Ctrl")
    screen.fill((0,0,0))
    t = font.render("Press Ctrl+R — check console", True, (255,255,255))
    screen.blit(t, (20, 40))
    pygame.display.flip()
pygame.quit()
