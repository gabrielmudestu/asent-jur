import argparse
import csv
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from difflib import SequenceMatcher
from pathlib import Path


ZIP_PATH = Path(r"C:\Users\vivia\Downloads\ASENT-JUR.zip")
EXTRACT_DIR = Path("tmp/fotos_asent_jur")
STATIC_DIR = Path("app/static/imagens_empresas")
STATIC_URL_PREFIX = "/static/imagens_empresas"
MYSQL = "mysql"
DB_ARGS = [
    "-hlocalhost",
    "-P3306",
    "-uroot",
    "-pJoaolopes05",
    "--default-character-set=utf8mb4",
    "--batch",
    "--raw",
    "--skip-column-names",
    "codego_db",
]
ALIAS_MANUAIS = {
    "GRANOL AEREA 1": "GRANOL INDUSTRIA COMERCIO E EXPORTACAO S A",
}

EXT_POR_MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"RIFF": ".webp",
}


def normalizar(valor):
    texto = str(valor or "").replace("\xa0", " ").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("&", " E ")
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    texto = re.sub(r"\b(SA|S A|S/A)\b", "SA", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def slug(valor):
    texto = normalizar(valor).lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:80] or "empresa"


def executar_mysql(sql):
    proc = subprocess.run(
        [MYSQL, *DB_ARGS, "-e", sql],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


def carregar_empresas():
    saida = executar_mysql(
        "SELECT id, empresa FROM municipal_lots "
        "WHERE empresa IS NOT NULL AND empresa <> '-' AND TRIM(empresa) <> ''"
    )
    empresas = []
    for row in csv.reader(saida.splitlines(), delimiter="\t"):
        if len(row) >= 2:
            empresas.append({"id": int(row[0]), "empresa": row[1], "norm": normalizar(row[1])})
    return empresas


def detectar_ext(caminho, ext_original):
    ext = ext_original.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".jfif"}:
        return ".jpg" if ext in {".jpeg", ".jfif"} else ext
    with caminho.open("rb") as arquivo:
        inicio = arquivo.read(12)
    for magic, extensao in EXT_POR_MAGIC.items():
        if inicio.startswith(magic):
            return extensao
    return ""


def extrair_imagens():
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    imagens = []
    with zipfile.ZipFile(ZIP_PATH) as zip_file:
        for entry in zip_file.infolist():
            if entry.is_dir():
                continue
            nome = Path(entry.filename).name
            ext = Path(nome).suffix.lower()
            if ext in {".xlsx", ".xls", ".csv", ".db"}:
                continue

            destino = EXTRACT_DIR / nome
            with zip_file.open(entry) as origem, destino.open("wb") as saida:
                shutil.copyfileobj(origem, saida)

            ext_detectada = detectar_ext(destino, ext)
            if not ext_detectada:
                destino.unlink(missing_ok=True)
                continue

            imagens.append(
                {
                    "arquivo": destino,
                    "nome": Path(nome).stem.strip(),
                    "norm": normalizar(Path(nome).stem),
                    "ext": ext_detectada,
                }
            )
    return imagens


def score_nome(nome_foto, nome_empresa):
    if not nome_foto or not nome_empresa:
        return 0.0
    if nome_foto == nome_empresa:
        return 1.0

    foto_tokens = set(nome_foto.split())
    empresa_tokens = set(nome_empresa.split())
    overlap = len(foto_tokens & empresa_tokens)
    token_score = overlap / max(1, len(foto_tokens))

    menor, maior = sorted([nome_foto, nome_empresa], key=len)
    contains_bonus = 0.0
    if len(menor) >= 10 and menor in maior:
        contains_bonus = 0.2
    if overlap >= min(2, len(foto_tokens)):
        contains_bonus = max(contains_bonus, 0.15)

    ratio = SequenceMatcher(None, nome_foto, nome_empresa).ratio()
    return max(ratio, min(1.0, token_score + contains_bonus))


def montar_correspondencias(imagens, empresas):
    correspondencias = []
    sem_match = []
    revisar = []

    for imagem in imagens:
        nome_busca = ALIAS_MANUAIS.get(imagem["norm"], imagem["norm"])
        pontuados = []
        for empresa in empresas:
            score = score_nome(nome_busca, empresa["norm"])
            if score >= 0.74:
                pontuados.append((score, empresa))
        pontuados.sort(key=lambda item: item[0], reverse=True)

        if not pontuados:
            sem_match.append(imagem)
            continue

        melhor = pontuados[0][0]
        if melhor < 0.86:
            revisar.append((imagem, pontuados[:5]))
            continue

        aceitos = [empresa for score, empresa in pontuados if score >= max(0.90, melhor - 0.02)]
        if not aceitos:
            aceitos = [pontuados[0][1]]

        for empresa in aceitos:
            correspondencias.append((imagem, empresa, melhor))

    return correspondencias, sem_match, revisar


def aplicar(correspondencias):
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    valores_sql = []

    for imagem, empresa, _ in correspondencias:
        nome_destino = f"empresa{empresa['id']}_{slug(empresa['empresa'])}{imagem['ext']}"
        destino = STATIC_DIR / nome_destino
        shutil.copy2(imagem["arquivo"], destino)
        caminho = f"{STATIC_URL_PREFIX}/{nome_destino}"
        valores_sql.append(f"({empresa['id']}, NULL, '{caminho}')")

    if not valores_sql:
        return

    sql = (
        "INSERT INTO empresa_infos (empresa_id, descricao, caminho_imagem) VALUES "
        + ",".join(valores_sql)
        + " ON DUPLICATE KEY UPDATE caminho_imagem = VALUES(caminho_imagem);"
    )
    proc = subprocess.run(
        [MYSQL, *DB_ARGS],
        input=sql,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    imagens = extrair_imagens()
    empresas = carregar_empresas()
    correspondencias, sem_match, revisar = montar_correspondencias(imagens, empresas)

    print(f"imagens_validas={len(imagens)}")
    print(f"empresas_banco={len(empresas)}")
    print(f"atualizacoes_previstas={len(correspondencias)}")
    print(f"ids_unicos={len({empresa['id'] for _, empresa, _ in correspondencias})}")
    print(f"sem_correspondencia={len(sem_match)}")
    print(f"para_revisao={len(revisar)}")

    print("\nAMOSTRA_CORRESPONDENCIAS")
    for imagem, empresa, score in correspondencias[:40]:
        print(f"{empresa['id']}\t{score:.2f}\t{imagem['nome']}\t=>\t{empresa['empresa']}")

    if sem_match:
        print("\nSEM_CORRESPONDENCIA")
        for imagem in sem_match:
            print(imagem["nome"])

    if revisar:
        print("\nPARA_REVISAO")
        for imagem, opcoes in revisar:
            sugestoes = " | ".join(f"{score:.2f}:{empresa['id']}:{empresa['empresa']}" for score, empresa in opcoes)
            print(f"{imagem['nome']} => {sugestoes}")

    if args.apply:
        aplicar(correspondencias)
        print("\nAPLICADO")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
