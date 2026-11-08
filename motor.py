"""
Motor do Meu PDF: todas as operações com PDF ficam aqui.
A interface (meupdf.py) só chama estas funções.
"""
import os
import re
import sys
import glob
import time
import shutil
import subprocess
import tempfile

import pymupdf as fitz  # PyMuPDF
from PIL import Image

EH_WINDOWS = sys.platform.startswith("win")


# ---------------------------------------------------------------- utilidades
def nome_saida(entrada, sufixo, extensao=None, pasta=None):
    """Gera um nome de arquivo de saída que não sobrescreve nada."""
    base = os.path.splitext(os.path.basename(entrada))[0]
    ext = extensao or os.path.splitext(entrada)[1]
    pasta = pasta or os.path.dirname(os.path.abspath(entrada))
    caminho = os.path.join(pasta, f"{base}_{sufixo}{ext}")
    n = 2
    while os.path.exists(caminho):
        caminho = os.path.join(pasta, f"{base}_{sufixo}_{n}{ext}")
        n += 1
    return caminho


def interpretar_intervalos(texto, total):
    """'1-3, 5, 8-' -> [[0,1,2],[4],[7,...,total-1]] (índices começando em 0)."""
    grupos = []
    for parte in texto.replace(";", ",").split(","):
        parte = parte.strip()
        if not parte:
            continue
        if "-" in parte:
            ini, fim = parte.split("-", 1)
            ini = int(ini) if ini.strip() else 1
            fim = int(fim) if fim.strip() else total
        else:
            ini = fim = int(parte)
        if ini < 1 or fim > total or ini > fim:
            raise ValueError(f"Intervalo inválido: '{parte}' (o PDF tem {total} páginas)")
        grupos.append(list(range(ini - 1, fim)))
    if not grupos:
        raise ValueError("Informe pelo menos uma página ou intervalo.")
    return grupos


def contar_paginas(caminho):
    with fitz.open(caminho) as doc:
        return doc.page_count


def _salvar(doc, saida):
    doc.save(saida, garbage=3, deflate=True)


# ---------------------------------------------------------------- juntar
def juntar(arquivos, saida):
    final = fitz.open()
    for arq in arquivos:
        ext = os.path.splitext(arq)[1].lower()
        if ext == ".pdf":
            with fitz.open(arq) as d:
                final.insert_pdf(d)
        else:  # imagem no meio da lista: vira uma página
            with fitz.open(arq) as img:
                pdfbytes = img.convert_to_pdf()
            with fitz.open("pdf", pdfbytes) as d:
                final.insert_pdf(d)
    _salvar(final, saida)
    final.close()
    return saida


# ---------------------------------------------------------------- dividir
def dividir_intervalos(entrada, intervalos, pasta):
    """Cada intervalo vira um arquivo separado."""
    saidas = []
    with fitz.open(entrada) as doc:
        grupos = interpretar_intervalos(intervalos, doc.page_count)
        for g in grupos:
            novo = fitz.open()
            for i in g:
                novo.insert_pdf(doc, from_page=i, to_page=i)
            rotulo = f"pag{g[0]+1}" if len(g) == 1 else f"pag{g[0]+1}-{g[-1]+1}"
            s = nome_saida(entrada, rotulo, ".pdf", pasta)
            _salvar(novo, s)
            novo.close()
            saidas.append(s)
    return saidas


def dividir_todas(entrada, pasta):
    """Uma página por arquivo."""
    with fitz.open(entrada) as doc:
        total = doc.page_count
    return dividir_intervalos(entrada, ",".join(str(i) for i in range(1, total + 1)), pasta)


def extrair_paginas(entrada, intervalos, saida):
    """Junta as páginas escolhidas num único PDF."""
    with fitz.open(entrada) as doc:
        grupos = interpretar_intervalos(intervalos, doc.page_count)
        novo = fitz.open()
        for g in grupos:
            for i in g:
                novo.insert_pdf(doc, from_page=i, to_page=i)
        _salvar(novo, saida)
        novo.close()
    return saida


