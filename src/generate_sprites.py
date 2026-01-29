"""Generate simple pixel art sprites for Footman and Skirmisher."""
from PIL import Image
import os

SPRITE_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(SPRITE_DIR, exist_ok=True)

T = (0, 0, 0, 0)  # transparent

def make_footman():
    """16x16 pixel art: armored melee soldier with sword and shield."""
    W = (255, 255, 255, 255)
    B = (30, 30, 30, 255)
    BL = (60, 100, 200, 255)      # blue armor
    BD = (40, 70, 150, 255)       # dark blue
    S = (180, 180, 190, 255)      # silver/steel
    SK = (220, 180, 140, 255)     # skin
    BR = (100, 70, 40, 255)       # brown

    pixels = [
        [T,T,T,T,T,T, S, S, S, S,T,T,T,T,T,T],
        [T,T,T,T,T, S, B, B, B, B, S,T,T,T,T,T],
        [T,T,T,T,T,SK,SK,SK,SK,SK,SK,T,T,T,T,T],
        [T,T,T,T,T,SK, B,SK,SK, B,SK,T,T,T,T,T],
        [T,T,T,T,T,SK,SK,SK,SK,SK,SK,T,T,T,T,T],
        [T,T,T,T,T,T,SK,SK,SK,SK,T,T,T,T,T,T],
        [T,T, S, S,BL,BL,BL,BL,BL,BL,BL,BL,T,T,T,T],
        [T,T, S, S,BD,BL,BL,BL,BL,BL,BL,BD, S,T,T,T],
        [T,T, S, S,BD,BL,BL, S,BL,BL,BL,BD, S,T,T,T],
        [T,T, S, S,BD,BL,BL,BL,BL,BL,BL,BD, S,T,T,T],
        [T,T, S, S,T,BD,BL,BL,BL,BL,BD,T, S,T,T,T],
        [T,T,T,T,T,T,BD,BL,BL,BD,T,T, S,T,T,T],
        [T,T,T,T,T,T,BR,T,T,BR,T,T,T,T,T,T],
        [T,T,T,T,T,T,BR,T,T,BR,T,T,T,T,T,T],
        [T,T,T,T,T,BR,BR,T,T,BR,BR,T,T,T,T,T],
        [T,T,T,T,T, B, B,T,T, B, B,T,T,T,T,T],
    ]
    img = Image.new("RGBA", (16, 16))
    for y, row in enumerate(pixels):
        for x, c in enumerate(row):
            img.putpixel((x, y), c)
    img = img.resize((32, 32), Image.NEAREST)
    img.save(os.path.join(SPRITE_DIR, "footman.png"))

def make_skirmisher():
    """16x16 pixel art: light ranged unit with bow."""
    B = (30, 30, 30, 255)
    R = (200, 60, 60, 255)        # red tunic
    RD = (150, 40, 40, 255)       # dark red
    SK = (220, 180, 140, 255)     # skin
    BR = (100, 70, 40, 255)       # brown
    BW = (140, 100, 50, 255)      # bow wood
    G = (60, 60, 60, 255)         # grey string

    pixels = [
        [T,T,T,T,T,T,T,BR,BR,T,T,T,T,T,T,T],
        [T,T,T,T,T,T,SK,SK,SK,SK,T,T,T,T,T,T],
        [T,T,T,T,T,SK,SK,SK,SK,SK,SK,T,T,T,T,T],
        [T,T,T,T,T,SK, B,SK,SK, B,SK,T,T,T,T,T],
        [T,T,T,T,T,SK,SK,SK,SK,SK,SK,T,T,T,T,T],
        [T,T,T,T,T,T,SK,SK,SK,SK,T,T,T,T,T,T],
        [T,T,T,T, R, R, R, R, R, R, R,T,T,T,T,T],
        [T,T,BW,T,RD, R, R, R, R, R,RD,SK,T,T,T,T],
        [T,BW,T, G,RD, R, R, R, R, R,RD,T,SK,T,T,T],
        [T,T,BW,T,RD, R, R, R, R, R,RD,T,T,T,T,T],
        [T,T,T,BW,T,RD, R, R, R,RD,T,T,T,T,T,T],
        [T,T,T,T,T,T,RD, R,RD,T,T,T,T,T,T,T],
        [T,T,T,T,T,T,BR,T,T,BR,T,T,T,T,T,T],
        [T,T,T,T,T,T,BR,T,T,BR,T,T,T,T,T,T],
        [T,T,T,T,T,BR,BR,T,T,BR,BR,T,T,T,T,T],
        [T,T,T,T,T, B, B,T,T, B, B,T,T,T,T,T],
    ]
    img = Image.new("RGBA", (16, 16))
    for y, row in enumerate(pixels):
        for x, c in enumerate(row):
            img.putpixel((x, y), c)
    img = img.resize((32, 32), Image.NEAREST)
    img.save(os.path.join(SPRITE_DIR, "skirmisher.png"))

if __name__ == "__main__":
    make_footman()
    make_skirmisher()
    print("Sprites saved to assets/")
