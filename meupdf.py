"""
Forja de Pergaminhos — ferramentas de PDF que rodam só no seu computador.
"""
import os
import re
import sys
import json
import queue
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

PASTA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PASTA)
ASSETS = os.path.join(PASTA, "assets")


def mostrar_erro_fatal(titulo):
    """Com o programa sem janela preta, o erro vira um aviso na tela e um arquivo erro.txt."""
    detalhe = traceback.format_exc()
    try:
        with open(os.path.join(PASTA, "erro.txt"), "w", encoding="utf-8") as f:
            f.write(detalhe)
    except Exception:
        pass
    r = tk.Tk()
    r.withdraw()
    messagebox.showerror("Forja de Pergaminhos", f"{titulo}\n\n{detalhe[-1500:]}")
    r.destroy()
    sys.exit(1)


try:
    import motor  # noqa: E402
    from PIL import Image, ImageTk  # noqa: E402
except Exception:
    mostrar_erro_fatal("Faltam partes do programa. Reinstale a Forja de Pergaminhos.")

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception:
    TkinterDnD = None
    DND_FILES = None
TEM_DND = False


def carregar_fontes():
    """Registra as letras do programa só para ele mesmo (não instala nada no Windows)."""
    pasta = os.path.join(ASSETS, "fontes")
    if not os.path.isdir(pasta):
        return
    for arq in os.listdir(pasta):
        if not arq.lower().endswith(".ttf"):
            continue
        caminho = os.path.join(pasta, arq)
        if motor.EH_WINDOWS:
            try:
                import ctypes
                ctypes.windll.gdi32.AddFontResourceExW(caminho, 0x10, 0)  # FR_PRIVATE
            except Exception:
                pass


# ---------------------------------------------------------------- aparência
TIT = "Almendra"          # letra dos títulos
TXT = "Forja Texto"       # letra dos textos (Cormorant Garamond)

PAPEL = "#f1e4c4"         # cor lisa do centro do pergaminho
PAPEL_ESC = "#e4d1a7"
CAMPO = "#fbf4e2"         # fundo de listas e caixas de texto
TINTA = "#3e220a"
TINTA2 = "#5a4022"
TINTA3 = "#7d6646"
LACRE = "#8e1d1a"

# nomes antigos usados pelas ferramentas
FUNDO = PAPEL
BRANCO = CAMPO
TEXTO = TINTA
CINZA = TINTA3
DESTAQUE = LACRE

TEMAS = {
    "escuro": dict(barra="#121115", titulo="#d9b56a", sub="#a8987a", borda="#5a4a2e", fundo="#1d1c21",
                   rotulo="Modo escuro"),
    "claro": dict(barra="#dccaa5", titulo="#6b3f16", sub="#6e5638", borda="#a9875a", fundo="#e8dabb",
                  rotulo="Modo claro"),
}


def F(px, *estilo):
    return (TXT, -px, *estilo)


def T(px, *estilo):
    return (TIT, -px, "bold", *estilo)


T_PDF = [("PDF", "*.pdf")]
T_IMG = [("Imagens", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp")]
T_WORD = [("Word", "*.doc *.docx *.odt *.rtf")]
T_EXCEL = [("Excel", "*.xls *.xlsx *.xlsm *.ods *.csv")]
T_PPT = [("PowerPoint", "*.ppt *.pptx *.odp")]
EXT_IMG = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")


def extensoes(tipos):
    exts = []
    for _, padrao in tipos:
        exts += [p.replace("*", "").lower() for p in padrao.split()]
    return tuple(exts)


_cache_img = {}


def img(nome):
    """Imagem dos assets como PhotoImage (fica guardada para não sumir da tela)."""
    if nome not in _cache_img:
        _cache_img[nome] = ImageTk.PhotoImage(Image.open(os.path.join(ASSETS, nome)))
    return _cache_img[nome]


_pil = {}


def pil(nome):
    if nome not in _pil:
        _pil[nome] = Image.open(os.path.join(ASSETS, nome)).convert("RGBA")
    return _pil[nome]


def compor_folha(w, h, rapido=False):
    """Pergaminho aberto (papel + dois rolos) no tamanho pedido."""
    w, h = max(80, int(w)), max(60, int(h))
    filtro = Image.BILINEAR if rapido else Image.LANCZOS
    rh = max(18, min(40, int(h * 0.06)))
    folha = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    papel = pil("papel.png").resize((max(10, w - 36), max(10, h - rh)), filtro)
    folha.alpha_composite(papel, (18, rh // 2))
    rolo = pil("rolo.png").resize((w, rh), filtro)
    folha.alpha_composite(rolo, (0, 0))
    folha.alpha_composite(rolo, (0, h - rh))
    return folha

# =====================================================================
# Componentes reaproveitados
# =====================================================================
class Rolavel(tk.Frame):
    """Área com barra de rolagem."""

    def __init__(self, pai, bg=FUNDO, **kw):
        super().__init__(pai, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.dentro = tk.Frame(self.canvas, bg=bg)
        self._id = self.canvas.create_window((0, 0), window=self.dentro, anchor="nw")
        self.canvas.configure(yscrollcommand=barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.dentro.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._id, width=e.width))
        for w in (self.canvas, self.dentro):
            w.bind("<Enter>", lambda e: self._roda(True))
            w.bind("<Leave>", lambda e: self._roda(False))

    def _roda(self, ligar):
        if ligar:
            self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
            self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
            self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))
        else:
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.canvas.unbind_all(ev)


def ativar_soltar(widget, ao_soltar, exts):
    """Permite arrastar arquivos do Windows Explorer para o widget."""
    if not TEM_DND:
        return
    def soltou(ev):
        arqs = [a for a in widget.tk.splitlist(ev.data) if a.lower().endswith(exts)]
        if arqs:
            ao_soltar(arqs)
        return ev.action
    try:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", soltou)
    except Exception:
        pass


class ListaArquivos(tk.Frame):
    def __init__(self, pai, tipos, titulo="Arquivos", altura=12):
        super().__init__(pai, bg=FUNDO)
        self.tipos = tipos
        self.exts = extensoes(tipos)
        self.arquivos = []
        dica = " (pode arrastar os arquivos aqui)" if TEM_DND else ""
        tk.Label(self, text=titulo + dica, bg=FUNDO, fg=CINZA, font=F(15)).pack(anchor="w")
        meio = tk.Frame(self, bg=FUNDO)
        meio.pack(fill="both", expand=True)
        self.lista = tk.Listbox(meio, height=altura, font=F(17), activestyle="none",
                                selectbackground="#e2c88f", selectforeground=TEXTO,
                                relief="flat", highlightthickness=1, highlightcolor="#a9875a", highlightbackground="#a9875a", bg=CAMPO, fg=TEXTO)
        self.lista.pack(side="left", fill="both", expand=True)
        bts = tk.Frame(meio, bg=FUNDO)
        bts.pack(side="left", fill="y", padx=(6, 0))
        for txt, cmd in (("+ Adicionar", self.adicionar), ("Remover", self.remover),
                         ("▲ Subir", lambda: self.mover(-1)), ("▼ Descer", lambda: self.mover(1)),
                         ("Limpar", self.limpar)):
            ttk.Button(bts, text=txt, command=cmd, width=12).pack(pady=2)
        ativar_soltar(self.lista, self.incluir, self.exts)

    def adicionar(self):
        arqs = filedialog.askopenfilenames(filetypes=self.tipos + [("Todos", "*.*")])
        self.incluir(arqs)

    def incluir(self, arqs):
        for a in arqs:
            self.arquivos.append(a)
            self.lista.insert("end", os.path.basename(a))

    def remover(self):
        for i in reversed(self.lista.curselection()):
            self.lista.delete(i)
            del self.arquivos[i]

    def limpar(self):
        self.lista.delete(0, "end")
        self.arquivos.clear()

    def mover(self, d):
        sel = self.lista.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + d
        if 0 <= j < len(self.arquivos):
            self.arquivos[i], self.arquivos[j] = self.arquivos[j], self.arquivos[i]
            txt = self.lista.get(i)
            self.lista.delete(i)
            self.lista.insert(j, txt)
            self.lista.selection_set(j)


class ArquivoUnico(tk.Frame):
    def __init__(self, pai, ao_escolher=None, tipos=T_PDF, rotulo="Escolher PDF"):
        super().__init__(pai, bg=FUNDO)
        self.tipos = tipos
        self.caminho = None
        self.ao_escolher = ao_escolher
        ttk.Button(self, text=rotulo, command=self.escolher, style="Acao.TButton").pack(side="left")
        self.nome = tk.Label(self, text="nenhum arquivo" + (" — ou arraste aqui" if TEM_DND else ""),
                             bg=FUNDO, fg=CINZA, font=F(17))
        self.nome.pack(side="left", padx=10)
        ativar_soltar(self, lambda a: self.definir(a[0]), extensoes(tipos))
        ativar_soltar(self.nome, lambda a: self.definir(a[0]), extensoes(tipos))

    def escolher(self):
        a = filedialog.askopenfilename(filetypes=self.tipos)
        if a:
            self.definir(a)

    def definir(self, a):
        self.caminho = a
        self.nome.config(text=os.path.basename(a), fg=TEXTO)
        if self.ao_escolher:
            self.ao_escolher(a)


class Visualizador(tk.Frame):
    """Mostra uma página do PDF e captura cliques ou retângulos arrastados."""

    def __init__(self, pai, modo=None, ao_clicar=None, ao_retangulo=None):
        super().__init__(pai, bg=PAPEL_ESC)
        self.modo = modo
        self.ao_clicar = ao_clicar
        self.ao_retangulo = ao_retangulo
        self.doc = None
        self.pagina = 0
        self.zoom = 1
        self.marcas = []  # dicts com pagina, tipo ('rect'|'texto'), coords, cor, texto
        self._img = None
        self._inicio = None
        self._temp = None
        self._agendado = None

        barra = tk.Frame(self, bg=PAPEL_ESC)
        barra.pack(fill="x", pady=4)
        ttk.Button(barra, text="◀", width=3, command=lambda: self.ir(-1)).pack(side="left", padx=4)
        self.rotulo = tk.Label(barra, text="", bg=PAPEL_ESC, font=F(17))
        self.rotulo.pack(side="left")
        ttk.Button(barra, text="▶", width=3, command=lambda: self.ir(1)).pack(side="left", padx=4)
        self.dica = tk.Label(barra, text="", bg=PAPEL_ESC, fg=CINZA, font=F(15))
        self.dica.pack(side="right", padx=6)

        area = tk.Frame(self)
        area.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(area, bg="#c9b28a", highlightthickness=0, cursor="crosshair")
        rol = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=rol.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        rol.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._redimensionou)
        self.canvas.bind("<ButtonPress-1>", self._apertou)
        self.canvas.bind("<B1-Motion>", self._arrastou)
        self.canvas.bind("<ButtonRelease-1>", self._soltou)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

    def abrir(self, caminho, manter_pagina=False):
        if self.doc:
            self.doc.close()
        self.doc = motor.fitz.open(caminho)
        if not manter_pagina or self.pagina >= self.doc.page_count:
            self.pagina = 0
        self.desenhar()

    def ir(self, d):
        if self.doc and 0 <= self.pagina + d < self.doc.page_count:
            self.pagina += d
            self.desenhar()

    def _redimensionou(self, e):
        if self._agendado:
            self.after_cancel(self._agendado)
        self._agendado = self.after(150, self.desenhar)

    def desenhar(self):
        self.canvas.delete("all")
        if not self.doc:
            self.canvas.create_text(20, 20, anchor="nw", text="Escolha um PDF para ver aqui.",
                                    font=F(18), fill=CINZA)
            return
        p = self.doc[self.pagina]
        larg = max(200, self.canvas.winfo_width() - 30)
        self.zoom = larg / p.rect.width
        pix = p.get_pixmap(matrix=motor.fitz.Matrix(self.zoom, self.zoom), alpha=False)
        self._img = tk.PhotoImage(data=pix.tobytes("ppm"))
        self.canvas.create_image(15, 15, anchor="nw", image=self._img)
        self.canvas.configure(scrollregion=(0, 0, larg + 30, pix.height + 30))
        self.rotulo.config(text=f"Página {self.pagina + 1} de {self.doc.page_count}")
        for m in self.marcas:
            if m["pagina"] != self.pagina:
                continue
            z = self.zoom
            if m["tipo"] == "rect":
                x0, y0, x1, y1 = m["coords"]
                self.canvas.create_rectangle(15 + x0 * z, 15 + y0 * z, 15 + x1 * z, 15 + y1 * z,
                                             outline=m.get("cor", DESTAQUE), width=2,
                                             fill=m.get("preench", ""), stipple=m.get("stipple", ""),
                                             dash=m.get("dash"))
                if m.get("texto"):
                    self.canvas.create_text(17 + x0 * z, 17 + y0 * z, anchor="nw", text=m["texto"],
                                            fill=m.get("cor", DESTAQUE), font=T(15))
            else:
                x, y = m["coords"]
                tam = max(6, int(m.get("tamanho", 12) * z * 0.75))
                self.canvas.create_text(15 + x * z, 15 + y * z, anchor="sw", text=m["texto"],
                                        fill=m.get("cor", "#000"), font=("Helvetica", -int(m.get("tamanho", 12) * z)))

    def _pos(self, e):
        x = (self.canvas.canvasx(e.x) - 15) / self.zoom
        y = (self.canvas.canvasy(e.y) - 15) / self.zoom
        return x, y

    def _apertou(self, e):
        if not self.doc or not self.modo:
            return
        if self.modo == "ponto":
            x, y = self._pos(e)
            if self.ao_clicar:
                self.ao_clicar(self.pagina, x, y)
        else:
            self._inicio = (self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))

    def _arrastou(self, e):
        if self.modo != "retangulo" or not self._inicio:
            return
        if self._temp:
            self.canvas.delete(self._temp)
        self._temp = self.canvas.create_rectangle(*self._inicio, self.canvas.canvasx(e.x),
                                                  self.canvas.canvasy(e.y), outline=DESTAQUE, width=2, dash=(4, 2))

    def _soltou(self, e):
        if self.modo != "retangulo" or not self._inicio:
            return
        x0, y0 = self._inicio
        x1, y1 = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self._inicio = None
        if self._temp:
            self.canvas.delete(self._temp)
            self._temp = None
        if abs(x1 - x0) < 6 or abs(y1 - y0) < 6:
            return
        z = self.zoom
        r = (min(x0, x1) - 15) / z, (min(y0, y1) - 15) / z, (max(x0, x1) - 15) / z, (max(y0, y1) - 15) / z
        if self.ao_retangulo:
            self.ao_retangulo(self.pagina, *r)




