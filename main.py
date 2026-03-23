import csv
import zipfile
import os
from datetime import datetime
import math

def time_weight(date_str):
    date = datetime.strptime(date_str, "%Y-%m-%d")
    days = (datetime.now() - date).days
    return math.exp(-days / 365)
def open_file(filepath: str):
    extract_path = "files"
    os.makedirs(extract_path, exist_ok=True)
    with zipfile.ZipFile(filepath, 'r') as zip_ref:
        zip_ref.extract('ratings.csv', extract_path)
    return os.path.join(extract_path, 'ratings.csv')


def read_file() -> list[tuple[str, str, float]]:
    result = []

    with open('files/ratings.csv', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            if len(row) < 5:
                continue
            result.append((
                row[0],# fecha
                row[1],# película
                float(row[4])# rating
            ))

    return result

def compute_vector(rows: list[tuple[str, str, float]]) -> list[tuple[str, float]]:
    result = []

    for date, movie, rating in rows:
        if not movie or rating is None or not date:
            continue

        rating_norm = rating / 5
        weight = rating_norm * time_weight(date)

        result.append((movie, weight))

    return result


def export_vector_to_csv(vector: list[tuple[str, float]], path: str):
    with open(path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["movie", "weight"])
        for movie, weight in vector:
            writer.writerow([movie, weight])

def format_output(vector: list[float]) -> dict:
    """Da forma a la salida final para que sea usable por el sistema recomendador."""
    pass

# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    open_file('letterboxd-withloveclau-2026-02-28-12-46-utc.zip')
    rows = read_file()
    vector = compute_vector(rows)
    export_vector_to_csv(vector,"files/vector.csv")

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
