"""
Compara a montagem nova com a anterior e prepara o instalador de atualização.

Uso: python ferramentas/gerar_atualizacao.py <pasta_dist> <manifesto_novo> [manifesto_anterior]
Gera o manifesto novo (lista de arquivos com impressão digital) e, se houver versão anterior,
o arquivo atualizacao_arquivos.iss com só os arquivos que mudaram.
"""
import hashlib
import json
import os
import sys


def impressao(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def main():
    dist, novo = sys.argv[1], sys.argv[2]
    anterior = sys.argv[3] if len(sys.argv) > 3 else None
    arquivos = {}
    for raiz, _, nomes in os.walk(dist):
        for n in nomes:
            c = os.path.join(raiz, n)
            arquivos[os.path.relpath(c, dist).replace("\\", "/")] = impressao(c)
    os.makedirs(os.path.dirname(os.path.abspath(novo)), exist_ok=True)
    with open(novo, "w", encoding="utf-8") as f:
        json.dump(arquivos, f, indent=0, sort_keys=True)

    if not anterior or not os.path.exists(anterior):
        print("Sem versão anterior: só o instalador completo será gerado.")
        return
    with open(anterior, encoding="utf-8") as f:
        velho = json.load(f)
    mudou = sorted(k for k, v in arquivos.items() if velho.get(k) != v)
    print(f"{len(mudou)} de {len(arquivos)} arquivos mudaram.")
    if not mudou or len(mudou) > len(arquivos) * 0.8:
        print("Atualização não compensa (nada mudou ou mudou quase tudo).")
        return
    linhas = []
    for k in mudou:
        origem = os.path.join(dist, k).replace("/", "\\")
        sub = os.path.dirname(k).replace("/", "\\")
        destino = "{app}" + ("\\" + sub if sub else "")
        linhas.append(f'Source: "{origem}"; DestDir: "{destino}"; Flags: ignoreversion')
    with open("atualizacao_arquivos.iss", "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print("atualizacao_arquivos.iss pronto.")


if __name__ == "__main__":
    main()
