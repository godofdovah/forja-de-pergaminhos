"""
Teste automático da Forja de Pergaminhos (roda no GitHub, no Windows, com o programa já montado).
Uso: "Forja de Pergaminhos.exe" --autoteste <pasta>
Gera <pasta>/resultados.txt e uma foto de cada tela.
"""
import os
import sys
import time
import threading
import traceback


def _escrever(pasta, linha):
    with open(os.path.join(pasta, "resultados.txt"), "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def _com_tempo(func, limite):
    res = {}

    def alvo():
        try:
            res["ok"] = func()
        except Exception as e:
            res["erro"] = f"{e.__class__.__name__}: {e}"
            res["tb"] = traceback.format_exc()
    t = threading.Thread(target=alvo, daemon=True)
    ini = time.time()
    t.start()
    t.join(limite)
    dur = time.time() - ini
    if t.is_alive():
        return "TRAVOU", dur, f"passou de {limite}s"
    if "erro" in res:
        return "FALHOU", dur, res["erro"]
    return "OK", dur, ""


def arquivos_de_teste(pasta, motor):
    fitz = motor.fitz
    from PIL import Image
    img = os.path.join(pasta, "foto.png")
    Image.new("RGB", (500, 350), (40, 120, 200)).save(img)
    base = os.path.join(pasta, "boletim.pdf")
    d = fitz.open()
    for i in range(4):
        p = d.new_page()
        p.insert_text((60, 70), f"Boletim epidemiológico - Semana {23 + i}", fontsize=16)
        p.insert_textbox(fitz.Rect(60, 90, 540, 170), "Casos notificados de chikungunya por "
                         "município. Dados sujeitos a revisão. " * 3, fontsize=10)
        y = 200
        linhas = [["Município", "Casos", "Incidência"]] + [[f"Cidade {k}", str(10 * k + i), f"{k},{i}"] for k in range(1, 12)]
        for r, linha in enumerate(linhas):
            for c, val in enumerate(linha):
                rect = fitz.Rect(60 + c * 150, y + r * 20, 210 + c * 150, y + 20 + r * 20)
                p.draw_rect(rect, color=(0, 0, 0), width=0.6)
                p.insert_text(rect.bl + (4, -6), val, fontsize=9)
        p.insert_image(fitz.Rect(320, 520, 540, 680), filename=img)
    d.save(base)
    d.close()
    form = os.path.join(pasta, "form.pdf")
    d = fitz.open()
    p = d.new_page()
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w.field_name = "nome"
    w.rect = fitz.Rect(72, 72, 300, 92)
    p.add_widget(w)
    d.save(form)
    d.close()
    return base, form, img


def teste_motor(pasta, motor):
    base, form, img = arquivos_de_teste(pasta, motor)
    s = lambda n: os.path.join(pasta, n)  # noqa: E731
    casos = [
        ("Juntar", lambda: motor.juntar([base, img, base], s("junto.pdf"))),
        ("Dividir", lambda: motor.dividir_intervalos(base, "1-2,4", pasta)),
        ("Organizar", lambda: motor.organizar(base, [3, 0, 1], [0, 90, 0], s("org.pdf"))),
        ("PDF -> Word", lambda: motor.pdf_para_word(base, s("boletim.docx"))),
        ("PDF -> Excel", lambda: motor.pdf_para_excel(base, s("boletim.xlsx"))),
        ("PDF -> PowerPoint", lambda: motor.pdf_para_powerpoint(base, s("boletim.pptx"))),
        ("Word -> PDF", lambda: motor.office_para_pdf(s("boletim.docx"), s("volta_docx.pdf"))),
        ("Excel -> PDF", lambda: motor.office_para_pdf(s("boletim.xlsx"), s("volta_xlsx.pdf"))),
        ("PowerPoint -> PDF", lambda: motor.office_para_pdf(s("boletim.pptx"), s("volta_pptx.pdf"))),
        ("PDF -> JPG", lambda: motor.pdf_para_imagens(base, pasta, "jpg", 120)),
        ("JPG -> PDF", lambda: motor.imagens_para_pdf([img, img], s("imgs.pdf"), "A4", 20)),
        ("Editar", lambda: motor.adicionar_textos(base, [{"pagina": 0, "x": 80, "y": 300, "texto": "Revisado ção",
                                                          "tamanho": 14, "cor": "#aa0000"}], s("edit.pdf"))),
        ("Marca d'água", lambda: motor.marca_dagua_texto(base, s("marca.pdf"), "CONFIDENCIAL")),
        ("PDF/A", lambda: motor.pdf_para_pdfa(base, s("pdfa.pdf"))),
        ("Ocultar", lambda: motor.ocultar(base, s("oculto.pdf"), [], ["chikungunya"])),
        ("Recortar", lambda: motor.recortar(base, s("rec.pdf"), 40, 40, 560, 500)),
        ("Formulários", lambda: motor.preencher_campos(form, {motor.ler_campos(form)[0]["xref"]: "Cleiton"},
                                                        s("form_ok.pdf"))),
        ("Traduzir", lambda: motor.traduzir(base, s("traduzido.pdf"), "en")),
    ]
    for nome, f in casos:
        estado, dur, msg = _com_tempo(f, 180)
        _escrever(pasta, f"{estado:7} {nome:20} {dur:6.1f}s  {msg}")


def teste_telas(pasta, modulo):
    from PIL import ImageGrab
    app = modulo.App()
    app.geometry("1360x900+0+0")
    base = os.path.join(pasta, "boletim.pdf")
    fotos = []

    def foto(nome):
        app.update()
        time.sleep(0.5)
        app.update()
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        try:
            ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(os.path.join(pasta, f"tela_{nome}.png"))
            fotos.append(nome)
        except Exception as e:
            _escrever(pasta, f"FOTO    {nome}: {e}")

    def roteiro():
        try:
            app.tema = "escuro"
            app.aplicar_tema()
            app.inicio()
            foto("00_salao_escuro")
            app.trocar_tema()
            foto("01_salao_claro")
            app.trocar_tema()
            for i, (cls, *_) in enumerate(modulo.FERRAMENTAS):
                app.inicio()
                app.update()
                app.abrir(cls, 100, 140)
                f = app.atual
                alvo = f.sub if isinstance(f, modulo.Par) else f
                try:
                    if isinstance(alvo, modulo.ComVisualizador):
                        alvo.arquivo.definir(base)
                    elif hasattr(alvo, "arq"):
                        alvo.arq.definir(base)
                    elif hasattr(alvo, "lista"):
                        alvo.lista.incluir([base])
                except Exception as e:
                    _escrever(pasta, f"TELA    {cls.__name__}: {e}")
                foto(f"{i + 2:02d}_{cls.__name__}")
            _escrever(pasta, f"TELAS   {len(fotos)} fotos tiradas")
        except Exception:
            _escrever(pasta, "TELAS   erro:\n" + traceback.format_exc())
        app.destroy()

    app.after(800, roteiro)
    app.mainloop()


def rodar(pasta, modulo):
    os.makedirs(pasta, exist_ok=True)
    open(os.path.join(pasta, "resultados.txt"), "w").close()
    motor = modulo.motor
    _escrever(pasta, "=== Funções ===")
    try:
        teste_motor(pasta, motor)
    except Exception:
        _escrever(pasta, traceback.format_exc())
    _escrever(pasta, "=== Telas ===")
    try:
        teste_telas(pasta, modulo)
    except Exception:
        _escrever(pasta, traceback.format_exc())
    _escrever(pasta, "FIM")