# =====================================================================
# Base das ferramentas (tudo isto fica em cima do pergaminho aberto)
# =====================================================================
class Ornamento(tk.Canvas):
    def __init__(self, pai, largura=600):
        super().__init__(pai, height=14, bg=PAPEL, highlightthickness=0, width=largura)
        self.bind("<Configure>", self._desenhar)

    def _desenhar(self, e=None):
        self.delete("all")
        w = self.winfo_width()
        m = w // 2
        for i in range(0, m - 14, 6):
            tom = int(200 - 90 * (i / max(1, m)))
            cor = f"#{tom:02x}{int(tom * 0.78):02x}{int(tom * 0.5):02x}"
            self.create_line(m - 14 - i - 6, 7, m - 14 - i, 7, fill=cor, width=2)
            self.create_line(m + 14 + i, 7, m + 14 + i + 6, 7, fill=cor, width=2)
        self.create_polygon(m, 1, m + 6, 7, m, 13, m - 6, 7, fill="#8a6430")


class Ferramenta(tk.Frame):
    titulo = ""
    descricao = ""
    resumo = ""

    def __init__(self, app, pai=None, embutido=False):
        super().__init__(pai or app.area, bg=FUNDO)
        self.app = app
        if not embutido:
            tk.Label(self, text=self.titulo, bg=FUNDO, fg=TINTA, font=T(34)).pack(anchor="w")
            tk.Label(self, text=self.descricao, bg=FUNDO, fg=TINTA2, font=F(19, "italic"),
                     wraplength=1000, justify="left").pack(anchor="w")
            Ornamento(self).pack(fill="x", pady=(6, 12))
        self.corpo = tk.Frame(self, bg=FUNDO)
        self.corpo.pack(fill="both", expand=True)
        self.montar()

    def montar(self):
        pass

    def secao(self, pai, texto):
        tk.Label(pai, text=texto, bg=FUNDO, fg=TINTA, font=T(18), wraplength=340,
                 justify="left").pack(anchor="w", pady=(10, 2))

    def botao_principal(self, pai, texto, comando):
        b = ttk.Button(pai, text=texto, command=comando, style="Grande.TButton")
        b.pack(anchor="w", pady=14)
        return b

    def salvar_como(self, sugestao, ext=".pdf", tipos=T_PDF):
        return filedialog.asksaveasfilename(
            initialdir=os.path.dirname(sugestao), initialfile=os.path.basename(sugestao),
            defaultextension=ext, filetypes=tipos)

    def precisa(self, cond, msg):
        if not cond:
            messagebox.showwarning("Falta material", msg)
        return cond


class ComVisualizador(Ferramenta):
    """Opções à esquerda e o documento à direita."""
    modo = "retangulo"

    def montar(self):
        esq = tk.Frame(self.corpo, bg=FUNDO, width=360)
        esq.pack(side="left", fill="y", padx=(0, 16))
        esq.pack_propagate(False)
        self.arquivo = ArquivoUnico(esq, self._abriu)
        self.arquivo.pack(anchor="w")
        self.esq = esq
        self.viz = Visualizador(self.corpo, self.modo, self.clicou, self.arrastou)
        self.viz.pack(side="left", fill="both", expand=True)
        self.viz.desenhar()
        self.opcoes(esq)

    def _abriu(self, caminho):
        self.viz.marcas = []
        self.viz.abrir(caminho)
        self.abriu(caminho)

    def abriu(self, caminho):
        pass

    def opcoes(self, pai):
        pass

    def clicou(self, pagina, x, y):
        pass

    def arrastou(self, pagina, x0, y0, x1, y1):
        pass