# ---------------------------------------------------------------- organizar
def organizar(entrada, ordem, rotacoes, saida):
    """
    ordem: lista de índices de página (começando em 0) na nova ordem.
           Página fora da lista é excluída; índice repetido duplica a página.
    rotacoes: lista paralela com graus extras (0, 90, 180, 270) para cada item.
    """
    with fitz.open(entrada) as doc:
        novo = fitz.open()
        for idx, rot in zip(ordem, rotacoes):
            novo.insert_pdf(doc, from_page=idx, to_page=idx)
            if rot:
                p = novo[-1]
                p.set_rotation((p.rotation + rot) % 360)
        _salvar(novo, saida)
        novo.close()
    return saida


def miniatura_png(caminho, indice, largura=160, rotacao_extra=0):
    """Devolve bytes PNG de uma página, para mostrar na tela."""
    with fitz.open(caminho) as doc:
        p = doc[indice]
        zoom = largura / p.rect.width
        mat = fitz.Matrix(zoom, zoom).prerotate(rotacao_extra)
        return p.get_pixmap(matrix=mat, alpha=False).tobytes("png")


# ---------------------------------------------------------------- PDF -> imagens
def pdf_para_imagens(entrada, pasta, formato="jpg", dpi=150):
    saidas = []
    with fitz.open(entrada) as doc:
        base = os.path.splitext(os.path.basename(entrada))[0]
        sub = os.path.join(pasta, base + "_imagens")
        os.makedirs(sub, exist_ok=True)
        for i, p in enumerate(doc):
            pix = p.get_pixmap(dpi=dpi, alpha=False)
            s = os.path.join(sub, f"{base}_pag{i+1:03d}.{formato}")
            if formato == "jpg":
                pix.save(s, jpg_quality=90)
            else:
                pix.save(s)
            saidas.append(s)
    return saidas


def extrair_imagens_embutidas(entrada, pasta):
    """Tira as fotos/figuras que estão dentro do PDF, no tamanho original."""
    saidas = []
    with fitz.open(entrada) as doc:
        base = os.path.splitext(os.path.basename(entrada))[0]
        sub = os.path.join(pasta, base + "_figuras")
        os.makedirs(sub, exist_ok=True)
        vistos = set()
        for i, p in enumerate(doc):
            for img in p.get_images(full=True):
                xref = img[0]
                if xref in vistos:
                    continue
                vistos.add(xref)
                info = doc.extract_image(xref)
                if not info or info["width"] < 40 or info["height"] < 40:
                    continue
                s = os.path.join(sub, f"{base}_pag{i+1}_fig{len(saidas)+1}.{info['ext']}")
                with open(s, "wb") as f:
                    f.write(info["image"])
                saidas.append(s)
    return saidas


# ---------------------------------------------------------------- imagens -> PDF
TAMANHOS = {"A4": fitz.paper_rect("a4"), "Carta": fitz.paper_rect("letter")}


def imagens_para_pdf(imagens, saida, tamanho="Original", margem=0):
    """tamanho: 'Original', 'A4' ou 'Carta'. A orientação acompanha cada imagem."""
    final = fitz.open()
    for arq in imagens:
        with Image.open(arq) as im:
            larg, alt = im.size
            # corrige foto de celular girada pelo EXIF
            try:
                from PIL import ImageOps
                im2 = ImageOps.exif_transpose(im)
                if im2.size != im.size or im2 is not im:
                    larg, alt = im2.size
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    im2.convert("RGB").save(tmp.name)
                    arq = tmp.name
            except Exception:
                pass
        if tamanho == "Original":
            pag = final.new_page(width=larg + 2 * margem, height=alt + 2 * margem)
        else:
            r = TAMANHOS[tamanho]
            w, h = (r.width, r.height) if alt >= larg else (r.height, r.width)
            pag = final.new_page(width=w, height=h)
        area = pag.rect + (margem, margem, -margem, -margem)
        pag.insert_image(area, filename=arq, keep_proportion=True)
    _salvar(final, saida)
    final.close()
    return saida


# ---------------------------------------------------------------- PDF -> Office
def pdf_para_word(entrada, saida, progresso=None):
    import logging
    from pdf2docx import Converter

    class Andamento(logging.Handler):
        fase = 0

        def emit(self, rec):
            if progresso is None:
                return
            msg = rec.getMessage()
            if "Creating pages" in msg:
                Andamento.fase = 1
            m = re.search(r"\((\d+)/(\d+)\) Page", msg)
            if m:
                i, n = int(m.group(1)), int(m.group(2))
                etapa = "lendo" if Andamento.fase == 0 else "montando"
                progresso((Andamento.fase + i / n) / 2, f"{etapa} página {i} de {n}")

    h = Andamento()
    logging.getLogger().addHandler(h)
    cv = Converter(entrada)
    try:
        cv.convert(saida)
    finally:
        cv.close()
        logging.getLogger().removeHandler(h)
    return saida


