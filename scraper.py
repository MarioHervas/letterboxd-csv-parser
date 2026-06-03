"""
scraper.py
──────────
Para cada película en data/movie_titles.txt:
  1. Busca en TMDB → obtiene id, año, géneros, overview, popularidad, director
  2. Scrape Letterboxd → obtiene nanogéneros y temáticas (themes)
  3. Guarda todo en data/movies.csv

Requisitos:
    pip install requests beautifulsoup4 tqdm

Uso:
    python scraper.py
"""

import csv
import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ─────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────

TMDB_API_KEY = "ca3d956ac8ac822dc1123ce3a585129e"
TMDB_BASE = "https://api.themoviedb.org/3"
LB_BASE = "https://letterboxd.com/film"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

LB_DELAY = 1.5
TMDB_DELAY = 0.25


# ─────────────────────────────────────────────
# TMDB helpers
# ─────────────────────────────────────────────

def fetch_tmdb_genre_map() -> dict[int, str]:
    """Llama una vez al inicio y devuelve {genre_id: genre_name}."""
    url = f"{TMDB_BASE}/genre/movie/list"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    genres = r.json().get("genres", [])
    return {g["id"]: g["name"] for g in genres}


def tmdb_search(title: str) -> dict | None:
    url = f"{TMDB_BASE}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": title, "language": "en-US"}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"  [TMDB] Error buscando '{title}': {e}")
        return None


def tmdb_credits(tmdb_id: int) -> str:
    url = f"{TMDB_BASE}/movie/{tmdb_id}/credits"
    params = {"api_key": TMDB_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        crew = r.json().get("crew", [])
        directors = [p["name"] for p in crew if p.get("job") == "Director"]
        return ", ".join(directors)
    except Exception:
        return ""


def tmdb_keywords(tmdb_id: int) -> list[str]:
    url = f"{TMDB_BASE}/movie/{tmdb_id}/keywords"
    params = {"api_key": TMDB_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return [k["name"] for k in r.json().get("keywords", [])]
    except Exception:
        return []


# ─────────────────────────────────────────────
# Letterboxd helpers
# ─────────────────────────────────────────────

def title_to_lb_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[''']", "", slug)
    slug = re.sub(r"[^a-z0-9\s-]", " ", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def lb_scrape(title: str) -> dict:
    slug = title_to_lb_slug(title)
    url = f"{LB_BASE}/{slug}/"
    result = {"nanogenres": [], "themes": [], "lb_url": url}

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            return result
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        nanogenres = []
        for section in soup.find_all("section", {"data-id": "nanogenres"}):
            for a in section.find_all("a"):
                text = a.get_text(strip=True)
                if text:
                    nanogenres.append(text)

        if not nanogenres:
            genre_section = soup.find("div", class_=re.compile(r"nano-genre|genre", re.I))
            if genre_section:
                for a in genre_section.find_all("a"):
                    text = a.get_text(strip=True)
                    if text:
                        nanogenres.append(text)

        result["nanogenres"] = nanogenres

        themes = []
        for section in soup.find_all("section", {"data-id": "themes"}):
            for a in section.find_all("a"):
                text = a.get_text(strip=True)
                if text:
                    themes.append(text)

        result["themes"] = themes

    except Exception as e:
        print(f"  [LB] Error scrapeando '{title}' ({url}): {e}")

    time.sleep(LB_DELAY)
    return result


# ─────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────

def enrich_movies(
    titles_path: str = "data/movie_titles.txt",
    output_path: str = "data/movies.csv",
    checkpoint_path: str = "data/movies_checkpoint.json",
) -> None:

    with open(titles_path, encoding="utf-8") as f:
        titles = [line.strip() for line in f if line.strip()]

    print(f"[·] {len(titles)} películas a enriquecer\n")

    # ── Cargar mapa de géneros TMDB UNA SOLA VEZ al inicio ──
    print("[·] Cargando mapa de géneros TMDB...")
    genre_map = fetch_tmdb_genre_map()
    print(f"    {len(genre_map)} géneros cargados\n")

    # Cargar checkpoint si existe (permite reanudar si se interrumpe)
    checkpoint: dict[str, dict] = {}
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding="utf-8") as f:
            checkpoint = json.load(f)
        print(f"[·] Checkpoint cargado: {len(checkpoint)} películas ya procesadas\n")

    results: dict[str, dict] = dict(checkpoint)

    fieldnames = [
        "title_normalized",
        "title_original",
        "tmdb_id",
        "year",
        "director",
        "tmdb_genres",
        "tmdb_keywords",
        "nanogenres",
        "themes",
        "overview",
        "popularity",
        "vote_average",
        "lb_url",
    ]

    pending = [t for t in titles if t not in results]
    print(f"[·] Pendientes: {len(pending)} películas\n")

    for title in tqdm(pending, desc="Enriqueciendo películas"):
        row: dict = {"title_normalized": title}

        # ── TMDB ──
        tmdb_result = tmdb_search(title)
        time.sleep(TMDB_DELAY)

        if tmdb_result:
            tmdb_id = tmdb_result["id"]
            director = tmdb_credits(tmdb_id)
            time.sleep(TMDB_DELAY)
            keywords = tmdb_keywords(tmdb_id)
            time.sleep(TMDB_DELAY)

            release_year = ""
            if tmdb_result.get("release_date"):
                release_year = tmdb_result["release_date"][:4]

            # genre_ids son ints → convertir a nombres con el mapa
            genre_names = [
                genre_map[gid]
                for gid in tmdb_result.get("genre_ids", [])
                if gid in genre_map
            ]

            row.update({
                "title_original": tmdb_result.get("title", title),
                "tmdb_id": tmdb_id,
                "year": release_year,
                "director": director,
                "tmdb_genres": "|".join(genre_names),
                "tmdb_keywords": "|".join(keywords[:20]),
                "overview": tmdb_result.get("overview", "")[:300],
                "popularity": tmdb_result.get("popularity", ""),
                "vote_average": tmdb_result.get("vote_average", ""),
            })
        else:
            row.update({
                "title_original": title,
                "tmdb_id": "",
                "year": "",
                "director": "",
                "tmdb_genres": "",
                "tmdb_keywords": "",
                "overview": "",
                "popularity": "",
                "vote_average": "",
            })

        # ── Letterboxd ──
        lb_data = lb_scrape(title)
        row.update({
            "nanogenres": "|".join(lb_data["nanogenres"]),
            "themes": "|".join(lb_data["themes"]),
            "lb_url": lb_data["lb_url"],
        })

        results[title] = row

        # Checkpoint cada 20 películas por si se interrumpe
        if len(results) % 20 == 0:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    # Checkpoint final
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Escribir CSV final
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in results.values():
            writer.writerow(row)

    print(f"\n[✓] movies.csv guardado en {output_path}")
    print(f"    {len(results)} películas totales")
    print(f"    {sum(1 for r in results.values() if r.get('nanogenres'))} con nanogéneros de Letterboxd")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    enrich_movies(
        titles_path="data/movie_titles.txt",
        output_path="data/movies.csv",
    )
