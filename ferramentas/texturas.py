"""Gera pergaminho e rolos com aparência realista (procedural, sem imagens de terceiros)."""
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

rng = np.random.default_rng(11)


def ruido(h, w, escala, oitavas=5, persist=0.55, semente=None):
    g = np.random.default_rng(semente)
    total = np.zeros((h, w))
    amp, freq, soma = 1.0, 1.0, 0.0
    for _ in range(oitavas):
        sh, sw = max(2, int(h / escala * freq)) + 1, max(2, int(w / escala * freq)) + 1
        base = g.random((sh, sw))
        camada = ndimage.zoom(base, (h / sh * 1.0001, w / sw * 1.0001), order=3)[:h, :w]
        total += camada * amp
        soma += amp
        amp *= persist
        freq *= 2
    t = total / soma
    return (t - t.min()) / (t.max() - t.min() + 1e-9)


def pergaminho(w, h, semente=1, borda_irregular=True, queimado=0.55):
    s = semente
    # cor base: varia entre creme e ocre
    grande = ruido(h, w, 260, 4, 0.5, s)
    medio = ruido(h, w, 70, 4, 0.5, s + 1)
    fino = ruido(h, w, 6, 2, 0.5, s + 2)
    fibras = ndimage.gaussian_filter(np.random.default_rng(s + 3).random((h, w)), (0.6, 7))
    fibras = (fibras - fibras.mean()) / (fibras.std() + 1e-9)

    claro = np.array([243, 228, 192], float)
    escuro = np.array([196, 160, 104], float)
    t = 0.55 * grande + 0.3 * medio + 0.15 * fino
    t = np.clip((t - 0.25) * 1.6, 0, 1)
    img = claro * (1 - t[..., None] * 0.55) + escuro * (t[..., None] * 0.55)
    img += fibras[..., None] * 3.2
    img += (fino[..., None] - 0.5) * 10

    # manchas de umidade (anéis)
    manchas = ruido(h, w, 120, 3, 0.6, s + 4)
    m = ndimage.gaussian_filter(np.clip((manchas - 0.58) * 3, 0, 1), 6)
    anel = ndimage.gaussian_filter(np.clip(1 - np.abs(manchas - 0.62) * 25, 0, 1), 1.5) * 0.25
    img -= (m[..., None] * np.array([10, 16, 24])) + anel[..., None] * np.array([12, 18, 24])
    # sujeira/desgaste fino espalhado
    sujo = np.clip((ruido(h, w, 3, 2, 0.5, s + 8) - 0.78) * 4, 0, 1)
    img -= sujo[..., None] * np.array([25, 30, 34])

    # máscara com borda rasgada/gasta
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.minimum.reduce([xx, w - 1 - xx, yy, h - 1 - yy]).astype(float)
    if borda_irregular:
        irreg = ruido(h, w, 22, 4, 0.6, s + 5) * 14 + ruido(h, w, 4, 2, 0.5, s + 6) * 4
    else:
        irreg = np.zeros((h, w))
    d = dist - irreg
    alfa = np.clip(d / 1.5, 0, 1)

    # bordas escurecidas/queimadas
    q = np.clip(1 - d / (min(w, h) * 0.16), 0, 1) ** 1.6
    q2 = np.clip(1 - d / 10, 0, 1)
    img = img * (1 - q[..., None] * 0.38 * queimado) - q2[..., None] * np.array([40, 55, 70]) * queimado
    img = np.clip(img, 0, 255)

    out = np.dstack([img, alfa * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def rolo(w, h, semente=2):
    """Rolo de papel enrolado: cilindro com sombreamento e espiral visível nas pontas."""
    papel = np.asarray(pergaminho(w, h, semente, borda_irregular=False, queimado=0.0)).astype(float)
    yy = np.linspace(-1, 1, h)[:, None]
    cil = np.sqrt(np.clip(1 - yy ** 2, 0, 1))
    luz = 0.28 + 0.62 * cil ** 0.7 + 0.22 * np.clip(-yy, 0, 1) * cil   # luz vindo de cima
    voltas = 0.5 + 0.5 * np.sin(np.linspace(0, 5 * np.pi, h) + 0.6)[:, None]
    rgb = papel[..., :3] * np.array([0.92, 0.85, 0.74]) * luz[..., None] * (0.94 + 0.06 * voltas[..., None])
    # desgaste mais escuro perto das pontas
    xs = np.linspace(0, 1, w)[None, :]
    pontas = np.clip(1 - np.minimum(xs, 1 - xs) / 0.06, 0, 1)
    rgb *= (1 - 0.25 * pontas[..., None])
    ew = max(6, int(h * 0.36))
    out = np.zeros((h, w + ew, 4))
    out[:, ew // 2:ew // 2 + w, :3] = rgb
    out[:, ew // 2:ew // 2 + w, 3] = 255 * (np.abs(yy) < 0.985)
    # elipses das pontas com a espiral do papel
    ey, ex = np.mgrid[0:h, 0:ew]
    cy, cx = (h - 1) / 2, (ew - 1) / 2
    ny, nx = (ey - cy) / (h / 2), (ex - cx) / (ew / 2)
    r = np.sqrt(nx ** 2 + ny ** 2)
    ang = np.arctan2(ny, nx)
    espiral = 0.5 + 0.5 * np.sin(r * 22 - ang * 1.0)
    base = np.array([214, 186, 138]) * (0.62 + 0.3 * espiral[..., None]) * (1 - 0.35 * r[..., None])
    base[r < 0.18] = [70, 48, 26]
    tampa = np.zeros((h, ew, 4))
    tampa[..., :3] = np.clip(base, 0, 255)
    tampa[..., 3] = 255 * (r <= 1)
    for x0 in (0, w):
        reg = out[:, x0:x0 + ew]
        m = tampa[..., 3:4] / 255
        reg[...] = tampa * m + reg * (1 - m)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def sombra(img, desloc=(0, 8), raio=10, opac=150):
    a = img.split()[3].filter(ImageFilter.GaussianBlur(raio))
    a = a.point(lambda v: v * opac // 255)
    base = Image.new("RGBA", (img.width + 40, img.height + 40), (0, 0, 0, 0))
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    base.paste(preto, (20 + desloc[0], 20 + desloc[1]), a)
    base.alpha_composite(img, (20, 20))
    return base


def cartao(w=310, h=128, semente=1):
    """Pergaminho entreaberto: papel no meio e dois rolos."""
    rh = 28
    papel = pergaminho(w - 20, h - rh, semente)
    r1 = rolo(w + 4, rh, semente + 20)
    r2 = rolo(w + 4, rh, semente + 30)
    tela = Image.new("RGBA", (w + 24, h + 10), (0, 0, 0, 0))
    # sombra dos rolos sobre o papel
    tela.alpha_composite(papel, (22, rh // 2 + 5))
    arr = np.asarray(tela).astype(float)
    ys = np.arange(arr.shape[0])[:, None]
    somb = np.clip(1 - np.abs(ys - (rh + 5)) / 16, 0, 1) * 0.35 + np.clip(1 - np.abs(ys - (h - rh + 5 + rh // 2 - rh // 2)) / 16, 0, 1) * 0.35
    arr[..., :3] *= (1 - somb[..., None])
    tela = Image.fromarray(arr.astype(np.uint8), "RGBA")
    tela.alpha_composite(r1, ((w + 24 - r1.width) // 2, 5))
    tela.alpha_composite(r2, ((w + 24 - r2.width) // 2, h - rh + 5))
    return sombra(tela, (2, 7), 9, 170)


if __name__ == "__main__":
    import sys
    destino = sys.argv[1] if len(sys.argv) > 1 else "."
    for i in range(4):
        cartao(310, 150, semente=i * 7 + 1).save(f"{destino}/cartao{i}.png")
    cartao(320, 330, semente=41).save(f"{destino}/cartao_meio.png")
    f = pergaminho(1240, 660, semente=5)
    folha = Image.new("RGBA", (1320, 730), (0, 0, 0, 0))
    folha.alpha_composite(f, (40, 30))
    r = rolo(1262, 40, 61)
    folha.alpha_composite(r, ((1320 - r.width) // 2, 8))
    folha.alpha_composite(rolo(1262, 40, 71), ((1320 - r.width) // 2, 676))
    sombra(folha, (0, 10), 14, 190).save(f"{destino}/folha.png")
    print("ok")

def gerar_extra(destino):
    cartao(360, 520, semente=53).save(f"{destino}/folha_alta.png")
