from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient background #22C55E → #16A34A
    top_c = (34, 197, 94)
    bot_c = (22, 163, 74)
    for y in range(size):
        t = y / max(size - 1, 1)
        c = tuple(int(top_c[i] + (bot_c[i] - top_c[i]) * t) for i in range(3))
        draw.line([(0, y), (size - 1, y)], fill=c + (255,))

    # Rounded corners mask
    radius = int(size * 0.22)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    img.putalpha(mask)
    draw = ImageDraw.Draw(img)

    # White arc (demi-cercle du haut = route / chemin)
    m = size * 0.12
    arc_w = max(3, int(size * 0.042))
    draw.arc(
        [m, m, size - m, size - m],
        start=205, end=335,
        fill=(255, 255, 255, 210),
        width=arc_w,
    )

    # "G" bold centré
    fsize = int(size * 0.50)
    font = None
    for path in [
        "C:/Windows/Fonts/ArialBD.ttf",
        "C:/Windows/Fonts/ariblk.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        try:
            font = ImageFont.truetype(path, fsize)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    bb = draw.textbbox((0, 0), "G", font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx = (size - tw) / 2 - bb[0]
    ty = (size - th) / 2 - bb[1] + size * 0.03   # légèrement vers le bas pour équilibre visuel

    # Ombre douce sous le G
    draw.text((tx + size * 0.018, ty + size * 0.018), "G",
              fill=(0, 0, 0, 40), font=font)
    # G blanc
    draw.text((tx, ty), "G", fill=(255, 255, 255, 255), font=font)

    return img


os.makedirs("frontend", exist_ok=True)
icons = [
    (180, "frontend/apple-touch-icon.png"),
    (192, "frontend/icon-192.png"),
    (512, "frontend/icon-512.png"),
]
for size, path in icons:
    make_icon(size).save(path, "PNG")
    print(f"OK {path}  ({size}x{size})")

print("Icones generees.")
