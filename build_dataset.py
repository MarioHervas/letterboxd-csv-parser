"""
build_dataset.py
────────────────
Une interactions.csv y movies.csv para generar el dataset
final que consumirá el Two-Tower model en PyTorch.

Salidas:
  data/dataset.csv          → (user_id, movie_title, weight) solo con películas que tienen metadata
  data/user_index.json      → {user_id: int_index}
  data/movie_index.json     → {movie_title: int_index}
  data/movie_features.json  → {movie_title: {nanogenres:[...], themes:[...], year:..., ...}}
  data/stats.txt            → resumen del dataset

Uso:
    python build_dataset.py
"""

import csv
import json
import os
from collections import defaultdict


# ─────────────────────────────────────────────
# Carga de datos
# ─────────────────────────────────────────────

def load_interactions(path: str = "data/interactions.csv") -> list[dict]:
    interactions = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            interactions.append({
                "user_id": row["user_id"],
                "movie_title": row["movie_title"],
                "weight": float(row["weight"]),
            })
    return interactions


def load_movies(path: str = "data/movies.csv") -> dict[str, dict]:
    """Devuelve {title_normalized: metadata_dict}"""
    movies = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row["title_normalized"]
            movies[title] = {
                "title_original": row.get("title_original", title),
                "tmdb_id": row.get("tmdb_id", ""),
                "year": row.get("year", ""),
                "director": row.get("director", ""),
                "tmdb_genres": [g for g in row.get("tmdb_genres", "").split("|") if g],
                "tmdb_keywords": [k for k in row.get("tmdb_keywords", "").split("|") if k],
                "nanogenres": [n for n in row.get("nanogenres", "").split("|") if n],
                "themes": [t for t in row.get("themes", "").split("|") if t],
                "overview": row.get("overview", ""),
                "popularity": row.get("popularity", ""),
                "vote_average": row.get("vote_average", ""),
            }
    return movies


# ─────────────────────────────────────────────
# Construcción de vocabularios
# ─────────────────────────────────────────────

def build_vocabularies(movies: dict[str, dict]) -> tuple[dict, dict, dict]:
    """
    Construye vocabularios para nanogéneros, temáticas y géneros TMDB.
    Devuelve (nanogenre_vocab, theme_vocab, genre_vocab) → {label: int_index}
    """
    nanogenre_vocab: dict[str, int] = {}
    theme_vocab: dict[str, int] = {}
    genre_vocab: dict[str, int] = {}

    for meta in movies.values():
        for ng in meta["nanogenres"]:
            if ng not in nanogenre_vocab:
                nanogenre_vocab[ng] = len(nanogenre_vocab)
        for th in meta["themes"]:
            if th not in theme_vocab:
                theme_vocab[th] = len(theme_vocab)
        for g in meta["tmdb_genres"]:
            if g not in genre_vocab:
                genre_vocab[g] = len(genre_vocab)

    return nanogenre_vocab, theme_vocab, genre_vocab


# ─────────────────────────────────────────────
# Filtrado y limpieza
# ─────────────────────────────────────────────

def filter_interactions(
    interactions: list[dict],
    movies: dict[str, dict],
    min_weight: float = 0.01,
) -> list[dict]:
    """
    Elimina interacciones:
      - Sin metadata de película (no se encontró en TMDB/LB)
      - Con peso demasiado bajo (películas casi ignoradas)
    """
    filtered = []
    skipped_no_meta = 0
    skipped_low_weight = 0

    for row in interactions:
        if row["movie_title"] not in movies:
            skipped_no_meta += 1
            continue
        if row["weight"] < min_weight:
            skipped_low_weight += 1
            continue
        filtered.append(row)

    print(f"  Filtradas por falta de metadata: {skipped_no_meta}")
    print(f"  Filtradas por peso bajo (<{min_weight}): {skipped_low_weight}")
    print(f"  Interacciones válidas: {len(filtered)}")
    return filtered


# ─────────────────────────────────────────────
# Construcción del dataset final
# ─────────────────────────────────────────────