def pdf_para_excel(entrada, saida):
    """Cada tabela encontrada vira uma aba. Se não houver tabela, o texto vai linha a linha."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    achou = 0
    with fitz.open(entrada) as doc:
        for i, p in enumerate(doc):
            try:
                tabelas = p.find_tables().tables
            except Exception:
                tabelas = []
            for t in tabelas:
                achou += 1
                ws = wb.create_sheet(f"Pág{i+1} Tab{achou}"[:31])
                for linha in t.extract():
                    ws.append([_numero_ou_texto(c) for c in linha])
                _ajustar_colunas(ws, get_column_letter)
        if achou == 0:
            ws = wb.create_sheet("Texto")
            for i, p in enumerate(doc):
                for linha in p.get_text().splitlines():
                    if linha.strip():
                        ws.append([i + 1, linha])
            _ajustar_colunas(ws, get_column_letter)
    wb.save(saida)
    return saida, achou


def _numero_ou_texto(c):
    if c is None:
        return ""
    c = str(c).strip()
    t = c.replace(".", "").replace(",", ".") if "," in c else c
    try:
        return float(t) if "." in t else int(t)
    except ValueError:
        return c


def _ajustar_colunas(ws, get_column_letter):
    for col in ws.columns:
        maior = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(10, maior + 2), 60)


def pdf_para_powerpoint(entrada, saida, dpi=150):
    """Cada página vira um slide (como imagem, fiel ao original)."""
    from pptx import Presentation
    from pptx.util import Emu
    prs = Presentation()
    with fitz.open(entrada) as doc:
        r = doc[0].rect
        prs.slide_width = Emu(int(r.width * 12700))
        prs.slide_height = Emu(int(r.height * 12700))
        branco = prs.slide_layouts[6]
        tmpdir = tempfile.mkdtemp()
        for i, p in enumerate(doc):
            img = os.path.join(tmpdir, f"p{i}.png")
            p.get_pixmap(dpi=dpi, alpha=False).save(img)
            slide = prs.slides.add_slide(branco)
            slide.shapes.add_picture(img, 0, 0, prs.slide_width, prs.slide_height)
            texto = p.get_text().strip()
            if texto:  # o texto da página fica nas anotações do slide
                slide.notes_slide.notes_text_frame.text = texto
    prs.save(saida)
    shutil.rmtree(tmpdir, ignore_errors=True)
    return saida


# ---------------------------------------------------------------- Office -> PDF
def _achar_libreoffice():
    for nome in ("soffice", "libreoffice"):
        c = shutil.which(nome)
        if c:
            return c
    if EH_WINDOWS:
        for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                   os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            c = os.path.join(pf, "LibreOffice", "program", "soffice.exe")
            if os.path.exists(c):
                return c
    return None


def _office_ms(entrada, saida):
    """Usa o Microsoft Office instalado no Windows (melhor fidelidade)."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    entrada, saida = os.path.abspath(entrada), os.path.abspath(saida)
    ext = os.path.splitext(entrada)[1].lower()
    try:
        if ext in (".doc", ".docx", ".odt", ".rtf", ".txt"):
            app = win32com.client.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            d = app.Documents.Open(entrada, ReadOnly=True, AddToRecentFiles=False)
            try:
                d.ExportAsFixedFormat(saida, 17)
            finally:
                d.Close(False)
                app.Quit()
        elif ext in (".xls", ".xlsx", ".xlsm", ".ods", ".csv"):
            app = win32com.client.DispatchEx("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            wb = app.Workbooks.Open(entrada, ReadOnly=True)
            try:
                wb.ExportAsFixedFormat(0, saida)
            finally:
                wb.Close(False)
                app.Quit()
        elif ext in (".ppt", ".pptx", ".odp"):
            app = win32com.client.DispatchEx("PowerPoint.Application")
            pres = app.Presentations.Open(entrada, ReadOnly=True, WithWindow=False)
            try:
                pres.SaveAs(saida, 32)
            finally:
                pres.Close()
                app.Quit()
        else:
            raise ValueError("Formato não suportado")
    finally:
        pythoncom.CoUninitialize()
    return saida


def _office_libre(entrada, saida):
    soffice = _achar_libreoffice()
    if not soffice:
        raise RuntimeError("LibreOffice não encontrado")
    tmp = tempfile.mkdtemp()
    flags = subprocess.CREATE_NO_WINDOW if EH_WINDOWS else 0
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, entrada],
                   check=True, capture_output=True, timeout=300, creationflags=flags)
    gerado = os.path.join(tmp, os.path.splitext(os.path.basename(entrada))[0] + ".pdf")
    if not os.path.exists(gerado):
        raise RuntimeError("O LibreOffice não gerou o PDF")
    shutil.move(gerado, saida)
    shutil.rmtree(tmp, ignore_errors=True)
    return saida


