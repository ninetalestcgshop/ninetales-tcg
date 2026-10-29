#!/usr/bin/env python3
"""Baixa as cartas de TODOS os ilustradores do cartasdepokemon.com.br e gera
cards.json (lido pelo app). Só ACRESCENTA cartas novas; nunca apaga as que já existem.

Uso:
  pip install requests beautifulsoup4
  python baixar_cartas.py --teste        # só 1 artista, para conferir
  python baixar_cartas.py                # todos (leva ~20-40 min, pode parar e continuar)
"""
import re, sys, time, os, json, argparse, datetime
import requests
from bs4 import BeautifulSoup

BASE = "https://www.cartasdepokemon.com.br"
OUT = "cards.json"
ALT = re.compile(r"\s*[—-]\s*carta Pokémon TCG$")
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (checklist pessoal Ninetales TCG)"
DELAY = 1.0  # segundos entre pedidos; não diminua, seja gentil com o site

def get(url, params=None):
    for i in range(4):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 200:
                time.sleep(DELAY)
                return BeautifulSoup(r.text, "html.parser")
            if r.status_code == 404:
                return None
            print(f"  status {r.status_code}, aguardando...")
            time.sleep(10 * (i + 1))
        except requests.RequestException as e:
            print("  erro de rede:", e)
            time.sleep(5 * (i + 1))
    return None

def artist_slugs():
    slugs, page, total = [], 1, 0
    while True:
        soup = get(BASE + "/ilustradores", {"page": page})
        if not soup:
            break
        new = []
        for a in soup.select('a[href*="/ilustradores/"]'):
            m = re.search(r"/ilustradores/([^/?#]+)$", a["href"].split("?")[0])
            if m and m.group(1) not in slugs and m.group(1) not in new:
                new.append(m.group(1))
        if page == 1:
            m = re.search(r"(\d+)\s+artistas catalogados", soup.get_text())
            total = int(m.group(1)) if m else 0
        if not new:
            break
        slugs += new
        page += 1
    if total and len(slugs) < total * 0.9:
        print(f"ATENÇÃO: achei {len(slugs)} de {total} artistas. A paginação pode não estar funcionando; me avise.")
    return slugs

def clean(s):
    return re.sub(r"\s+", " ", s.replace(";", ",")).strip()

def parse_cards(soup, artist):
    rows = []
    for img in soup.find_all("img", alt=ALT):
        name = clean(ALT.sub("", img["alt"]))
        box = img
        for _ in range(6):  # sobe até o bloco que contém "Ilustração:"
            if box.parent is None or "Ilustração" in box.get_text():
                break
            box = box.parent
        texts = [t.strip() for t in box.stripped_strings if t.strip()]
        num = next((m.group(1) for t in texts if (m := re.match(r"#\s*([A-Za-z0-9]+(?:/[A-Za-z0-9]+)?)", t))), "")
        colecao = ""
        if name in texts:
            i = texts.index(name)
            if i + 1 < len(texts):
                colecao = texts[i + 1]
        src = img.get("src") or img.get("data-src") or ""
        if src.startswith("/"):
            src = BASE + src
        if src.startswith("data:"):
            src = ""
        rows.append("; ".join([clean(artist), name, num, clean(colecao), src]))
    return rows

def artist_cards(slug):
    out, seen, page = [], set(), 1
    artist = slug
    while True:
        soup = get(f"{BASE}/ilustradores/{slug}", {"page": page})
        if not soup:
            break
        if page == 1 and soup.title and soup.title.string:
            artist = soup.title.string.split("–")[0].split(" - ")[0].strip() or slug
        rows = parse_cards(soup, artist)
        fresh = [r for r in rows if r not in seen]
        if not fresh:
            break
        seen.update(fresh)
        out += fresh
        page += 1
    return out

def ckey(c):
    return "|".join([c["artist"], c["set"], c["number"], c["name"]])

def to_card(row):
    p = [x.strip() for x in row.split(";", 4)]
    p += [""] * (5 - len(p))
    return {"artist": p[0], "name": p[1], "number": p[2], "set": p[3], "img": p[4]}

def load():
    if not os.path.exists(OUT):
        return []
    try:
        return json.load(open(OUT, encoding="utf-8")).get("cards", [])
    except Exception:
        return []

def save(cards):
    data = {"updated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "total": len(cards), "cards": cards}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teste", action="store_true")
    ap.add_argument("--limite", type=int, default=0, help="só os N primeiros artistas")
    a = ap.parse_args()
    if a.teste:
        for r in artist_cards("shinji-kanda")[:8]:
            print(r)
        print("Se as linhas acima estão certas, rode sem --teste.")
        return
    cards = load()
    seen = {ckey(c) for c in cards}
    slugs = artist_slugs()
    if not slugs:
        sys.exit("Nenhum artista encontrado; o site pode ter mudado. Nada foi alterado.")
    if a.limite:
        slugs = slugs[:a.limite]
    print(len(slugs), "artistas;", len(cards), "cartas já salvas")
    novos = 0
    for i, slug in enumerate(slugs, 1):
        added = 0
        for r in artist_cards(slug):
            c = to_card(r)
            if c["name"] and ckey(c) not in seen:
                seen.add(ckey(c)); cards.append(c); added += 1
        novos += added
        print(f"[{i}/{len(slugs)}] {slug}: +{added}")
        if novos and i % 25 == 0:
            save(cards)  # progresso seguro: pode parar e rodar de novo
    if novos or not os.path.exists(OUT):
        save(cards)
    print(f"Pronto: {novos} cartas novas, {len(cards)} no total em {OUT}")

if __name__ == "__main__":
    main()
