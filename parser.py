import csv
import zipfile
import os
import math
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────

def time_weight(date_str: str) -> float:
    """Decaimiento exponencial: películas recientes pesan más."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    days = (datetime.now() - date).days
    return math.exp(-days / 365)


def normalize_title(title: str) -> str:
    """Limpia el título para usarlo como clave consistente."""
    return title.strip().lower()


# ─────────────────────────────────────────────
# Extracción de un zip individual
# ─────────────────────────────────────────────

def extract_ratings_from_zip(zip_path: str, extract_dir: str) -> list[tuple[str, str, float]]:
    """
    Extrae ratings.csv de un zip de Letterboxd.
    Devuelve lista de (fecha, título_película, rating).
    """
    user_id = Path(zip_path).stem  # nombre del zip = ID del usuario
    user_extract = os.path.join(extract_dir, user_id)
    os.makedirs(user_extract, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Letterboxd puede incluir ratings.csv en la raíz o en subcarpeta
        candidates = [f for f in zf.namelist() if f.endswith('ratings.csv')]
        if not candidates:
            print(f"  [!] {zip_path}: no contiene ratings.csv — saltando")
            return []
        zf.extract(candidates[0], user_extract)
        ratings_path = os.path.join(user_extract, candidates[0])

    rows = []
    with open(ratings_path, encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # saltar cabecera
        for row in reader:
            if len(row) < 5:
                continue
            date, title, rating_str = row[0], row[1], row[4]
            if not date or not title or not rating_str:
                continue
            try:
                rows.append((date, title, float(rating_str)))
            except ValueError:
                continue

    return rows


# ─────────────────────────────────────────────
# Cálculo del vector de usuario
# ─────────────────────────────────────────────

def compute_user_vector(rows: list[tuple[str, str, float]]) -> dict[str, float]:
    """
    Para cada película vista, calcula weight = (rating/5) * time_decay.
    Si un usuario ha visto la misma película varias veces, acumula el mayor peso.
    Devuelve dict {título_normalizado: weight}.
    """
    vector: dict[str, float] = {}
    for date, title, rating in rows:
        key = normalize_title(title)
        weight = (rating / 5.0) * time_weight(date)
        # Quedarse con el peso máximo en caso de revisits
        if key not in vector or weight > vector[key]:
            vector[key] = round(weight, 6)
    return vector


# ─────────────────────────────────────────────
# Procesado de todos los zips
# ─────────────────────────────────────────────

def process_all_zips(zips_dir: str = "zips", output_dir: str = "data") -> dict[str, dict[str, float]]:
    """
    Procesa todos los .zip de zips_dir.
    Devuelve dict {user_id: {movie_title: weight}}.
    También exporta:
      - data/interactions.csv  (user_id, movie_title, weight)
      - data/movie_titles.txt  (títulos únicos para el scraper)
    """
    os.makedirs(output_dir, exist_ok=True)
    extract_dir = os.path.join(output_dir, "_extracted")

    zip_files = sorted(Path(zips_dir).glob("*.zip"))
    if not zip_files:
        print(f"[!] No se encontraron .zip en '{zips_dir}'")
        return {}

    print(f"[·] Encontrados {len(zip_files)} zips\n")

    all_users: dict[str, dict[str, float]] = {}

    for zip_path in zip_files:
        user_id = zip_path.stem
        print(f"  → Procesando usuario: {user_id}")
        rows = extract_ratings_from_zip(str(zip_path), extract_dir)
        if not rows:
            continue
        vector = compute_user_vector(rows)
        all_users[user_id] = vector
        print(f"     {len(vector)} películas con peso calculado")

    # ── Exportar interactions.csv ──
    interactions_path = os.path.join(output_dir, "interactions.csv")
    with open(interactions_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "movie_title", "weight"])
        for user_id, vector in all_users.items():
            for title, weight in vector.items():
                writer.writerow([user_id, title, weight])

    # ── Exportar lista de títulos únicos para el scraper ──
    all_titles = set()
    for vector in all_users.values():
        all_titles.update(vector.keys())

    titles_path = os.path.join(output_dir, "movie_titles.txt")
    with open(titles_path, 'w', encoding='utf-8') as f:
        for title in sorted(all_titles):
            f.write(title + "\n")

    print(f"\n[✓] interactions.csv → {interactions_path}  ({sum(len(v) for v in all_users.values())} filas)")
    print(f"[✓] movie_titles.txt → {titles_path}  ({len(all_titles)} películas únicas)")

    return all_users


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    process_all_zips(zips_dir="zips", output_dir="data")
