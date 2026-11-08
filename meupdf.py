"""
Forja de Pergaminhos — ferramentas de PDF que rodam só no seu computador.
"""
import os
import sys
import queue
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

PASTA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PASTA)


def mostrar_erro_fatal(titulo):
    """Com pythonw não aparece janela preta, então o erro vira um aviso na tela e um arquivo erro.txt."""
    detalhe = traceback.format_exc()
    try:
        with open(os.path.join(PASTA, "erro.txt"), "w", encoding="utf-8") as f:
            f.write(detalhe)
    except Exception:
        pass
    r = tk.Tk()
    r.withdraw()
    messagebox.showerror("Forja de Pergaminhos", f"{titulo}\n\n{detalhe[-1500:]}\n\n(Isso também foi salvo em erro.txt na pasta do programa.)")
    r.destroy()
    sys.exit(1)


try:
    import motor  # noqa: E402
except Exception:
    mostrar_erro_fatal("Faltam bibliotecas. Rode o '1 - Instalar.bat' de novo.")

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception:
    TkinterDnD = None
    DND_FILES = None
BaseTk = tk.Tk
TEM_DND = False

FONTE = "Segoe UI" if motor.EH_WINDOWS else "DejaVu Sans"
FUNDO = "#f4f5f9"
BRANCO = "#ffffff"
TEXTO = "#33333b"
CINZA = "#77778a"
DESTAQUE = "#e5322d"

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
        tk.Label(self, text=titulo + dica, bg=FUNDO, fg=CINZA, font=(FONTE, 9)).pack(anchor="w")
        meio = tk.Frame(self, bg=FUNDO)
        meio.pack(fill="both", expand=True)
        self.lista = tk.Listbox(meio, height=altura, font=(FONTE, 10), activestyle="none",
                                selectbackground="#fde3e2", selectforeground=TEXTO,
                                relief="flat", highlightthickness=1, highlightcolor="#ddd")
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
                             bg=FUNDO, fg=CINZA, font=(FONTE, 10))
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
        super().__init__(pai, bg="#e3e4ea")
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

        barra = tk.Frame(self, bg="#e3e4ea")
        barra.pack(fill="x", pady=4)
        ttk.Button(barra, text="◀", width=3, command=lambda: self.ir(-1)).pack(side="left", padx=4)
        self.rotulo = tk.Label(barra, text="", bg="#e3e4ea", font=(FONTE, 10))
        self.rotulo.pack(side="left")
        ttk.Button(barra, text="▶", width=3, command=lambda: self.ir(1)).pack(side="left", padx=4)
        self.dica = tk.Label(barra, text="", bg="#e3e4ea", fg=CINZA, font=(FONTE, 9))
        self.dica.pack(side="right", padx=6)

        area = tk.Frame(self)
        area.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(area, bg="#cfd1d9", highlightthickness=0, cursor="crosshair")
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
                                    font=(FONTE, 11), fill=CINZA)
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
                                            fill=m.get("cor", DESTAQUE), font=(FONTE, 9, "bold"))
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
# Base das ferramentas
# =====================================================================
class Ferramenta(tk.Frame):
    titulo = ""
    descricao = ""

    def __init__(self, app):
        super().__init__(app.conteudo, bg=FUNDO)
        self.app = app
        tk.Label(self, text=self.titulo, bg=FUNDO, fg=TEXTO, font=(FONTE, 18, "bold")).pack(anchor="w")
        tk.Label(self, text=self.descricao, bg=FUNDO, fg=CINZA, font=(FONTE, 10),
                 wraplength=900, justify="left").pack(anchor="w", pady=(0, 12))
        self.corpo = tk.Frame(self, bg=FUNDO)
        self.corpo.pack(fill="both", expand=True)
        self.montar()

    def montar(self):
        pass

    def secao(self, pai, texto):
        tk.Label(pai, text=texto, bg=FUNDO, fg=TEXTO, font=(FONTE, 10, "bold"), wraplength=310,
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
            messagebox.showwarning("Falta algo", msg)
        return cond


class ComVisualizador(Ferramenta):
    """Layout com opções à esquerda e o documento à direita."""
    modo = "retangulo"

    def montar(self):
        esq = tk.Frame(self.corpo, bg=FUNDO, width=330)
        esq.pack(side="left", fill="y", padx=(0, 14))
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


# =====================================================================
# Ferramentas
# =====================================================================
class Juntar(Ferramenta):
    titulo = "Juntar PDF"
    descricao = "Coloque os arquivos na ordem que quiser e junte tudo num PDF só. Dá para misturar imagens também."

    def montar(self):
        self.lista = ListaArquivos(self.corpo, T_PDF + T_IMG, "PDFs e imagens, na ordem final", 16)
        self.lista.pack(fill="both", expand=True)
        self.botao_principal(self.corpo, "Juntar PDFs", self.rodar)

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
        self.info = tk.Label(self.corpo, text="", bg=FUNDO, fg=CINZA, font=(FONTE, 10))
        self.info.pack(anchor="w", pady=4)
        self.secao(self.corpo, "Como dividir")
        self.modo = tk.StringVar(value="intervalos")
        for v, t in (("intervalos", "Cada intervalo vira um PDF separado"),
                     ("extrair", "Juntar as páginas escolhidas num PDF só"),
                     ("todas", "Uma página por arquivo (todas)")):
            ttk.Radiobutton(self.corpo, text=t, value=v, variable=self.modo).pack(anchor="w")
        self.secao(self.corpo, "Páginas")
        self.paginas = ttk.Entry(self.corpo, width=40, font=(FONTE, 11))
        self.paginas.pack(anchor="w")
        tk.Label(self.corpo, text="Exemplos:  1-3, 5, 8-10     ou   4-   (da 4 até o fim)",
                 bg=FUNDO, fg=CINZA, font=(FONTE, 9)).pack(anchor="w")
        self.botao_principal(self.corpo, "Dividir PDF", self.rodar)

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
            lbl = tk.Label(f, text=f"pág. {idx + 1}", bg=f["bg"], fg=BRANCO if sel else CINZA, font=(FONTE, 9))
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

    def converter(self, entrada, saida):
        raise NotImplementedError

    def montar(self):
        self.lista = ListaArquivos(self.corpo, self.tipos, "Arquivos para converter", 12)
        self.lista.pack(fill="both", expand=True)
        self.extras(self.corpo)
        if self.aviso:
            tk.Label(self.corpo, text=self.aviso, bg=FUNDO, fg=CINZA, font=(FONTE, 9),
                     wraplength=850, justify="left").pack(anchor="w", pady=(8, 0))
        self.botao_principal(self.corpo, "Converter", self.rodar)

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
    titulo = "PDF para Word"
    descricao = "Transforma o PDF num documento do Word (.docx) para você editar."
    ext_saida = ".docx"
    aviso = "Funciona melhor com PDFs de texto. PDF escaneado (foto de papel) vira imagem dentro do Word."

    def converter(self, e, s):
        return motor.pdf_para_word(e, s)


class PdfPpt(Conversor):
    titulo = "PDF para PowerPoint"
    descricao = "Cada página do PDF vira um slide (.pptx)."
    ext_saida = ".pptx"
    aviso = "Os slides ficam idênticos ao PDF (como imagem). O texto de cada página vai nas anotações do slide."

    def converter(self, e, s):
        return motor.pdf_para_powerpoint(e, s)


class PdfExcel(Conversor):
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
    titulo = "Word para PDF"
    descricao = "Converte documentos do Word (.doc, .docx) em PDF."
    tipos = T_WORD


class PptPdf(OfficePdf):
    titulo = "PowerPoint para PDF"
    descricao = "Converte apresentações (.ppt, .pptx) em PDF."
    tipos = T_PPT


class ExcelPdf(OfficePdf):
    titulo = "Excel para PDF"
    descricao = "Converte planilhas (.xls, .xlsx) em PDF."
    tipos = T_EXCEL


class PdfPdfa(Conversor):
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
        self.botao_principal(self.corpo, "Criar PDF", self.rodar)

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
        self.texto = ttk.Entry(pai, width=36, font=(FONTE, 11))
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
        self.lista = tk.Listbox(pai, height=8, font=(FONTE, 9), relief="flat")
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
        self.texto = ttk.Entry(pai, width=34, font=(FONTE, 11))
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
                 bg=FUNDO, fg=DESTAQUE, font=(FONTE, 9), wraplength=310, justify="left").pack(anchor="w", pady=8)
        self.secao(pai, "Palavras para esconder")
        tk.Label(pai, text="separe por vírgula, ex.: CPF, 123.456.789-00", bg=FUNDO, fg=CINZA,
                 font=(FONTE, 9)).pack(anchor="w")
        self.termos = tk.Text(pai, height=4, width=36, font=(FONTE, 10), relief="flat")
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
                     font=(FONTE, 9)).pack(anchor="w", pady=(6, 0))
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
                 bg=FUNDO, fg=CINZA, font=(FONTE, 9), wraplength=700, justify="left").pack(anchor="w")
        self.botao_principal(self.corpo, "Traduzir", self.rodar)

    def rodar(self):
        c = self.arq.caminho
        if not self.precisa(c, "Escolha um PDF."):
            return
        cod = motor.IDIOMAS[self.idioma.get()]
        s = self.salvar_como(motor.nome_saida(c, cod, ".pdf"))
        if s:
            prog = lambda i, n: self.app.status(f"Traduzindo página {i} de {n}...")
            self.app.tarefa(lambda: motor.traduzir(c, s, cod, prog), s, "PDF traduzido!")