class Par(Ferramenta):
    """Um pergaminho com dois sentidos de conversão (ex.: PDF → Word e Word → PDF)."""
    lados = []      # [(rótulo, explicação, classe), ...]
    selo = "azul"
    sigla = "W"

    def montar(self):
        topo = tk.Frame(self.corpo, bg=FUNDO)
        topo.pack(anchor="w", pady=(0, 12))
        self.caixas = []
        for i, (rot, dica, _) in enumerate(self.lados):
            c = tk.Frame(topo, bg=FUNDO, highlightthickness=2, cursor="hand2", padx=10, pady=6)
            c.pack(side="left", padx=(0, 16))
            s = tk.Label(c, image=img(f"selo_{self.selo}_p.png"), text=self.sigla, compound="center",
                         fg="#fbead0", font=T(15), bg=FUNDO)
            s.pack(side="left", padx=(0, 10))
            txt = tk.Frame(c, bg=FUNDO)
            txt.pack(side="left")
            a = tk.Label(txt, text=rot, font=T(21), bg=FUNDO)
            a.pack(anchor="w")
            b = tk.Label(txt, text=dica, font=F(16, "italic"), bg=FUNDO)
            b.pack(anchor="w")
            for w in (c, s, txt, a, b):
                w.bind("<Button-1>", lambda e, k=i: self.escolher(k))
            self.caixas.append((c, s, txt, a, b))
        self.miolo = tk.Frame(self.corpo, bg=FUNDO)
        self.miolo.pack(fill="both", expand=True)
        self.sub = None
        self.escolher(0)

    def escolher(self, k):
        for i, (c, s, txt, a, b) in enumerate(self.caixas):
            ativo = i == k
            fundo = "#e6cf9c" if ativo else FUNDO
            for w in (c, s, txt, a, b):
                w.config(bg=fundo)
            c.config(highlightbackground=LACRE if ativo else "#c4a878", highlightcolor=LACRE if ativo else "#c4a878")
            a.config(fg=TINTA if ativo else TINTA3)
            b.config(fg=TINTA2 if ativo else "#9c8463")
        if self.sub is not None:
            self.sub.destroy()
        self.sub = self.lados[k][2](self.app, self.miolo, embutido=True)
        self.sub.pack(fill="both", expand=True)

# =====================================================================
# Ferramentas
# =====================================================================
class Juntar(Ferramenta):
    titulo = "Juntar PDF"
    descricao = "Coloque os arquivos na ordem que quiser e junte tudo num PDF só. Dá para misturar imagens também."

    def montar(self):
        self.lista = ListaArquivos(self.corpo, T_PDF + T_IMG, "PDFs e imagens, na ordem final", 16)
        self.lista.pack(fill="both", expand=True)
        self.botao_principal(self.corpo, "Forjar PDF", self.rodar)

    def rodar(self):
        arqs = self.lista.arquivos
        if not self.precisa(len(arqs) >= 2, "Adicione pelo menos dois arquivos."):
            return
        s = self.salvar_como(motor.nome_saida(arqs[0], "juntado", ".pdf"))
        if s:
            self.app.tarefa(lambda: motor.juntar(arqs, s), s, "PDFs juntados!")


class Dividir(Ferramenta):
    titulo = "Dividir PDF"
    descricao = "Separe um intervalo de páginas, tire só as páginas que precisa ou transforme cada página num PDF."

    def montar(self):
        self.arq = ArquivoUnico(self.corpo, self.abriu)
        self.arq.pack(anchor="w")
        self.info = tk.Label(self.corpo, text="", bg=FUNDO, fg=CINZA, font=F(17))
        self.info.pack(anchor="w", pady=4)
        self.secao(self.corpo, "Como dividir")
        self.modo = tk.StringVar(value="intervalos")
        for v, t in (("intervalos", "Cada intervalo vira um PDF separado"),
                     ("extrair", "Juntar as páginas escolhidas num PDF só"),
                     ("todas", "Uma página por arquivo (todas)")):
            ttk.Radiobutton(self.corpo, text=t, value=v, variable=self.modo).pack(anchor="w")
        self.secao(self.corpo, "Páginas")
        self.paginas = ttk.Entry(self.corpo, width=40, font=F(18))
        self.paginas.pack(anchor="w")
        tk.Label(self.corpo, text="Exemplos:  1-3, 5, 8-10     ou   4-   (da 4 até o fim)",
                 bg=FUNDO, fg=CINZA, font=F(15)).pack(anchor="w")
        self.botao_principal(self.corpo, "Forjar divisão", self.rodar)

    def abriu(self, c):
        self.info.config(text=f"Este PDF tem {motor.contar_paginas(c)} páginas.")

    def rodar(self):
        c = self.arq.caminho
        if not self.precisa(c, "Escolha um PDF."):
            return
        m, pg = self.modo.get(), self.paginas.get()
        pasta = os.path.dirname(c)
        if m == "todas":
            self.app.tarefa(lambda: motor.dividir_todas(c, pasta), pasta, "PDF dividido!")
        elif self.precisa(pg.strip(), "Diga quais páginas (ex.: 1-3, 5)."):
            if m == "intervalos":
                self.app.tarefa(lambda: motor.dividir_intervalos(c, pg, pasta), pasta, "PDF dividido!")
            else:
                s = self.salvar_como(motor.nome_saida(c, "paginas", ".pdf"))
                if s:
                    self.app.tarefa(lambda: motor.extrair_paginas(c, pg, s), s, "Páginas extraídas!")