def office_para_pdf(entrada, saida):
    erros = []
    if EH_WINDOWS:
        try:
            return _office_ms(entrada, saida)
        except Exception as e:
            erros.append(f"Microsoft Office: {e}")
    try:
        return _office_libre(entrada, saida)
    except Exception as e:
        erros.append(f"LibreOffice: {e}")
    raise RuntimeError(
        "Para converter Word, Excel ou PowerPoint em PDF é preciso ter o Microsoft Office "
        "ou o LibreOffice (gratuito, libreoffice.org) instalado.\n\n" + "\n".join(erros))


# ---------------------------------------------------------------- editar (texto)
def _cor(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))


def adicionar_textos(entrada, itens, saida):
    """
    itens: lista de dicts {pagina, x, y, texto, tamanho, cor('#rrggbb')}
    x, y em coordenadas da página como aparece na tela (origem no canto superior esquerdo).
    """
    with fitz.open(entrada) as doc:
        for it in itens:
            p = doc[it["pagina"]]
            ponto = fitz.Point(it["x"], it["y"]) * p.derotation_matrix
            p.insert_text(ponto, it["texto"], fontsize=it["tamanho"], fontname="helv",
                          color=_cor(it["cor"]), rotate=p.rotation)
        _salvar(doc, saida)
    return saida


def adicionar_imagens(entrada, itens, saida):
    """itens: {pagina, x0, y0, x1, y1, arquivo} — ex.: colar uma assinatura escaneada ou logo."""
    with fitz.open(entrada) as doc:
        for it in itens:
            p = doc[it["pagina"]]
            r = fitz.Rect(it["x0"], it["y0"], it["x1"], it["y1"]) * p.derotation_matrix
            p.insert_image(r, filename=it["arquivo"], keep_proportion=True, rotate=p.rotation)
        _salvar(doc, saida)
    return saida


# ---------------------------------------------------------------- marca d'água
def marca_dagua_texto(entrada, saida, texto, tamanho=60, cor="#888888",
                      opacidade=0.3, angulo=45, posicao="centro"):
    with fitz.open(entrada) as doc:
        fonte = fitz.Font("helv")
        largura = fonte.text_length(texto, fontsize=tamanho)
        for p in doc:
            r = p.rect
            if posicao == "centro":
                c = fitz.Point(r.width / 2, r.height / 2)
            elif posicao == "topo":
                c = fitz.Point(r.width / 2, tamanho + 20)
            else:  # rodapé
                c = fitz.Point(r.width / 2, r.height - 30)
            c = c * p.derotation_matrix
            inicio = fitz.Point(c.x - largura / 2, c.y + tamanho / 3)
            giro = fitz.Matrix(angulo) if angulo else fitz.Identity
            p.insert_text(inicio, texto, fontsize=tamanho, fontname="helv", color=_cor(cor),
                          fill_opacity=opacidade, stroke_opacity=opacidade,
                          morph=(c, giro), overlay=True)
        _salvar(doc, saida)
    return saida


