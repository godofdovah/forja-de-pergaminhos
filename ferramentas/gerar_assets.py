"""Gera todas as imagens da interface em assets/. Rode: python ferramentas/gerar_assets.py"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from texturas import pergaminho, rolo, ruido, sombra  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
PAPEL = np.array([241, 228, 196], float)   # cor lisa do centro (os widgets usam esta cor de fundo)


def salvar(img, nome):
    img.save(os.path.join(RAIZ, nome), optimize=True)


def papel_grande():
    w, h = 1600, 1000
    p = np.asarray(pergaminho(w, h, semente=5)).astype(float)
    yy, xx = np.mgrid[0:h, 0:w]
    dx = np.minimum(xx, w - 1 - xx) / (w * 0.5)
    dy = np.minimum(yy, h - 1 - yy) / (h * 0.5)
    centro = np.clip(np.minimum(dx / 0.045, dy / 0.07), 0, 1) ** 1.3   # 0 na borda, 1 no miolo
    p[..., :3] = p[..., :3] * (1 - centro[..., None]) + PAPEL * centro[..., None]
    salvar(Image.fromarray(np.clip(p, 0, 255).astype(np.uint8), "RGBA"), "papel.png")
    salvar(rolo(1700, 44, 61), "rolo.png")


def cartao(w, h, semente, brilho=False):
    rh = 28
    papel = pergaminho(w - 20, h - rh, semente)
    arr = np.asarray(papel).astype(float)
    hh, ww = arr.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww]
    dx = np.minimum(xx, ww - 1 - xx) / (ww * 0.5)
    cen = np.clip(dx / 0.25, 0, 1) ** 1.2
    arr[..., :3] = arr[..., :3] * (1 - cen[..., None] * 0.55) + PAPEL * cen[..., None] * 0.55
    papel = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    r1, r2 = rolo(w + 4, rh, semente + 20), rolo(w + 4, rh, semente + 30)
    tela = Image.new("RGBA", (w + 24, h + 10), (0, 0, 0, 0))
    tela.alpha_composite(papel, (22, rh // 2 + 5))
    a = np.asarray(tela).astype(float)
    ys = np.arange(a.shape[0])[:, None]
    s = np.clip(1 - np.abs(ys - (rh + 5)) / 14, 0, 1) * 0.3 + np.clip(1 - np.abs(ys - (h - rh + 5)) / 14, 0, 1) * 0.3
    a[..., :3] *= (1 - s[..., None])
    tela = Image.fromarray(a.astype(np.uint8), "RGBA")
    tela.alpha_composite(r1, ((w + 24 - r1.width) // 2, 5))
    tela.alpha_composite(r2, ((w + 24 - r2.width) // 2, h - rh + 5))
    if not brilho:
        return sombra(tela, (2, 5), 4, 120)
    # brilho dourado em volta
    alfa = tela.split()[3].filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(6))
    base = Image.new("RGBA", (tela.width + 40, tela.height + 40), (0, 0, 0, 0))
    ouro = Image.new("RGBA", tela.size, (245, 195, 95, 255))
    base.paste(ouro, (20, 20), alfa.point(lambda v: int(v * 0.85)))
    clar = Image.fromarray(np.clip(np.asarray(tela).astype(float) * [1.05, 1.05, 1.03, 1], 0, 255).astype(np.uint8), "RGBA")
    base.alpha_composite(clar, (20, 20))
    return base


def selo(cor, tam=50):
    S = tam * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = np.array(cor, float)
    yy, xx = np.mgrid[0:S, 0:S]
    cx = cy = S / 2
    ang = np.arctan2(yy - cy, xx - cx)
    raio = S * 0.46 * (1 + 0.035 * np.sin(ang * 7) + 0.02 * np.sin(ang * 13 + 1))
    d = np.hypot(xx - cx, yy - cy)
    dentro = d < raio
    luz = np.clip(1.25 - np.hypot(xx - S * 0.36, yy - S * 0.32) / (S * 0.75), 0.35, 1.25)
    aro = np.clip(1 - np.abs(d - raio * 0.78) / (S * 0.03), 0, 1)
    rgb = c * luz[..., None] * (1 - 0.25 * aro[..., None]) + 255 * 0.08 * aro[..., None]
    rgb += (ruido(S, S, 30, 3, 0.5, 3)[..., None] - 0.5) * 14
    arr = np.zeros((S, S, 4))
    arr[..., :3] = np.clip(rgb, 0, 255)
    arr[..., 3] = dentro * 255
    im = Image.fromarray(arr.astype(np.uint8), "RGBA").resize((tam, tam), Image.LANCZOS)
    return sombra(im, (1, 2), 2, 160).crop((17, 17, tam + 24, tam + 24))


def madeira(w, h, tom=1.0, semente=3):
    veio = ruido(h, w, 3, 3, 0.5, semente)
    long_ = np.asarray(Image.fromarray((ruido(h, w // 6 + 2, 2, 3, 0.6, semente + 1) * 255).astype(np.uint8)).resize((w, h))) / 255
    yy = np.linspace(-1, 1, h)[:, None]
    luz = 1.08 - 0.25 * yy
    base = np.array([128, 86, 44]) * tom
    rgb = base * luz[..., None] * (0.8 + 0.25 * long_[..., None] + 0.1 * veio[..., None])
    return rgb


def tabua(w=150, h=38, estado="normal"):
    tom = {"normal": 1.0, "hover": 1.15, "pressed": 0.85}[estado]
    rgb = madeira(w, h, tom)
    arr = np.zeros((h, w, 4))
    arr[..., :3] = np.clip(rgb, 0, 255)
    arr[..., 3] = 255
    im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=(52, 32, 12), width=2)
    d.line((2, 2, w - 3, 2), fill=(214, 170, 110), width=1)
    for x in (7, w - 8):  # cravos
        for y in (7, h - 8):
            d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(70, 52, 30), outline=(170, 140, 90))
    return im


def acao(w=300, h=54, estado="normal"):
    S = 3
    W, H = w * S, h * S
    tom = {"normal": 1.0, "hover": 1.12, "pressed": 0.88}[estado]
    yy, xx = np.mgrid[0:H, 0:W]
    luz = np.clip(1.3 - np.hypot((xx - W * 0.3) / W, (yy - H * 0.25) / H * 0.6) * 1.1, 0.45, 1.3) * tom
    base = np.array([160, 36, 30])
    rgb = base * luz[..., None] + (ruido(H, W, 40, 3, 0.5, 9)[..., None] - 0.5) * 14
    arr = np.zeros((H, W, 4))
    arr[..., :3] = np.clip(rgb, 0, 255)
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, W - 1, H - 1), H // 2, fill=255)
    arr[..., 3] = np.asarray(mask)
    im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((5 * S, 5 * S, W - 5 * S, H - 5 * S), H // 2 - 5 * S, outline=(110, 18, 14), width=2 * S)
    im = im.resize((w, h), Image.LANCZOS)
    return im


def chave(modo):
    S = 4
    w, h = 86 * S, 38 * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fundo = (40, 37, 44) if modo == "escuro" else (226, 207, 168)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=fundo, outline=(176, 138, 69), width=2 * S)
    bx = w - h + 3 * S if modo == "escuro" else 3 * S
    r = h - 6 * S
    yy, xx = np.mgrid[0:r, 0:r]
    luz = np.clip(1.25 - np.hypot(xx - r * 0.35, yy - r * 0.3) / (r * 0.8), 0.4, 1.25)
    bola = np.zeros((r, r, 4))
    bola[..., :3] = np.clip(np.array([214, 168, 70]) * luz[..., None], 0, 255)
    bola[..., 3] = (np.hypot(xx - r / 2, yy - r / 2) < r / 2) * 255
    im.alpha_composite(Image.fromarray(bola.astype(np.uint8), "RGBA"), (bx, 3 * S))
    return im.resize((86, 38), Image.LANCZOS)


def fundo(modo):
    w, h = 1920, 1200
    if modo == "escuro":
        n = ruido(h, w, 220, 4, 0.5, 21) * 0.6 + ruido(h, w, 6, 2, 0.5, 22) * 0.4
        base = np.array([30, 29, 34]) + (n[..., None] - 0.5) * 26
        yy, xx = np.mgrid[0:h, 0:w]
        vin = np.clip(1 - np.hypot((xx - w / 2) / w, (yy - h * 0.3) / h) * 0.9, 0.55, 1)
        rgb = base * vin[..., None]
    else:
        n = ruido(h, w, 260, 4, 0.5, 31) * 0.7 + ruido(h, w, 5, 2, 0.5, 32) * 0.3
        base = np.array([232, 218, 188]) + (n[..., None] - 0.5) * 30
        yy, xx = np.mgrid[0:h, 0:w]
        vin = np.clip(1.04 - np.hypot((xx - w / 2) / w, (yy - h * 0.3) / h) * 0.35, 0.82, 1.04)
        rgb = base * vin[..., None]
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").save(
        os.path.join(RAIZ, f"fundo_{modo}.jpg"), quality=86)


CORES_SELO = {"vermelho": (178, 44, 38), "azul": (48, 86, 160), "verde": (44, 120, 70),
              "laranja": (196, 92, 40), "roxo": (120, 70, 156), "ouro": (196, 150, 50), "preto": (62, 58, 66)}

if __name__ == "__main__":
    os.makedirs(RAIZ, exist_ok=True)
    papel_grande()
    for i in range(4):
        salvar(cartao(280, 140, i * 7 + 1), f"cartao{i}.png")
        salvar(cartao(280, 140, i * 7 + 1, brilho=True), f"cartao{i}_brilho.png")
    for nome, cor in CORES_SELO.items():
        salvar(selo(cor, 46), f"selo_{nome}.png")
        salvar(selo(cor, 34), f"selo_{nome}_p.png")
    for e in ("normal", "hover", "pressed"):
        salvar(tabua(estado=e), f"tabua_{e}.png")
        salvar(acao(estado=e), f"acao_{e}.png")
    for m in ("escuro", "claro"):
        salvar(chave(m), f"chave_{m}.png")
        fundo(m)
    print("assets ok")
