import csv
import zipfile
import os
def open_file(filepath: str):
    extract_path = "files"
    os.makedirs(extract_path, exist_ok=True)
    with zipfile.ZipFile(filepath, 'r') as zip_ref:
        zip_ref.extract('ratings.csv', extract_path)
    return os.path.join(extract_path, 'ratings.csv')


def read_file() -> list[dict]:
        with open('files/ratings.csv', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                print(row)
            return list(reader)

def compute_vector(rows: list[dict]) -> list[float]:
    """Calcula el vector del usuario basado en puntuación y factor temporal."""
    pass

def format_output(vector: list[float]) -> dict:
    """Da forma a la salida final para que sea usable por el sistema recomendador."""
    pass
def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')
    open_file('letterboxd-withloveclau-2026-02-28-12-46-utc.zip')
    read_file()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