def marca_dagua_imagem(entrada, saida, imagem, escala=0.4, opacidade=0.3):
    with Image.open(imagem) as im:
        im = im.convert("RGBA")
        alfa = im.getchannel("A").point(lambda v: int(v * opacidade))
        im.putalpha(alfa)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        im.save(tmp)
        prop = im.height / im.width
    with fitz.open(entrada) as doc:
        for p in doc:
            r = p.rect
            w = r.width * escala
            h = w * prop
            area = fitz.Rect((r.width - w) / 2, (r.height - h) / 2,
                             (r.width + w) / 2, (r.height + h) / 2) * p.derotation_matrix
            p.insert_image(area, filename=tmp, overlay=True, rotate=p.rotation)
        _salvar(doc, saida)
    os.remove(tmp)
    return saida


# ---------------------------------------------------------------- PDF/A
def _achar_ghostscript():
    for nome in ("gswin64c", "gswin32c", "gs"):
        c = shutil.which(nome)
        if c:
            return c
    if EH_WINDOWS:
        for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                   os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            achados = sorted(glob.glob(os.path.join(pf, "gs", "gs*", "bin", "gswin*c.exe")))
            if achados:
                return achados[-1]
    return None


def pdf_para_pdfa(entrada, saida, nivel=2):
    gs = _achar_ghostscript()
    if not gs:
        raise RuntimeError(
            "Para gerar PDF/A é preciso ter o Ghostscript instalado (gratuito).\n"
            "Baixe em ghostscript.com/releases, instale e tente de novo.")
    flags = subprocess.CREATE_NO_WINDOW if EH_WINDOWS else 0
    cmd = [gs, f"-dPDFA={nivel}", "-dBATCH", "-dNOPAUSE", "-dNOOUTERSAVE", "-dQUIET",
           "-sColorConversionStrategy=RGB", "-sDEVICE=pdfwrite",
           "-dPDFACompatibilityPolicy=1", f"-sOutputFile={saida}", entrada]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=flags)
    if r.returncode != 0 or not os.path.exists(saida):
        raise RuntimeError("O Ghostscript não conseguiu converter:\n" + (r.stderr or r.stdout)[-800:])
    return saida


# ---------------------------------------------------------------- ocultar (tarja preta)
def ocultar(entrada, saida, areas=None, termos=None):
    """
    Remove DE VERDADE o conteúdo (não é só um retângulo por cima).
    areas: lista de {pagina, x0, y0, x1, y1}; termos: lista de palavras a apagar em todo o PDF.
    """
    total = 0
    with fitz.open(entrada) as doc:
        for a in areas or []:
            p = doc[a["pagina"]]
            r = fitz.Rect(a["x0"], a["y0"], a["x1"], a["y1"]) * p.derotation_matrix
            p.add_redact_annot(r, fill=(0, 0, 0))
            total += 1
        for termo in termos or []:
            termo = termo.strip()
            if not termo:
                continue
            for p in doc:
                for r in p.search_for(termo):
                    p.add_redact_annot(r, fill=(0, 0, 0))
                    total += 1
        for p in doc:
            p.apply_redactions()
        doc.set_metadata({})
        _salvar(doc, saida)
    return saida, total


# ---------------------------------------------------------------- recortar
def recortar(entrada, saida, x0, y0, x1, y1, paginas=None):
    """Retângulo em coordenadas da tela (página como aparece). paginas=None -> todas."""
    with fitz.open(entrada) as doc:
        alvo = range(doc.page_count) if paginas is None else paginas
        for i in alvo:
            p = doc[i]
            r = fitz.Rect(x0, y0, x1, y1) * p.derotation_matrix
            r.normalize()
            # converte para o espaço do mediabox e garante que fica dentro dele
            mb = p.mediabox
            r = (r + (mb.x0, mb.y0, mb.x0, mb.y0)) & mb
            if r.is_empty:
                continue
            p.set_cropbox(fitz.Rect(r.x0 - mb.x0, r.y0 - mb.y0, r.x1 - mb.x0, r.y1 - mb.y0))
        _salvar(doc, saida)
    return saida


# ---------------------------------------------------------------- formulários
TIPOS_CAMPO = {
    fitz.PDF_WIDGET_TYPE_TEXT: "texto",
    fitz.PDF_WIDGET_TYPE_CHECKBOX: "marcar",
    fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "opcao",
    fitz.PDF_WIDGET_TYPE_COMBOBOX: "lista",
    fitz.PDF_WIDGET_TYPE_LISTBOX: "lista",
}


