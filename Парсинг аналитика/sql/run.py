"""Запуск SQL-файлов проекта в DuckDB.

Запуск: python sql/run.py sql/checks/01_overview.sql [ещё файлы...]
Перед запуском выполняется sql/views.sql, поэтому таблицы доступны по именам: FROM vacancies, FROM vacancy_directions, FROM skills.
Пути в своих read_csv — от корня проекта: read_csv('data/vacancies.csv', delim = ';').
Файл может содержать несколько запросов через «;» — выводится результат каждого.
Терминал показывает, сколько колонок влезает по ширине; полный результат каждого запроса
сохраняется в sql/out/<файл>_<номер запроса>.csv (открывается в Excel).
"""
import csv
import shutil
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sql" / "out"


def save(result, path):
    rows = result.fetchall()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(result.columns)
        writer.writerows(rows)
    return len(rows)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    connection = duckdb.connect()
    connection.execute(f"SET file_search_path = '{ROOT.as_posix()}'")
    connection.execute((ROOT / "sql" / "views.sql").read_text(encoding="utf-8"))  # vacancies, vacancy_directions, skills, …
    OUT.mkdir(exist_ok=True)
    width = shutil.get_terminal_size((200, 40)).columns
    for name in sys.argv[1:]:
        print(f"== {name}")
        number = 0
        for statement in duckdb.extract_statements(Path(name).read_text(encoding="utf-8")):
            result = connection.sql(statement.query)
            if result is None:
                continue
            number += 1
            result.show(max_rows=100, max_width=width)
            path = OUT / f"{Path(name).stem}_{number}.csv"
            count = save(result, path)
            print(f"Полностью ({count} строк, {len(result.columns)} колонок): {path.relative_to(ROOT).as_posix()}\n")


if __name__ == "__main__":
    main()