class Organizar(Ferramenta):
    titulo = "Organizar PDF"
    resumo = "Mude a ordem, gire, duplique ou exclua páginas."
    descricao = ("Clique numa página para selecionar (Ctrl+clique para várias). "
                 "Depois mova, gire, duplique ou exclua e salve.")

    def montar(self):
        topo = tk.Frame(self.corpo, bg=FUNDO)
        topo.pack(fill="x")
        self.arq = ArquivoUnico(topo, self.abriu)
        self.arq.pack(side="left")
        bar = tk.Frame(self.corpo, bg=FUNDO)
        bar.pack(fill="x", pady=8)
        for t, c in (("◀ Mover", lambda: self.mover(-1)), ("Mover ▶", lambda: self.mover(1)),
                     ("↻ Girar", self.girar), ("Duplicar", self.duplicar), ("Excluir", self.excluir)):
            ttk.Button(bar, text=t, command=c).pack(side="left", padx=2)
        ttk.Button(bar, text="Salvar PDF", style="Acao.TButton", command=self.rodar).pack(side="right")
        self.area = Rolavel(self.corpo)
        self.area.pack(fill="both", expand=True)
        self.itens = []  # [indice_original, rotacao]
        self.sel = set()
        self.cache = {}

    def abriu(self, c):
        n = motor.contar_paginas(c)
        self.itens = [[i, 0] for i in range(n)]
        self.sel = set()
        self.cache = {}
        self.redesenhar()

    def miniatura(self, idx, rot):
        k = (idx, rot)
        if k not in self.cache:
            self.cache[k] = tk.PhotoImage(data=motor.miniatura_png(self.arq.caminho, idx, 120, rot))
        return self.cache[k]

    def redesenhar(self):
        for w in self.area.dentro.winfo_children():
            w.destroy()
        colunas = max(1, (self.area.winfo_width() or 900) // 150)
        for pos, (idx, rot) in enumerate(self.itens):
            sel = pos in self.sel
            f = tk.Frame(self.area.dentro, bg=DESTAQUE if sel else BRANCO, padx=3, pady=3)
            f.grid(row=pos // colunas, column=pos % colunas, padx=6, pady=6)
            img = tk.Label(f, image=self.miniatura(idx, rot), bg=BRANCO)
            img.pack()
            lbl = tk.Label(f, text=f"pág. {idx + 1}", bg=f["bg"], fg=BRANCO if sel else CINZA, font=F(15))
            lbl.pack()
            for w in (f, img, lbl):
                w.bind("<Button-1>", lambda e, p=pos: self.clicar(p, e))

    def clicar(self, pos, e):
        if e.state & 0x0004:  # Ctrl
            self.sel.symmetric_difference_update({pos})
        else:
            self.sel = {pos}
        self.redesenhar()

    def mover(self, d):
        if not self.sel:
            return
        ordem = sorted(self.sel, reverse=(d > 0))
        novo = set()
        for p in ordem:
            q = p + d
            if 0 <= q < len(self.itens) and q not in novo:
                self.itens[p], self.itens[q] = self.itens[q], self.itens[p]
                novo.add(q)
            else:
                novo.add(p)
        self.sel = novo
        self.redesenhar()

    def girar(self):
        for p in self.sel:
            self.itens[p][1] = (self.itens[p][1] + 90) % 360
        self.redesenhar()

    def duplicar(self):
        for p in sorted(self.sel, reverse=True):
            self.itens.insert(p + 1, list(self.itens[p]))
        self.sel = set()
        self.redesenhar()

    def excluir(self):
        if len(self.sel) >= len(self.itens):
            messagebox.showwarning("Ops", "O PDF precisa ficar com pelo menos uma página.")
            return
        self.itens = [it for p, it in enumerate(self.itens) if p not in self.sel]
        self.sel = set()
        self.redesenhar()

    def rodar(self):
        c = self.arq.caminho
        if not self.precisa(c and self.itens, "Escolha um PDF."):
            return
        s = self.salvar_como(motor.nome_saida(c, "organizado", ".pdf"))
        if s:
            ordem = [i for i, _ in self.itens]
            rots = [r for _, r in self.itens]
            self.app.tarefa(lambda: motor.organizar(c, ordem, rots, s), s, "PDF organizado!")


class Conversor(Ferramenta):
    """Converte vários arquivos de uma vez; o resultado fica ao lado do original."""
    tipos = T_PDF
    ext_saida = ".pdf"
    sufixo = "convertido"
    aviso = ""
    acao_txt = "Forjar"

    def converter(self, entrada, saida):
        raise NotImplementedError

    def montar(self):
        self.lista = ListaArquivos(self.corpo, self.tipos, "Arquivos para converter", 12)
        self.lista.pack(fill="both", expand=True)
        self.extras(self.corpo)
        if self.aviso:
            tk.Label(self.corpo, text=self.aviso, bg=FUNDO, fg=CINZA, font=F(15),
                     wraplength=850, justify="left").pack(anchor="w", pady=(8, 0))
        self.botao_principal(self.corpo, self.acao_txt, self.rodar)

    def extras(self, pai):
        pass

    def rodar(self):
        arqs = list(self.lista.arquivos)
        if not self.precisa(arqs, "Adicione pelo menos um arquivo."):
            return

        def trabalho():
            saidas = []
            for n, a in enumerate(arqs, 1):
                self.app.status(f"Convertendo {n} de {len(arqs)}: {os.path.basename(a)}")
                saidas.append(self.converter(a, motor.nome_saida(a, self.sufixo, self.ext_saida)))
            return saidas
        alvo = os.path.dirname(arqs[0])
        self.app.tarefa(trabalho, alvo, f"{len(arqs)} arquivo(s) convertido(s)! Estão na mesma pasta dos originais.")


class PdfWord(Conversor):
    acao_txt = "Forjar documento do Word"
    titulo = "PDF para Word"
    descricao = "Transforma o PDF num documento do Word (.docx) para você editar."
    ext_saida = ".docx"
    aviso = "Funciona melhor com PDFs de texto. PDF escaneado (foto de papel) vira imagem dentro do Word."

    def converter(self, e, s):
        return motor.pdf_para_word(e, s)


class PdfPpt(Conversor):
    acao_txt = "Forjar apresentação"
    titulo = "PDF para PowerPoint"
    descricao = "Cada página do PDF vira um slide (.pptx)."
    ext_saida = ".pptx"
    aviso = "Os slides ficam idênticos ao PDF (como imagem). O texto de cada página vai nas anotações do slide."

    def converter(self, e, s):
        return motor.pdf_para_powerpoint(e, s)


class PdfExcel(Conversor):
    acao_txt = "Forjar planilha"
    titulo = "PDF para Excel"
    descricao = "Puxa as tabelas do PDF para uma planilha (.xlsx). Cada tabela vira uma aba."
    ext_saida = ".xlsx"
    aviso = "Se não achar tabela, o texto do PDF vai linha por linha numa aba chamada Texto."

    def converter(self, e, s):
        return motor.pdf_para_excel(e, s)[0]


class OfficePdf(Conversor):
    aviso = ("Usa o Microsoft Office do seu computador. Se não tiver, usa o LibreOffice "
             "(gratuito, libreoffice.org).")

    def converter(self, e, s):
        return motor.office_para_pdf(e, s)


class WordPdf(OfficePdf):
    acao_txt = "Forjar PDF"
    titulo = "Word para PDF"
    descricao = "Converte documentos do Word (.doc, .docx) em PDF."
    tipos = T_WORD


class PptPdf(OfficePdf):
    acao_txt = "Forjar PDF"
    titulo = "PowerPoint para PDF"
    descricao = "Converte apresentações (.ppt, .pptx) em PDF."
    tipos = T_PPT


class ExcelPdf(OfficePdf):
    acao_txt = "Forjar PDF"
    titulo = "Excel para PDF"
    descricao = "Converte planilhas (.xls, .xlsx) em PDF."
    tipos = T_EXCEL


class PdfPdfa(Conversor):
    acao_txt = "Forjar PDF/A"
    titulo = "PDF para PDF/A"
    resumo = "Formato de arquivamento pedido pelo SEI, editais e tribunais."
    descricao = "Gera a versão PDF/A, o formato de arquivamento que muitos sistemas (SEI, tribunais, editais) pedem."
    sufixo = "PDFA"
    aviso = "Precisa do Ghostscript instalado (gratuito, ghostscript.com/releases)."

    def extras(self, pai):
        self.secao(pai, "Versão")
        self.nivel = tk.StringVar(value="2")
        f = tk.Frame(pai, bg=FUNDO)
        f.pack(anchor="w")
        for v, t in (("1", "PDF/A-1b"), ("2", "PDF/A-2b (recomendado)"), ("3", "PDF/A-3b")):
            ttk.Radiobutton(f, text=t, value=v, variable=self.nivel).pack(side="left", padx=(0, 12))

    def converter(self, e, s):
        return motor.pdf_para_pdfa(e, s, int(self.nivel.get()))


class PdfJpg(Conversor):
    acao_txt = "Forjar imagens"
    titulo = "PDF para JPG"
    descricao = "Transforma cada página em imagem, ou tira só as fotos que estão dentro do PDF."
    sufixo = "imagens"

    def extras(self, pai):
        self.secao(pai, "O que fazer")
        self.modo = tk.StringVar(value="paginas")
        ttk.Radiobutton(pai, text="Cada página vira uma imagem", value="paginas", variable=self.modo).pack(anchor="w")
        ttk.Radiobutton(pai, text="Extrair só as fotos/figuras de dentro do PDF", value="figuras",
                        variable=self.modo).pack(anchor="w")
        f = tk.Frame(pai, bg=FUNDO)
        f.pack(anchor="w", pady=6)
        tk.Label(f, text="Formato:", bg=FUNDO).pack(side="left")
        self.fmt = ttk.Combobox(f, values=["jpg", "png"], width=6, state="readonly")
        self.fmt.set("jpg")
        self.fmt.pack(side="left", padx=(4, 16))
        tk.Label(f, text="Qualidade:", bg=FUNDO).pack(side="left")
        self.qual = ttk.Combobox(f, values=["Normal (150 dpi)", "Alta (300 dpi)", "Leve (96 dpi)"],
                                 width=16, state="readonly")
        self.qual.set("Normal (150 dpi)")
        self.qual.pack(side="left", padx=4)

    def converter(self, e, s):
        pasta = os.path.dirname(e)
        if self.modo.get() == "figuras":
            return motor.extrair_imagens_embutidas(e, pasta)
        dpi = int(self.qual.get().split("(")[1].split()[0])
        return motor.pdf_para_imagens(e, pasta, self.fmt.get(), dpi)


class JpgPdf(Ferramenta):
    titulo = "JPG para PDF"
    descricao = "Junte fotos e imagens num PDF, na ordem que quiser."

    def montar(self):
        self.lista = ListaArquivos(self.corpo, T_IMG, "Imagens, na ordem das páginas", 12)
        self.lista.pack(fill="both", expand=True)
        f = tk.Frame(self.corpo, bg=FUNDO)
        f.pack(anchor="w", pady=8)
        tk.Label(f, text="Tamanho da página:", bg=FUNDO).pack(side="left")
        self.tam = ttk.Combobox(f, values=["A4", "Carta", "Original"], width=10, state="readonly")
        self.tam.set("A4")
        self.tam.pack(side="left", padx=(4, 16))
        tk.Label(f, text="Margem:", bg=FUNDO).pack(side="left")
        self.marg = ttk.Combobox(f, values=["Sem margem", "Pequena", "Grande"], width=12, state="readonly")
        self.marg.set("Pequena")
        self.marg.pack(side="left", padx=4)
        self.botao_principal(self.corpo, "Forjar PDF", self.rodar)

    def rodar(self):
        arqs = list(self.lista.arquivos)
        if not self.precisa(arqs, "Adicione pelo menos uma imagem."):
            return
        s = self.salvar_como(motor.nome_saida(arqs[0], "imagens", ".pdf"))
        if s:
            m = {"Sem margem": 0, "Pequena": 20, "Grande": 45}[self.marg.get()]
            t = self.tam.get()
            self.app.tarefa(lambda: motor.imagens_para_pdf(arqs, s, t, m), s, "PDF criado!")


class Editar(ComVisualizador):
    titulo = "Editar PDF"
    resumo = "Escreva texto ou cole imagens (assinatura, logo) em qualquer lugar."
    descricao = ("Escreva texto em qualquer lugar do PDF (clique onde quer) ou cole uma imagem, "
                 "como assinatura escaneada ou logo (arraste um retângulo).")
    modo = "ponto"

    def opcoes(self, pai):
        self.secao(pai, "O que adicionar")
        self.tipo = tk.StringVar(value="texto")
        ttk.Radiobutton(pai, text="Texto (clique no documento)", value="texto", variable=self.tipo,
                        command=self.trocou).pack(anchor="w")
        ttk.Radiobutton(pai, text="Imagem (arraste um retângulo)", value="imagem", variable=self.tipo,
                        command=self.trocou).pack(anchor="w")
        self.secao(pai, "Texto")
        self.texto = ttk.Entry(pai, width=36, font=F(18))
        self.texto.pack(anchor="w")
        f = tk.Frame(pai, bg=FUNDO)
        f.pack(anchor="w", pady=6)
        tk.Label(f, text="Tamanho:", bg=FUNDO).pack(side="left")
        self.tam = ttk.Spinbox(f, from_=6, to=96, width=5)
        self.tam.set(12)
        self.tam.pack(side="left", padx=(4, 12))
        self.cor = "#000000"
        self.bcor = tk.Button(f, text="  Cor  ", bg=self.cor, fg="white", relief="flat", command=self.escolher_cor)
        self.bcor.pack(side="left")
        self.secao(pai, "Alterações")
        self.lista = tk.Listbox(pai, height=8, font=F(15), relief="flat")
        self.lista.pack(fill="x")
        ttk.Button(pai, text="Desfazer última", command=self.desfazer).pack(anchor="w", pady=4)
        self.itens = []
        self.botao_principal(pai, "Salvar PDF", self.rodar)

    def trocou(self):
        self.viz.modo = "ponto" if self.tipo.get() == "texto" else "retangulo"

    def escolher_cor(self):
        c = colorchooser.askcolor(self.cor)[1]
        if c:
            self.cor = c
            self.bcor.config(bg=c)

    def clicou(self, pagina, x, y):
        t = self.texto.get().strip() or simpledialog.askstring("Texto", "O que escrever aqui?")
        if not t:
            return
        tam = float(self.tam.get() or 12)
        self.itens.append(("texto", {"pagina": pagina, "x": x, "y": y, "texto": t, "tamanho": tam, "cor": self.cor}))
        self.viz.marcas.append({"pagina": pagina, "tipo": "texto", "coords": (x, y), "texto": t,
                                "tamanho": tam, "cor": self.cor})
        self.lista.insert("end", f"Pág. {pagina + 1}: texto “{t}”")
        self.viz.desenhar()

    def arrastou(self, pagina, x0, y0, x1, y1):
        img = filedialog.askopenfilename(title="Escolha a imagem", filetypes=T_IMG)
        if not img:
            return
        self.itens.append(("imagem", {"pagina": pagina, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "arquivo": img}))
        self.viz.marcas.append({"pagina": pagina, "tipo": "rect", "coords": (x0, y0, x1, y1),
                                "texto": os.path.basename(img), "cor": "#2d6be5", "dash": (4, 2)})
        self.lista.insert("end", f"Pág. {pagina + 1}: imagem {os.path.basename(img)}")
        self.viz.desenhar()

    def desfazer(self):
        if self.itens:
            self.itens.pop()
            self.viz.marcas.pop()
            self.lista.delete("end")
            self.viz.desenhar()

    def abriu(self, c):
        self.itens = []
        self.lista.delete(0, "end")

    def rodar(self):
        c = self.arquivo.caminho
        if not self.precisa(c and self.itens, "Escolha um PDF e adicione pelo menos um texto ou imagem."):
            return
        s = self.salvar_como(motor.nome_saida(c, "editado", ".pdf"))
        if not s:
            return
        textos = [d for t, d in self.itens if t == "texto"]
        imagens = [d for t, d in self.itens if t == "imagem"]

        def trabalho():
            tmp = c
            if imagens:
                tmp = motor.adicionar_imagens(c, imagens, s if not textos else s + ".tmp.pdf")
            if textos:
                motor.adicionar_textos(tmp, textos, s)
                if tmp != c:
                    os.remove(tmp)
            return s
        self.app.tarefa(trabalho, s, "PDF editado!")


class MarcaDagua(ComVisualizador):
    titulo = "Marca d'água"
    resumo = "Texto ou logo em todas as páginas."
    descricao = "Coloque um texto (ex.: CONFIDENCIAL, RASCUNHO) ou uma imagem (ex.: logo) em todas as páginas."
    modo = None

    def opcoes(self, pai):
        self.tipo = tk.StringVar(value="texto")
        self.secao(pai, "Tipo")
        f = tk.Frame(pai, bg=FUNDO)
        f.pack(anchor="w")
        ttk.Radiobutton(f, text="Texto", value="texto", variable=self.tipo).pack(side="left")
        ttk.Radiobutton(f, text="Imagem", value="imagem", variable=self.tipo).pack(side="left", padx=10)
        self.secao(pai, "Texto")
        self.texto = ttk.Entry(pai, width=34, font=F(18))
        self.texto.insert(0, "CONFIDENCIAL")
        self.texto.pack(anchor="w")
        g = tk.Frame(pai, bg=FUNDO)
        g.pack(anchor="w", pady=6)
        tk.Label(g, text="Tamanho:", bg=FUNDO).pack(side="left")
        self.tam = ttk.Spinbox(g, from_=10, to=200, width=5)
        self.tam.set(60)
        self.tam.pack(side="left", padx=(4, 10))
        self.cor = "#888888"
        self.bcor = tk.Button(g, text="  Cor  ", bg=self.cor, fg="white", relief="flat", command=self.escolher_cor)
        self.bcor.pack(side="left")
        h = tk.Frame(pai, bg=FUNDO)
        h.pack(anchor="w")
        tk.Label(h, text="Inclinação:", bg=FUNDO).pack(side="left")
        self.ang = ttk.Combobox(h, values=["45", "0", "90"], width=4, state="readonly")
        self.ang.set("45")
        self.ang.pack(side="left", padx=(4, 10))
        tk.Label(h, text="Posição:", bg=FUNDO).pack(side="left")
        self.pos = ttk.Combobox(h, values=["centro", "topo", "rodapé"], width=8, state="readonly")
        self.pos.set("centro")
        self.pos.pack(side="left", padx=4)
        self.secao(pai, "Imagem")
        self.img = ArquivoUnico(pai, tipos=T_IMG, rotulo="Escolher imagem")
        self.img.pack(anchor="w")
        self.secao(pai, "Transparência")
        self.opac = tk.DoubleVar(value=0.3)
        ttk.Scale(pai, from_=0.05, to=1, variable=self.opac, length=260).pack(anchor="w")
        ttk.Button(pai, text="Pré-visualizar", command=self.previa).pack(anchor="w", pady=(12, 0))
        self.botao_principal(pai, "Aplicar e salvar", self.rodar)
        self._previa = None

    def escolher_cor(self):
        c = colorchooser.askcolor(self.cor)[1]
        if c:
            self.cor = c
            self.bcor.config(bg=c)

    def aplicar(self, entrada, saida):
        if self.tipo.get() == "imagem":
            if not self.img.caminho:
                raise ValueError("Escolha a imagem da marca d'água.")
            return motor.marca_dagua_imagem(entrada, saida, self.img.caminho, 0.45, self.opac.get())
        return motor.marca_dagua_texto(entrada, saida, self.texto.get() or " ", float(self.tam.get()),
                                       self.cor, self.opac.get(), int(self.ang.get()),
                                       {"rodapé": "rodape"}.get(self.pos.get(), self.pos.get()))

    def previa(self):
        c = self.arquivo.caminho
        if not self.precisa(c, "Escolha um PDF."):
            return
        try:
            self._previa = os.path.join(tempfile.gettempdir(), "meupdf_previa.pdf")
            self.viz.doc and self.viz.doc.close()
            self.viz.doc = None
            self.aplicar(c, self._previa)
            self.viz.abrir(self._previa, manter_pagina=True)
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def rodar(self):
        c = self.arquivo.caminho
        if not self.precisa(c, "Escolha um PDF."):
            return
        s = self.salvar_como(motor.nome_saida(c, "marca", ".pdf"))
        if s:
            self.app.tarefa(lambda: self.aplicar(c, s), s, "Marca d'água aplicada!")


class Ocultar(ComVisualizador):
    titulo = "Ocultar PDF"
    resumo = "Tarje e apague de verdade informações sensíveis."
    descricao = ("Tarje informações sensíveis (CPF, endereço, notas). Arraste retângulos no documento "
                 "ou digite palavras para esconder em todas as páginas.")

    def opcoes(self, pai):
        tk.Label(pai, text="O que fica embaixo da tarja é apagado de verdade, não dá para copiar nem recuperar.",
                 bg=FUNDO, fg=DESTAQUE, font=F(15), wraplength=310, justify="left").pack(anchor="w", pady=8)
        self.secao(pai, "Palavras para esconder")
        tk.Label(pai, text="separe por vírgula, ex.: CPF, 123.456.789-00", bg=FUNDO, fg=CINZA,
                 font=F(15)).pack(anchor="w")
        self.termos = tk.Text(pai, height=4, width=36, font=F(17), relief="flat")
        self.termos.pack(anchor="w")
        self.secao(pai, "Áreas marcadas")
        self.qtd = tk.Label(pai, text="0 áreas", bg=FUNDO, fg=CINZA)
        self.qtd.pack(anchor="w")
        ttk.Button(pai, text="Desfazer última área", command=self.desfazer).pack(anchor="w", pady=4)
        self.botao_principal(pai, "Ocultar e salvar", self.rodar)
        self.areas = []

    def abriu(self, c):
        self.areas = []
        self.qtd.config(text="0 áreas")

    def arrastou(self, pagina, x0, y0, x1, y1):
        self.areas.append({"pagina": pagina, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
        self.viz.marcas.append({"pagina": pagina, "tipo": "rect", "coords": (x0, y0, x1, y1),
                                "cor": "#000", "preench": "#000", "stipple": "gray50"})
        self.qtd.config(text=f"{len(self.areas)} área(s)")
        self.viz.desenhar()

    def desfazer(self):
        if self.areas:
            self.areas.pop()
            self.viz.marcas.pop()
            self.qtd.config(text=f"{len(self.areas)} área(s)")
            self.viz.desenhar()

    def rodar(self):
        c = self.arquivo.caminho
        termos = [t for t in self.termos.get("1.0", "end").replace("\n", ",").split(",") if t.strip()]
        if not self.precisa(c and (self.areas or termos), "Escolha um PDF e marque áreas ou digite palavras."):
            return
        s = self.salvar_como(motor.nome_saida(c, "oculto", ".pdf"))
        if s:
            self.app.tarefa(lambda: motor.ocultar(c, s, self.areas, termos)[0], s, "Informações ocultadas!")


class Recortar(ComVisualizador):
    titulo = "Recortar PDF"
    resumo = "Corte as margens ou fique só com uma parte da página."
    descricao = "Arraste um retângulo em volta da parte que quer manter. Tudo fora dele é cortado."

    def opcoes(self, pai):
        self.secao(pai, "Aplicar em")
        self.onde = tk.StringVar(value="todas")
        ttk.Radiobutton(pai, text="Todas as páginas", value="todas", variable=self.onde).pack(anchor="w")
        ttk.Radiobutton(pai, text="Só na página que estou vendo", value="esta", variable=self.onde).pack(anchor="w")
        self.info = tk.Label(pai, text="Nenhuma área marcada", bg=FUNDO, fg=CINZA)
        self.info.pack(anchor="w", pady=8)
        self.botao_principal(pai, "Recortar e salvar", self.rodar)
        self.ret = None

    def arrastou(self, pagina, x0, y0, x1, y1):
        self.ret = (x0, y0, x1, y1)
        self.viz.marcas = [{"pagina": pg, "tipo": "rect", "coords": self.ret, "cor": "#2d6be5", "dash": (6, 3)}
                           for pg in range(self.viz.doc.page_count)]
        self.info.config(text="Área marcada. Arraste de novo para mudar.")
        self.viz.desenhar()

    def rodar(self):
        c = self.arquivo.caminho
        if not self.precisa(c and self.ret, "Escolha um PDF e arraste a área a manter."):
            return
        s = self.salvar_como(motor.nome_saida(c, "recortado", ".pdf"))
        if s:
            pgs = None if self.onde.get() == "todas" else [self.viz.pagina]
            self.app.tarefa(lambda: motor.recortar(c, s, *self.ret, paginas=pgs), s, "PDF recortado!")


class Formularios(ComVisualizador):
    titulo = "Formulários PDF"
    resumo = "Preencha formulários PDF ou crie campos novos."
    descricao = ("Preencha os campos de um formulário PDF. Também dá para criar campos novos num PDF comum: "
                 "arraste um retângulo onde o campo deve ficar.")

    def opcoes(self, pai):
        self.secao(pai, "Campos")
        self.area = Rolavel(pai)
        self.area.pack(fill="both", expand=True)
        self.travar = tk.BooleanVar(value=False)
        ttk.Checkbutton(pai, text="Travar o formulário depois de preencher", variable=self.travar).pack(anchor="w", pady=4)
        self.botao_principal(pai, "Salvar PDF", self.rodar)
        self.vars = {}
        self.novos = []

    def abriu(self, c):
        for w in self.area.dentro.winfo_children():
            w.destroy()
        self.vars = {}
        self.novos = []
        campos = motor.ler_campos(c)
        self.viz.marcas = [{"pagina": k["pagina"], "tipo": "rect", "coords": k["rect"], "cor": "#1e7145",
                            "texto": k["rotulo"]} for k in campos]
        self.viz.desenhar()
        if not campos:
            tk.Label(self.area.dentro, text="Este PDF não tem campos.\nArraste no documento para criar.",
                     bg=FUNDO, fg=CINZA, justify="left").pack(anchor="w")
        for k in campos:
            tk.Label(self.area.dentro, text=f"{k['rotulo']}  (pág. {k['pagina'] + 1})", bg=FUNDO,
                     font=F(15)).pack(anchor="w", pady=(6, 0))
            if k["tipo"] == "texto":
                v = tk.StringVar(value=k["valor"] or "")
                ttk.Entry(self.area.dentro, textvariable=v, width=34).pack(anchor="w")
            elif k["tipo"] in ("marcar", "opcao"):
                v = tk.BooleanVar(value=k["valor"] not in (None, "", "Off", False))
                ttk.Checkbutton(self.area.dentro, text="marcado", variable=v).pack(anchor="w")
            else:
                v = tk.StringVar(value=k["valor"] or "")
                ttk.Combobox(self.area.dentro, textvariable=v, values=k["opcoes"], width=32).pack(anchor="w")
            self.vars[k["xref"]] = v

    def arrastou(self, pagina, x0, y0, x1, y1):
        nome = simpledialog.askstring("Novo campo", "Nome do campo (ex.: nome, data, assinatura):")
        if not nome:
            return
        self.novos.append((pagina, x0, y0, x1, y1, nome))
        self.viz.marcas.append({"pagina": pagina, "tipo": "rect", "coords": (x0, y0, x1, y1),
                                "texto": nome, "cor": "#2d6be5"})
        self.viz.desenhar()

    def rodar(self):
        c = self.arquivo.caminho
        if not self.precisa(c and (self.vars or self.novos), "Escolha um PDF com campos ou crie campos novos."):
            return
        s = self.salvar_como(motor.nome_saida(c, "preenchido", ".pdf"))
        if not s:
            return
        valores = {x: v.get() for x, v in self.vars.items()}
        novos, travar = list(self.novos), self.travar.get()

        def trabalho():
            atual = c
            if valores:
                motor.preencher_campos(c, valores, s + ".tmp.pdf", travar)
                atual = s + ".tmp.pdf"
            for i, n in enumerate(novos):
                destino = s + f".n{i}.pdf"
                motor.criar_campo_texto(atual, destino, *n)
                if atual != c:
                    os.remove(atual)
                atual = destino
            os.replace(atual, s)
            return s
        self.app.tarefa(trabalho, s, "Formulário salvo!")


class Traduzir(Ferramenta):
    titulo = "Traduzir PDF"
    descricao = "Traduz o texto do PDF mantendo o layout, as imagens e os desenhos no lugar."

    def montar(self):
        self.arq = ArquivoUnico(self.corpo)
        self.arq.pack(anchor="w")
        f = tk.Frame(self.corpo, bg=FUNDO)
        f.pack(anchor="w", pady=10)
        tk.Label(f, text="Traduzir para:", bg=FUNDO).pack(side="left")
        self.idioma = ttk.Combobox(f, values=list(motor.IDIOMAS), state="readonly", width=14)
        self.idioma.set("Português")
        self.idioma.pack(side="left", padx=6)
        tk.Label(self.corpo, text="Esta é a única ferramenta que precisa de internet: o texto é enviado "
                                  "ao Google Tradutor. Não use com documentos sigilosos.",
                 bg=FUNDO, fg=CINZA, font=F(15), wraplength=700, justify="left").pack(anchor="w")
        self.botao_principal(self.corpo, "Forjar tradução", self.rodar)

    def rodar(self):
        c = self.arq.caminho
        if not self.precisa(c, "Escolha um PDF."):
            return
        cod = motor.IDIOMAS[self.idioma.get()]
        s = self.salvar_como(motor.nome_saida(c, cod, ".pdf"))
        if s:
            prog = lambda i, n: self.app.status(f"Traduzindo página {i} de {n}...")
            self.app.tarefa(lambda: motor.traduzir(c, s, cod, prog), s, "PDF traduzido!")




# ---------------------------------------------------------------- conversores em par
class WordPar(Par):
    titulo = "Word ⇄ PDF"
    descricao = "Escolha para qual lado quer converter. Dá para colocar vários arquivos de uma vez."
    resumo = "De PDF para Word ou de Word para PDF."
    selo = "azul"
    lados = [("PDF → Word", "transforma o PDF num documento editável", PdfWord),
             ("Word → PDF", "transforma o documento do Word em PDF", WordPdf)]


class ExcelPar(Par):
    sigla = "X"
    titulo = "Excel ⇄ PDF"
    descricao = "Escolha para qual lado quer converter. Dá para colocar vários arquivos de uma vez."
    resumo = "De PDF para Excel ou de Excel para PDF."
    selo = "verde"
    lados = [("PDF → Excel", "puxa as tabelas do PDF para a planilha", PdfExcel),
             ("Excel → PDF", "transforma a planilha em PDF", ExcelPdf)]


class PptPar(Par):
    sigla = "P"
    titulo = "PowerPoint ⇄ PDF"
    descricao = "Escolha para qual lado quer converter. Dá para colocar vários arquivos de uma vez."
    resumo = "De PDF para slides ou de slides para PDF."
    selo = "laranja"
    lados = [("PDF → PowerPoint", "cada página vira um slide", PdfPpt),
             ("PowerPoint → PDF", "transforma a apresentação em PDF", PptPdf)]


class JpgPar(Par):
    sigla = "▣"
    titulo = "JPG ⇄ PDF"
    descricao = "Escolha para qual lado quer converter."
    resumo = "De PDF para imagens ou de imagens para PDF."
    selo = "ouro"
    lados = [("PDF → JPG", "cada página vira uma imagem", PdfJpg),
             ("JPG → PDF", "junta fotos e imagens num PDF", JpgPdf)]


Juntar.resumo = "Une vários pergaminhos num só."
Dividir.resumo = "Separa páginas ou intervalos."
Organizar.resumo = "Muda a ordem, gira, exclui páginas."
Editar.resumo = "Escreve texto ou cola imagens."
MarcaDagua.resumo = "Texto ou brasão em todas as páginas."
PdfPdfa.resumo = "Formato de arquivamento do SEI e editais."
Ocultar.resumo = "Apaga de vez o que é sigiloso."
Recortar.resumo = "Corta as margens da página."
Formularios.resumo = "Preenche ou cria campos."
Traduzir.resumo = "Traduz mantendo o layout."
PdfPdfa.descricao = ("Gera a versão PDF/A, o formato de arquivamento que muitos sistemas "
                     "(SEI, tribunais, editais) pedem.")

FERRAMENTAS = [
    (Juntar, "⊕", "vermelho"), (Dividir, "÷", "vermelho"), (Organizar, "❖", "vermelho"),
    (Editar, "✒", "roxo"), (WordPar, "W", "azul"), (ExcelPar, "X", "verde"),
    (PptPar, "P", "laranja"), (JpgPar, "▣", "ouro"), (MarcaDagua, "≋", "roxo"),
    (PdfPdfa, "A", "azul"), (Ocultar, "▬", "preto"), (Recortar, "✂", "roxo"),
    (Formularios, "☰", "roxo"), (Traduzir, "文", "azul"),
]

ESTADOS = {
    "fria": ("#6d6a70", None, "A forja está fria · esperando materiais para forjar"),
    "acesa": ("#e0661c", "#ffb060", "Forjando..."),
    "pronta": ("#d9a93a", "#ffe08a", "Forjado!"),
    "falha": ("#b3261e", "#ff7a6a", "A forja falhou"),
}

CW, CH = 344, 190       # tamanho das imagens dos pergaminhos do salão


# =====================================================================
# Janela principal
# =====================================================================
class App(tk.Tk):
    def __init__(self):
        carregar_fontes()
        super().__init__()
        global TEM_DND, TIT, TXT
        if TkinterDnD is not None:
            try:
                TkinterDnD._require(self)
                TEM_DND = True
            except Exception:
                TEM_DND = False
        try:
            import tkinter.font as tkfont
            familias = set(tkfont.families(self))
            if TIT not in familias:
                TIT = "Georgia"
            if TXT not in familias:
                TXT = "Georgia"
        except Exception:
            pass

        self.title("Forja de Pergaminhos")
        self.geometry("1360x900")
        self.minsize(1120, 720)
        try:
            if motor.EH_WINDOWS:
                self.iconbitmap(os.path.join(PASTA, "icone.ico"))
            else:
                self.iconphoto(True, tk.PhotoImage(file=os.path.join(PASTA, "icone.png")))
        except Exception:
            pass

        self._arq_config = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                                        "ForjaDePergaminhos", "config.json")
        self.tema = self._ler_config().get("tema", "escuro")
        self._fila = queue.Queue()
        self._ocupado = False
        self._prog = None
        self._anim_fase = 0
        self._agendado = None
        self._fundo_img = None
        self._folha_img = None
        self.tela = None
        self.area = None
        self.estilos()
        self.montar_moldura()
        self.aplicar_tema()
        self.inicio()
        self.after(100, self._ler_fila)

    # ---------------- configuração
    def _ler_config(self):
        try:
            with open(self._arq_config, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _salvar_config(self):
        try:
            os.makedirs(os.path.dirname(self._arq_config), exist_ok=True)
            with open(self._arq_config, "w", encoding="utf-8") as f:
                json.dump({"tema": self.tema}, f)
        except Exception:
            pass

    # ---------------- estilos
    def estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", font=F(17), background=PAPEL, foreground=TINTA)
        filhos = {"sticky": "nsew", "children": [("Button.padding", {"sticky": "nsew", "children": [
            ("Button.label", {"sticky": "nsew"})]})]}
        s.element_create("Tabua.border", "image", img("tabua_normal.png"),
                         ("pressed", img("tabua_pressed.png")), ("active", img("tabua_hover.png")),
                         border=(12, 10), sticky="nsew", width=36, height=34)
        s.element_create("Selo.border", "image", img("acao_normal.png"),
                         ("pressed", img("acao_pressed.png")), ("active", img("acao_hover.png")),
                         border=(27, 26), sticky="nsew", width=60, height=54)
        for nome in ("TButton", "Acao.TButton"):
            s.layout(nome, [("Tabua.border", filhos)])
            s.configure(nome, foreground="#f6e7c8", font=T(16), padding=(14, 3), anchor="center")
            s.map(nome, foreground=[("disabled", "#b9a27c")])
        s.layout("Grande.TButton", [("Selo.border", filhos)])
        s.configure("Grande.TButton", foreground="#fbe9d2", font=T(21), padding=(34, 2), anchor="center")
        for nome in ("TRadiobutton", "TCheckbutton"):
            s.configure(nome, background=PAPEL, foreground=TINTA2, font=F(17), indicatorcolor=CAMPO,
                        indicatorbackground=CAMPO, upperbordercolor="#a9875a", lowerbordercolor="#a9875a")
            s.map(nome, background=[("active", PAPEL)], indicatorcolor=[("selected", LACRE)])
        for nome in ("TEntry", "TCombobox", "TSpinbox"):
            s.configure(nome, fieldbackground=CAMPO, foreground=TINTA, bordercolor="#a9875a",
                        lightcolor=CAMPO, darkcolor="#c9b07e", arrowcolor=TINTA2, background=PAPEL_ESC,
                        insertcolor=TINTA, padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", CAMPO)], foreground=[("readonly", TINTA)])
        s.configure("Horizontal.TScale", troughcolor="#d8c194", background="#8a6430", bordercolor="#8a6430")
        s.configure("Vertical.TScrollbar", background="#b8995f", troughcolor=PAPEL_ESC, arrowcolor=TINTA,
                    bordercolor="#a9875a", lightcolor="#c9ab70", darkcolor="#8a6430")
        for w in ("Label", "Listbox", "Text", "Entry", "Button", "Spinbox"):
            self.option_add(f"*{w}.font", F(17))
        self.option_add("*TCombobox*Listbox.font", F(16))
        self.option_add("*TCombobox*Listbox.background", CAMPO)
        self.option_add("*TCombobox*Listbox.foreground", TINTA)
        self.option_add("*TCombobox*Listbox.selectBackground", "#e2c88f")

    # ---------------- moldura: topo, área e status
    def montar_moldura(self):
        self.topo = tk.Frame(self, height=72)
        self.topo.pack(fill="x")
        self.topo.pack_propagate(False)
        logo = Image.open(os.path.join(PASTA, "icone.png")).resize((46, 46), Image.LANCZOS)
        self._logo = ImageTk.PhotoImage(logo)
        self.l_logo = tk.Label(self.topo, image=self._logo, bd=0)
        self.l_logo.pack(side="left", padx=(24, 12))
        self.l_nome = tk.Label(self.topo, text="Forja de Pergaminhos", font=T(30))
        self.l_nome.pack(side="left")
        self.voltar = ttk.Button(self.topo, text="← Voltar ao salão", command=self.inicio)
        self.chave = tk.Label(self.topo, cursor="hand2", bd=0)
        self.chave.pack(side="right", padx=(8, 26))
        self.chave.bind("<Button-1>", lambda e: self.trocar_tema())
        self.l_tema = tk.Label(self.topo, font=T(15))
        self.l_tema.pack(side="right")
        self.l_tema.bind("<Button-1>", lambda e: self.trocar_tema())
        self.linha_topo = tk.Frame(self, height=2)
        self.linha_topo.pack(fill="x")

        self.rodape = tk.Frame(self, height=34)
        self.rodape.pack(side="bottom", fill="x")
        self.rodape.pack_propagate(False)
        self.linha_rod = tk.Frame(self, height=1)
        self.linha_rod.pack(side="bottom", fill="x")
        self.brasa = tk.Canvas(self.rodape, width=22, height=22, highlightthickness=0)
        self.brasa.pack(side="left", padx=(14, 6))
        self.l_status = tk.Label(self.rodape, font=T(15), anchor="w")
        self.l_status.pack(side="left")
        self.metal = tk.Canvas(self.rodape, width=280, height=14, highlightthickness=0)
        versao = ""
        try:
            with open(os.path.join(PASTA, "versao.txt"), encoding="utf-8") as f:
                versao = "versão " + f.read().strip()
        except Exception:
            pass
        self.l_versao = tk.Label(self.rodape, text=versao, font=F(14, "italic"))
        self.l_versao.pack(side="right", padx=14)

        self.cv = tk.Canvas(self, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", self._redimensionou)
        self.cv.bind("<MouseWheel>", self._rolar)
        self.cv.bind("<Button-4>", lambda e: self._rolar(e, -1))
        self.cv.bind("<Button-5>", lambda e: self._rolar(e, 1))
        self._estado = "fria"
        self._texto_status = ESTADOS["fria"][2]

    def _rolar(self, e, d=None):
        if self.tela != "salao":
            return
        passos = d if d is not None else int(-e.delta / 120)
        self.cv.yview_scroll(passos * 3, "units")

    def trocar_tema(self):
        self.tema = "claro" if self.tema == "escuro" else "escuro"
        self._salvar_config()
        self.aplicar_tema()
        if self.tela == "salao":
            self.desenhar_salao()
        elif self.tela == "ferramenta":
            self.desenhar_fundo()
            self.cv.tag_lower("fundo")

    def aplicar_tema(self):
        t = TEMAS[self.tema]
        for w in (self.topo, self.l_logo, self.l_nome, self.l_tema, self.chave, self.rodape, self.brasa,
                  self.l_status, self.metal, self.l_versao):
            w.config(bg=t["barra"])
        self.l_nome.config(fg=t["titulo"])
        self.l_tema.config(fg=t["sub"], text=t["rotulo"])
        self.l_status.config(fg=t["sub"])
        self.l_versao.config(fg=t["sub"])
        self.linha_topo.config(bg=t["borda"])
        self.linha_rod.config(bg=t["borda"])
        self.chave.config(image=img(f"chave_{self.tema}.png"))
        self.cv.config(bg=t["fundo"])
        self.estado(self._estado, self._texto_status)

    # ---------------- fundo
    def desenhar_fundo(self):
        w, h = max(1, self.cv.winfo_width()), max(1, self.cv.winfo_height())
        if self.tela == "salao":
            h = max(h, int(float(self.cv.cget("scrollregion").split()[3])) if self.cv.cget("scrollregion") else h)
        base = pil(f"fundo_{self.tema}.jpg")
        esc = max(w / base.width, h / base.height, 1)
        im = base.resize((int(base.width * esc) + 1, int(base.height * esc) + 1), Image.BILINEAR) if esc > 1 else base
        im = im.crop((0, 0, w, h))
        self._fundo_img = ImageTk.PhotoImage(im)
        self.cv.delete("fundo")
        self.cv.create_image(0, 0, anchor="nw", image=self._fundo_img, tags="fundo")
        self.cv.tag_lower("fundo")

    def _redimensionou(self, e=None):
        if self._agendado:
            self.after_cancel(self._agendado)
        self._agendado = self.after(120, self._refazer)

    def _refazer(self):
        self._agendado = None
        if self.tela == "salao":
            self.desenhar_salao()
        elif self.tela == "ferramenta":
            self.desenhar_folha()

    # ---------------- salão
    def limpar(self):
        if self.area is not None:
            self.area.destroy()
            self.area = None
        self.cv.delete("all")

    def inicio(self):
        self.limpar()
        self.tela = "salao"
        self.voltar.pack_forget()
        if not self._ocupado:
            self.estado("fria")
        self.cv.yview_moveto(0)
        self.desenhar_salao()

    def desenhar_salao(self):
        t = TEMAS[self.tema]
        cv = self.cv
        cv.delete("all")
        W = max(cv.winfo_width(), 600)
        passo_x, passo_y = CW - 12, 168
        cols = max(2, min(4, (W - 10) // passo_x))
        linhas = (len(FERRAMENTAS) + cols - 1) // cols
        x0 = (W - cols * passo_x) // 2 - 6
        y0 = 132
        altura = y0 + linhas * passo_y + 40
        cv.configure(scrollregion=(0, 0, W, max(altura, cv.winfo_height())))
        self.desenhar_fundo()
        cv.create_text(W // 2, 54, text="O que vamos forjar hoje?", font=T(38), fill=t["titulo"])
        cv.create_text(W // 2, 92, text="Escolha um pergaminho para abrir a ferramenta",
                       font=F(20, "italic"), fill=t["sub"])
        m = W // 2
        cv.create_line(m - 180, 116, m - 26, 116, fill=t["titulo"], width=1)
        cv.create_line(m + 26, 116, m + 180, 116, fill=t["titulo"], width=1)
        cv.create_polygon(m, 110, m + 6, 116, m, 122, m - 6, 116, fill=t["titulo"])
        for dx in (-16, 16):
            cv.create_oval(m + dx - 3, 113, m + dx + 3, 119, fill=t["titulo"], outline="")
        for i, (cls, sigla, cor) in enumerate(FERRAMENTAS):
            x = x0 + (i % cols) * passo_x
            y = y0 + (i // cols) * passo_y
            tag = f"c{i}"
            base = cv.create_image(x, y, anchor="nw", image=img(f"cartao{i % 4}.png"), tags=(tag,))
            cv.create_image(x + 80, y + 95, image=img(f"selo_{cor}.png"), tags=(tag,))
            cv.create_text(x + 80, y + 94, text=sigla, font=T(19), fill="#fbead0", tags=(tag,))
            cv.create_text(x + 110, y + 72, text=cls.titulo, anchor="nw", font=T(18), fill=TINTA,
                           width=172, tags=(tag,))
            cv.create_text(x + 110, y + 96, text=cls.resumo, anchor="nw", font=F(15, "bold"), fill=TINTA2,
                           width=168, tags=(tag,))
            normal, brilho = img(f"cartao{i % 4}.png"), img(f"cartao{i % 4}_brilho.png")
            cv.tag_bind(tag, "<Enter>", lambda e, b=base, im=brilho: (cv.itemconfig(b, image=im),
                                                                     cv.config(cursor="hand2")))
            cv.tag_bind(tag, "<Leave>", lambda e, b=base, im=normal: (cv.itemconfig(b, image=im),
                                                                     cv.config(cursor="")))
            cv.tag_bind(tag, "<Button-1>", lambda e, c=cls, xx=x, yy=y: self.abrir(c, xx, yy))

    # ---------------- abrir pergaminho (animação)
    def _retangulo_folha(self):
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        return 22, 12, W - 22, H - 10

    def abrir(self, cls, x, y):
        cv = self.cv
        cv.config(cursor="")
        ox, oy = cv.canvasx(0), cv.canvasy(0)
        ini = (x + 40 - ox, y + 28 - oy, x + CW - 40 - ox, y + CH - 24 - oy)
        cv.yview_moveto(0)
        cv.delete("all")
        cv.configure(scrollregion=(0, 0, cv.winfo_width(), cv.winfo_height()))
        self.tela = "animando"
        self.desenhar_fundo()
        fim = self._retangulo_folha()
        quadros = []
        for k in range(1, 8):
            t = 1 - (1 - k / 7) ** 2.2
            r = [a + (b - a) * t for a, b in zip(ini, fim)]
            quadros.append(r)
        for r in quadros:
            im = ImageTk.PhotoImage(compor_folha(r[2] - r[0], r[3] - r[1], rapido=True))
            cv.delete("anim")
            cv.create_image(r[0], r[1], anchor="nw", image=im, tags="anim")
            cv._anim = im
            cv.update_idletasks()
            cv.update()
            self.after(14)
        self.montar_ferramenta(cls)

    def montar_ferramenta(self, cls):
        self.cv.delete("all")
        self.tela = "ferramenta"
        self.voltar.pack(side="left", padx=26)
        self.area = tk.Frame(self.cv, bg=PAPEL)
        self.atual = cls(self, self.area)
        self.atual.pack(fill="both", expand=True)
        self.desenhar_folha()

    def desenhar_folha(self):
        cv = self.cv
        x0, y0, x1, y1 = self._retangulo_folha()
        w, h = x1 - x0, y1 - y0
        self.desenhar_fundo()
        self._folha_img = ImageTk.PhotoImage(compor_folha(w, h))
        cv.delete("folha")
        cv.create_image(x0, y0, anchor="nw", image=self._folha_img, tags="folha")
        rh = max(18, min(40, int(h * 0.06)))
        ax0, ay0 = x0 + 18 + 44, y0 + rh + 16
        ax1, ay1 = x1 - 18 - 44, y1 - rh - 12
        cv.delete("janela")
        cv.create_window(ax0, ay0, anchor="nw", window=self.area, width=ax1 - ax0, height=ay1 - ay0,
                         tags="janela")
        cv.tag_raise("janela")

    # ---------------- status da forja
    def estado(self, tipo, texto=None):
        self._estado = tipo
        self._texto_status = texto or ESTADOS[tipo][2]
        cor, brilho, _ = ESTADOS[tipo]
        t = TEMAS[self.tema]
        b = self.brasa
        b.delete("all")
        if brilho:
            b.create_oval(1, 1, 21, 21, fill="", outline=brilho, width=2)
        b.create_oval(5, 5, 17, 17, fill=cor, outline="#000000" if tipo == "fria" else brilho)
        self.l_status.config(text=self._texto_status, fg=t["titulo"] if tipo != "fria" else t["sub"])
        if tipo == "acesa":
            self.metal.pack(side="left", padx=14, after=self.l_status)
            if self._prog is None:
                self._animar_metal()
        else:
            self.metal.pack_forget()

    def _animar_metal(self):
        if self._estado != "acesa":
            self._prog = None
            return
        m = self.metal
        m.delete("all")
        w, h = 280, 14
        m.create_rectangle(0, 0, w - 1, h - 1, fill="#2a2620", outline="#6b5530")
        frac = self._progresso_frac()
        if frac is None:  # sem número: brilho correndo
            self._anim_fase = (self._anim_fase + 7) % (w + 80)
            x = self._anim_fase - 80
            for i, cor in enumerate(("#8e2a0a", "#c4471a", "#e0661c", "#ffb060", "#ffd27a")):
                m.create_rectangle(max(1, x + i * 12), 2, min(w - 2, x + 80 - i * 12), h - 3, fill=cor, outline="")
        else:
            fim = max(2, int((w - 3) * frac))
            passos = 6
            for i in range(passos):
                cor = ("#8e2a0a", "#b33a12", "#d0561a", "#e0661c", "#f39a45", "#ffd27a")[i]
                m.create_rectangle(1 + fim * i // passos, 2, 1 + fim * (i + 1) // passos, h - 3, fill=cor, outline="")
        self._prog = self.after(40, self._animar_metal)

    def _progresso_frac(self):
        r = re.search(r"(\d+)\s+de\s+(\d+)", self._texto_status or "")
        if r and int(r.group(2)) > 0:
            return min(1, int(r.group(1)) / int(r.group(2)))
        return None

    def status(self, texto):
        self._fila.put(("status", texto))

    def tarefa(self, funcao, alvo, mensagem):
        if self._ocupado:
            messagebox.showinfo("Aguarde", "A forja ainda está trabalhando no pedido anterior.")
            return
        self._ocupado = True
        self.estado("acesa", "Forjando...")

        def rodar():
            try:
                funcao()
                self._fila.put(("ok", (alvo, mensagem)))
            except Exception as e:
                traceback.print_exc()
                self._fila.put(("erro", str(e) or e.__class__.__name__))
        threading.Thread(target=rodar, daemon=True).start()

    def _ler_fila(self):
        try:
            while True:
                tipo, dado = self._fila.get_nowait()
                if tipo == "status":
                    self.estado("acesa", "Forjando... " + dado)
                    continue
                self._ocupado = False
                if tipo == "ok":
                    alvo, mensagem = dado
                    self.estado("pronta", "Forjado! " + mensagem)
                    oque = "a pasta" if os.path.isdir(alvo) else "o arquivo"
                    if messagebox.askyesno("Forjado!", f"{mensagem}\n\nQuer abrir {oque} agora?"):
                        motor.abrir(alvo)
                else:
                    curto = dado.strip().splitlines()[0][:90] if dado.strip() else "erro desconhecido"
                    self.estado("falha", "A forja falhou · " + curto)
                    messagebox.showerror("A forja falhou", dado)
        except queue.Empty:
            pass
        self.after(100, self._ler_fila)


if __name__ == "__main__":
    try:
        App().mainloop()
    except SystemExit:
        raise
    except Exception:
        mostrar_erro_fatal("A Forja de Pergaminhos não conseguiu abrir.")