# ---------------------------------------------------------------- catálogo
FERRAMENTAS = [
    (Juntar, "⊕", "#e5322d"), (Dividir, "÷", "#e5322d"), (Organizar, "▦", "#e5322d"),
    (PdfWord, "W", "#2b5797"), (PdfPpt, "P", "#d24726"), (PdfExcel, "X", "#1e7145"),
    (WordPdf, "W", "#2b5797"), (PptPdf, "P", "#d24726"), (ExcelPdf, "X", "#1e7145"),
    (Editar, "✎", "#8e44ad"), (PdfJpg, "▣", "#d4a017"), (JpgPdf, "▣", "#d4a017"),
    (MarcaDagua, "≋", "#8e44ad"), (PdfPdfa, "A", "#2b5797"), (Ocultar, "▬", "#33333b"),
    (Recortar, "⌗", "#8e44ad"), (Formularios, "☰", "#8e44ad"), (Traduzir, "文", "#5b4ce5"),
]


# =====================================================================
# Janela principal
# =====================================================================
class App(BaseTk):
    def __init__(self):
        super().__init__()
        global TEM_DND
        if TkinterDnD is not None:
            try:
                TkinterDnD._require(self)
                TEM_DND = True
            except Exception:
                TEM_DND = False
        self.title("Forja de Pergaminhos")
        self.geometry("1180x780")
        self.minsize(900, 600)
        self.configure(bg=FUNDO)
        pasta = os.path.dirname(os.path.abspath(__file__))
        try:
            if motor.EH_WINDOWS:
                self.iconbitmap(os.path.join(pasta, "icone.ico"))
            else:
                self.iconphoto(True, tk.PhotoImage(file=os.path.join(pasta, "icone.png")))
        except Exception:
            pass
        self._fila = queue.Queue()
        self._ocupado = False
        self.estilos()

        topo = tk.Frame(self, bg=BRANCO, height=56)
        topo.pack(fill="x")
        topo.pack_propagate(False)
        tk.Label(topo, text="Forja de", bg=BRANCO, fg=TEXTO, font=(FONTE, 18, "bold")).pack(side="left", padx=(20, 4))
        tk.Label(topo, text="Pergaminhos", bg=BRANCO, fg=DESTAQUE, font=(FONTE, 18, "bold")).pack(side="left")
        self.voltar = ttk.Button(topo, text="← Todas as ferramentas", command=self.inicio)
        tk.Label(topo, text="tudo roda no seu computador", bg=BRANCO, fg=CINZA,
                 font=(FONTE, 9)).pack(side="right", padx=20)

        rodape = tk.Frame(self, bg=BRANCO, height=30)
        rodape.pack(side="bottom", fill="x")
        self.barra = ttk.Progressbar(rodape, mode="indeterminate", length=160)
        self.msg = tk.Label(rodape, text="Pronto", bg=BRANCO, fg=CINZA, font=(FONTE, 9))
        self.msg.pack(side="left", padx=12)

        self.conteudo = tk.Frame(self, bg=FUNDO)
        self.conteudo.pack(fill="both", expand=True, padx=24, pady=16)
        self.atual = None
        self.inicio()
        self.after(100, self._ler_fila)

    def estilos(self):
        s = ttk.Style(self)
        try:
            s.theme_use("vista" if motor.EH_WINDOWS else "clam")
        except tk.TclError:
            s.theme_use("clam")
        s.configure(".", font=(FONTE, 10))
        s.configure("TRadiobutton", background=FUNDO)
        s.configure("TCheckbutton", background=FUNDO)
        s.configure("Acao.TButton", font=(FONTE, 10, "bold"))
        s.configure("Grande.TButton", font=(FONTE, 12, "bold"), padding=(22, 8))

    def limpar(self):
        if self.atual is not None:
            self.atual.destroy()
        for w in self.conteudo.winfo_children():
            w.destroy()

    def inicio(self):
        self.limpar()
        self.voltar.pack_forget()
        rol = Rolavel(self.conteudo)
        rol.pack(fill="both", expand=True)
        self.atual = rol
        tk.Label(rol.dentro, text="O que vamos forjar hoje?", bg=FUNDO, fg=TEXTO,
                 font=(FONTE, 20, "bold")).grid(row=0, column=0, columnspan=4, pady=(4, 2))
        tk.Label(rol.dentro, text="Sem internet, sem limite, sem mandar seus arquivos para ninguém.",
                 bg=FUNDO, fg=CINZA, font=(FONTE, 11)).grid(row=1, column=0, columnspan=4, pady=(0, 16))
        for c in range(4):
            rol.dentro.columnconfigure(c, weight=1, uniform="c")
        for i, (cls, sigla, cor) in enumerate(FERRAMENTAS):
            self.cartao(rol.dentro, cls, sigla, cor).grid(row=2 + i // 4, column=i % 4, sticky="nsew", padx=7, pady=7)

    def cartao(self, pai, cls, sigla, cor):
        f = tk.Frame(pai, bg=BRANCO, padx=16, pady=14, highlightthickness=1, highlightbackground="#e2e3ea",
                     cursor="hand2")
        ic = tk.Label(f, text=sigla, bg=cor, fg="white", font=(FONTE, 13, "bold"), width=3)
        ic.pack(anchor="w")
        t = tk.Label(f, text=cls.titulo, bg=BRANCO, fg=TEXTO, font=(FONTE, 12, "bold"))
        t.pack(anchor="w", pady=(8, 2))
        d = tk.Label(f, text=getattr(cls, "resumo", cls.descricao), bg=BRANCO, fg=CINZA, font=(FONTE, 9), wraplength=230,
                     justify="left", height=3, anchor="nw")
        d.pack(anchor="w", fill="x")
        for w in (f, ic, t, d):
            w.bind("<Button-1>", lambda e: self.abrir(cls))
            w.bind("<Enter>", lambda e: f.config(highlightbackground=cor))
            w.bind("<Leave>", lambda e: f.config(highlightbackground="#e2e3ea"))
        return f

    def abrir(self, cls):
        self.limpar()
        self.voltar.pack(side="left", padx=24)
        self.atual = cls(self)
        self.atual.pack(fill="both", expand=True)

    # ---------------- tarefas em segundo plano
    def status(self, texto):
        self._fila.put(("status", texto))

    def tarefa(self, funcao, alvo, mensagem):
        if self._ocupado:
            messagebox.showinfo("Aguarde", "Ainda estou terminando a tarefa anterior.")
            return
        self._ocupado = True
        self.barra.pack(side="right", padx=12)
        self.barra.start(12)
        self.msg.config(text="Trabalhando...")

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
                    self.msg.config(text=dado)
                    continue
                self._ocupado = False
                self.barra.stop()
                self.barra.pack_forget()
                if tipo == "ok":
                    alvo, mensagem = dado
                    self.msg.config(text=mensagem)
                    oque = "a pasta" if os.path.isdir(alvo) else "o arquivo"
                    if messagebox.askyesno("Pronto!", f"{mensagem}\n\nQuer abrir {oque} agora?"):
                        motor.abrir(alvo)
                else:
                    self.msg.config(text="Deu erro")
                    messagebox.showerror("Não deu certo", dado)
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