def ler_campos(entrada):
    campos = []
    with fitz.open(entrada) as doc:
        for i, p in enumerate(doc):
            for w in p.widgets():
                tipo = TIPOS_CAMPO.get(w.field_type)
                if not tipo:
                    continue
                campos.append({
                    "pagina": i, "nome": w.field_name, "tipo": tipo,
                    "valor": w.field_value, "opcoes": list(w.choice_values or []),
                    "rotulo": w.field_label or w.field_name,
                    "estado_on": w.on_state() if tipo in ("marcar", "opcao") else None,
                    "xref": w.xref,
                    "rect": tuple(w.rect * p.rotation_matrix),
                })
    return campos


def preencher_campos(entrada, valores, saida, travar=False):
    """valores: {xref: valor}. travar=True deixa o formulário só leitura depois."""
    with fitz.open(entrada) as doc:
        for p in doc:
            for w in p.widgets():
                if w.xref not in valores:
                    continue
                v = valores[w.xref]
                if w.field_type in (fitz.PDF_WIDGET_TYPE_CHECKBOX, fitz.PDF_WIDGET_TYPE_RADIOBUTTON):
                    w.field_value = w.on_state() if v else "Off"
                else:
                    w.field_value = v
                if travar:
                    w.field_flags |= fitz.PDF_FIELD_IS_READ_ONLY
                w.update()
        _salvar(doc, saida)
    return saida


def criar_campo_texto(entrada, saida, pagina, x0, y0, x1, y1, nome):
    """Cria um campo de texto preenchível novo num PDF comum."""
    with fitz.open(entrada) as doc:
        p = doc[pagina]
        w = fitz.Widget()
        w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w.field_name = nome
        w.rect = fitz.Rect(x0, y0, x1, y1) * p.derotation_matrix
        w.text_fontsize = 0
        w.border_color = (0.6, 0.6, 0.6)
        p.add_widget(w)
        _salvar(doc, saida)
    return saida


# ---------------------------------------------------------------- forja em processo separado
class Cancelado(Exception):
    """O usuário cancelou a forja."""


def _alvo_processo(nome, args, fila):
    """Roda dentro do processo filho: executa a função e manda o andamento de volta."""
    try:
        func = globals()[nome]
        kwargs = {}
        if nome == "pdf_para_word":
            kwargs["progresso"] = lambda f, t: fila.put(("prog", f, t))
        res = func(*args, **kwargs)
        fila.put(("ok", res))
    except Exception as e:  # noqa: BLE001
        fila.put(("erro", f"{e.__class__.__name__}: {e}" if not str(e) else str(e)))


def rodar_em_processo(nome, args, progresso=None, cancelado=None, sem_resposta=150):
    """
    Roda uma função pesada num processo separado, que pode ser encerrado na hora.
    Para se o usuário cancelar ou se ficar sem dar sinal de vida por `sem_resposta` segundos.
    """
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    fila = ctx.Queue()
    proc = ctx.Process(target=_alvo_processo, args=(nome, args, fila), daemon=True)
    proc.start()
    ultimo = time.time()
    try:
        while True:
            if cancelado and cancelado():
                raise Cancelado()
            try:
                tipo, *dado = fila.get(timeout=0.15)
            except Exception:
                if not proc.is_alive():
                    try:
                        tipo, *dado = fila.get(timeout=1)
                    except Exception:
                        raise RuntimeError("A conversão parou sem avisar o motivo.")
                elif time.time() - ultimo > sem_resposta:
                    raise RuntimeError(
                        f"A conversão ficou {sem_resposta} segundos sem avançar e foi interrompida. "
                        "Este arquivo pode ter algo que a ferramenta não consegue ler.")
                else:
                    continue
            ultimo = time.time()
            if tipo == "prog":
                if progresso:
                    progresso(*dado)
            elif tipo == "ok":
                return dado[0]
            else:
                raise RuntimeError(dado[0])
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(3)
            if proc.is_alive():
                proc.kill()


def impressao_digital(caminho):
    """Identifica o arquivo pelo conteúdo (vale mesmo se renomear ou mover)."""
    import hashlib
    h = hashlib.sha1()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ---------------------------------------------------------------- abrir pasta/arquivo
def abrir(caminho):
    try:
        if EH_WINDOWS:
            os.startfile(caminho)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
    except Exception:
        pass
