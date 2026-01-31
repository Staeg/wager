"""Generate simple pixel art sprites."""

from PIL import Image
import os

SPRITE_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(SPRITE_DIR, exist_ok=True)

T = (0, 0, 0, 0)  # transparent


def make_footman():
    """16x16 pixel art: armored melee soldier with sword and shield."""
    B = (30, 30, 30, 255)
    BL = (60, 100, 200, 255)  # blue armor
    BD = (40, 70, 150, 255)  # dark blue
    S = (180, 180, 190, 255)  # silver/steel
    SK = (220, 180, 140, 255)  # skin
    BR = (100, 70, 40, 255)  # brown

    pixels = [
        [T, T, T, T, T, T, S, S, S, S, T, T, T, T, T, T],
        [T, T, T, T, T, S, B, B, B, B, S, T, T, T, T, T],
        [T, T, T, T, T, SK, SK, SK, SK, SK, SK, T, T, T, T, T],
        [T, T, T, T, T, SK, B, SK, SK, B, SK, T, T, T, T, T],
        [T, T, T, T, T, SK, SK, SK, SK, SK, SK, T, T, T, T, T],
        [T, T, T, T, T, T, SK, SK, SK, SK, T, T, T, T, T, T],
        [T, T, S, S, BL, BL, BL, BL, BL, BL, BL, BL, T, T, T, T],
        [T, T, S, S, BD, BL, BL, BL, BL, BL, BL, BD, S, T, T, T],
        [T, T, S, S, BD, BL, BL, S, BL, BL, BL, BD, S, T, T, T],
        [T, T, S, S, BD, BL, BL, BL, BL, BL, BL, BD, S, T, T, T],
        [T, T, S, S, T, BD, BL, BL, BL, BL, BD, T, S, T, T, T],
        [T, T, T, T, T, T, BD, BL, BL, BD, T, T, S, T, T, T],
        [T, T, T, T, T, T, BR, T, T, BR, T, T, T, T, T, T],
        [T, T, T, T, T, T, BR, T, T, BR, T, T, T, T, T, T],
        [T, T, T, T, T, BR, BR, T, T, BR, BR, T, T, T, T, T],
        [T, T, T, T, T, B, B, T, T, B, B, T, T, T, T, T],
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
    R = (200, 60, 60, 255)  # red tunic
    RD = (150, 40, 40, 255)  # dark red
    SK = (220, 180, 140, 255)  # skin
    BR = (100, 70, 40, 255)  # brown
    BW = (140, 100, 50, 255)  # bow wood
    G = (60, 60, 60, 255)  # grey string

    pixels = [
        [T, T, T, T, T, T, T, BR, BR, T, T, T, T, T, T, T],
        [T, T, T, T, T, T, SK, SK, SK, SK, T, T, T, T, T, T],
        [T, T, T, T, T, SK, SK, SK, SK, SK, SK, T, T, T, T, T],
        [T, T, T, T, T, SK, B, SK, SK, B, SK, T, T, T, T, T],
        [T, T, T, T, T, SK, SK, SK, SK, SK, SK, T, T, T, T, T],
        [T, T, T, T, T, T, SK, SK, SK, SK, T, T, T, T, T, T],
        [T, T, T, T, R, R, R, R, R, R, R, T, T, T, T, T],
        [T, T, BW, T, RD, R, R, R, R, R, RD, SK, T, T, T, T],
        [T, BW, T, G, RD, R, R, R, R, R, RD, T, SK, T, T, T],
        [T, T, BW, T, RD, R, R, R, R, R, RD, T, T, T, T, T],
        [T, T, T, BW, T, RD, R, R, R, RD, T, T, T, T, T, T],
        [T, T, T, T, T, T, RD, R, RD, T, T, T, T, T, T, T],
        [T, T, T, T, T, T, BR, T, T, BR, T, T, T, T, T, T],
        [T, T, T, T, T, T, BR, T, T, BR, T, T, T, T, T, T],
        [T, T, T, T, T, BR, BR, T, T, BR, BR, T, T, T, T, T],
        [T, T, T, T, T, B, B, T, T, B, B, T, T, T, T, T],
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

    # --- Heroes ---
    def make_hero(name, main_color, accent_color):
        """16x16 hero with crown; colors are (R,G,B,A)."""
        B = (30, 30, 30, 255)
        SK = (220, 180, 140, 255)
        CROWN = (240, 210, 40, 255)
        MC = main_color
        AC = accent_color
        pixels = [
            [T, T, T, T, T, CROWN, T, CROWN, T, CROWN, T, T, T, T, T, T],
            [T, T, T, T, CROWN, CROWN, CROWN, CROWN, CROWN, CROWN, T, T, T, T, T, T],
            [T, T, T, T, T, SK, SK, SK, SK, SK, T, T, T, T, T, T],
            [T, T, T, T, T, SK, B, SK, SK, B, SK, T, T, T, T, T],
            [T, T, T, T, T, SK, SK, SK, SK, SK, SK, T, T, T, T, T],
            [T, T, T, T, T, T, SK, SK, SK, SK, T, T, T, T, T, T],
            [T, T, T, T, MC, MC, MC, MC, MC, MC, MC, T, T, T, T, T],
            [T, T, T, T, AC, MC, MC, MC, MC, MC, AC, T, T, T, T, T],
            [T, T, T, T, AC, MC, MC, MC, MC, MC, AC, T, T, T, T, T],
            [T, T, T, T, AC, MC, MC, MC, MC, MC, AC, T, T, T, T, T],
            [T, T, T, T, T, AC, MC, MC, MC, AC, T, T, T, T, T, T],
            [T, T, T, T, T, T, AC, MC, AC, T, T, T, T, T, T, T],
            [T, T, T, T, T, T, B, T, T, B, T, T, T, T, T, T],
            [T, T, T, T, T, T, B, T, T, B, T, T, T, T, T, T],
            [T, T, T, T, T, B, B, T, T, B, B, T, T, T, T, T],
            [T, T, T, T, T, B, B, T, T, B, B, T, T, T, T, T],
        ]
        img = Image.new("RGBA", (16, 16))
        for y, row in enumerate(pixels):
            for x, c in enumerate(row):
                img.putpixel((x, y), c)
        img = img.resize((32, 32), Image.NEAREST)
        img.save(os.path.join(SPRITE_DIR, f"{name.lower()}.png"))

    # Faction palettes
    CUST_MAIN = (210, 170, 40, 255)
    CUST_ACC = (150, 110, 20, 255)
    WEAV_MAIN = (120, 90, 200, 255)
    WEAV_ACC = (70, 50, 130, 255)
    ART_MAIN = (120, 120, 120, 255)
    ART_ACC = (60, 60, 60, 255)
    PUR_MAIN = (210, 70, 70, 255)
    PUR_ACC = (140, 40, 40, 255)

    make_hero("Watcher", CUST_MAIN, CUST_ACC)
    make_hero("Neophyte", CUST_MAIN, CUST_ACC)
    make_hero("Accursed", CUST_MAIN, CUST_ACC)
    make_hero("Enchantress", WEAV_MAIN, WEAV_ACC)
    make_hero("Prodigy", WEAV_MAIN, WEAV_ACC)
    make_hero("Scholar", WEAV_MAIN, WEAV_ACC)
    make_hero("Outcast", ART_MAIN, ART_ACC)
    make_hero("Mercenary", ART_MAIN, ART_ACC)
    make_hero("Tactician", ART_MAIN, ART_ACC)
    make_hero("Maiden", PUR_MAIN, PUR_ACC)
    make_hero("Aspirant", PUR_MAIN, PUR_ACC)
    make_hero("Apostle", PUR_MAIN, PUR_ACC)
    print("Sprites saved to assets/")