def build_dataset(output_dir: str = "data") -> None:
    print("[·] Cargando datos...")
    interactions = load_interactions(os.path.join(output_dir, "interactions.csv"))
    movies = load_movies(os.path.join(output_dir, "movies.csv"))

    print(f"  {len(interactions)} interacciones crudas")
    print(f"  {len(movies)} películas con metadata\n")

    print("[·] Filtrando...")
    clean = filter_interactions(interactions, movies)

    # ── Índices enteros para usuarios y películas ──
    users_seen = sorted(set(r["user_id"] for r in clean))
    movies_seen = sorted(set(r["movie_title"] for r in clean))

    user_index = {u: i for i, u in enumerate(users_seen)}
    movie_index = {m: i for i, m in enumerate(movies_seen)}

    # ── Vocabularios de features ──
    nanogenre_vocab, theme_vocab, genre_vocab = build_vocabularies(
        {m: movies[m] for m in movies_seen}
    )

    print(f"\n[·] Vocabularios:")
    print(f"  Nanogéneros únicos: {len(nanogenre_vocab)}")
    print(f"  Temáticas únicas:   {len(theme_vocab)}")
    print(f"  Géneros TMDB:       {len(genre_vocab)}")

    # ── dataset.csv ──
    dataset_path = os.path.join(output_dir, "dataset.csv")
    with open(dataset_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_idx", "movie_idx", "weight", "user_id", "movie_title"])
        for row in clean:
            writer.writerow([
                user_index[row["user_id"]],
                movie_index[row["movie_title"]],
                row["weight"],
                row["user_id"],
                row["movie_title"],
            ])

    # ── Índices JSON ──
    with open(os.path.join(output_dir, "user_index.json"), "w", encoding="utf-8") as f:
        json.dump(user_index, f, ensure_ascii=False, indent=2)

    with open(os.path.join(output_dir, "movie_index.json"), "w", encoding="utf-8") as f:
        json.dump(movie_index, f, ensure_ascii=False, indent=2)

    # ── Features de películas ──
    movie_features = {}
    for title in movies_seen:
        meta = movies[title]
        movie_features[title] = {
            "idx": movie_index[title],
            "title_original": meta["title_original"],
            "year": meta["year"],
            "director": meta["director"],
            "nanogenres": meta["nanogenres"],
            "nanogenre_ids": [nanogenre_vocab[ng] for ng in meta["nanogenres"] if ng in nanogenre_vocab],
            "themes": meta["themes"],
            "theme_ids": [theme_vocab[t] for t in meta["themes"] if t in theme_vocab],
            "tmdb_genres": meta["tmdb_genres"],
            "genre_ids": [genre_vocab[g] for g in meta["tmdb_genres"] if g in genre_vocab],
            "vote_average": meta["vote_average"],
            "popularity": meta["popularity"],
        }

    with open(os.path.join(output_dir, "movie_features.json"), "w", encoding="utf-8") as f:
        json.dump(movie_features, f, ensure_ascii=False, indent=2)

    # ── Vocabularios ──
    vocabs = {
        "nanogenre_vocab": nanogenre_vocab,
        "theme_vocab": theme_vocab,
        "genre_vocab": genre_vocab,
        "nanogenre_size": len(nanogenre_vocab),
        "theme_size": len(theme_vocab),
        "genre_size": len(genre_vocab),
    }
    with open(os.path.join(output_dir, "vocabs.json"), "w", encoding="utf-8") as f:
        json.dump(vocabs, f, ensure_ascii=False, indent=2)

    # ── Estadísticas ──
    user_movie_counts = defaultdict(int)
    for row in clean:
        user_movie_counts[row["user_id"]] += 1

    stats = [
        f"Usuarios: {len(user_index)}",
        f"Películas únicas (con metadata): {len(movie_index)}",
        f"Interacciones totales: {len(clean)}",
        f"Media películas por usuario: {len(clean)/max(len(user_index),1):.1f}",
        f"Min películas por usuario: {min(user_movie_counts.values())}",
        f"Max películas por usuario: {max(user_movie_counts.values())}",
        f"Nanogéneros únicos: {len(nanogenre_vocab)}",
        f"Temáticas únicas: {len(theme_vocab)}",
        f"Géneros TMDB únicos: {len(genre_vocab)}",
    ]

    stats_path = os.path.join(output_dir, "stats.txt")
    with open(stats_path, "w", encoding="utf-8") as f:
        f.write("\n".join(stats))

    print("\n[✓] Dataset generado:")
    for s in stats:
        print(f"   {s}")
    print(f"\n   Archivos en '{output_dir}':")
    for fname in ["dataset.csv", "user_index.json", "movie_index.json", "movie_features.json", "vocabs.json", "stats.txt"]:
        print(f"   · {fname}")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    build_dataset(output_dir="data")
