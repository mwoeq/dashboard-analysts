"""Сбор вакансий аналитиков с веб-страниц hh.ru: системные, данные, продукт.

Запуск: python collect.py
Шаг 1 — страницы поиска по профессиональным ролям (список вакансий).
Шаг 2 — страница каждой вакансии (ключевые навыки есть только там). Разобранные карточки
кэшируются в data/cache/, поэтому прерванный запуск продолжается с места остановки.
Результат в data/:
  vacancies.csv  — вакансия, ссылка, работодатель, зарплата, опыт, формат, дата создания,
                   отклики и отклики в день, ключевые навыки
  skills.csv     — одна строка на пару «вакансия — навык» (для подсчётов и сводных в Excel)
  skills_top.csv — частота навыков по направлениям: сколько вакансий требует навык и какая это доля
"""
import csv
import html
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
SEARCH_URL = "https://hh.ru/search/vacancy"
VACANCY_URL = "https://hh.ru/vacancy/{}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
STATE_RE = re.compile(r'<template[^>]*id="HH-Lux-InitialState"[^>]*>(.*?)</template>', re.S)

AREA = 1  # 1 — Москва, 2 — Санкт-Петербург, 113 — вся Россия
PERIOD_DAYS = 30  # вакансии, опубликованные за последние N дней (hh принимает 1, 3, 7, 30)
# направления — профессиональные роли hh
DIRECTIONS = {
    "системный": 148,  # Системный аналитик
    "данные": 156,     # BI-аналитик, аналитик данных
    "продукт": 164,    # Продуктовый аналитик
}
PER_PAGE = 50
MAX_PAGES = 40  # больше 2000 вакансий на один поиск hh не показывает
PAUSE = (1.5, 3.0)  # случайная пауза между запросами, секунд

EXPERIENCE = {"noExperience": "Нет опыта", "between1And3": "1–3 года",
              "between3And6": "3–6 лет", "moreThan6": "Более 6 лет"}
WORK_FORMATS = {"ON_SITE": "офис", "REMOTE": "удалённо", "HYBRID": "гибрид", "FIELD_WORK": "разъездной"}
VACANCY_COLUMNS = ["id", "directions", "name", "employer", "area", "experience", "work_formats",
                   "salary_from", "salary_to", "currency", "gross", "created_at", "published_at", "days_open",
                   "responses", "responses_per_day", "url", "key_skills"]


class Blocked(Exception):
    """hh показал капчу или страницу без данных — сбор останавливаем, а не обходим."""


def fetch_state(session, url, params=None):
    time.sleep(random.uniform(*PAUSE))
    response = session.get(url, params=params, timeout=30)
    if response.status_code in (403, 429):
        raise Blocked(f"hh ответил {response.status_code} на {response.url}")
    response.raise_for_status()
    match = STATE_RE.search(response.text)
    if not match:
        raise Blocked(f"на странице нет данных (вероятно, капча): {response.url}")
    return json.loads(html.unescape(match.group(1)))


def search_fields(vacancy, now):
    """Поля из выдачи поиска: дата создания и отклики. Отклики меняются, поэтому не кэшируются."""
    created = vacancy.get("creationTime")
    responses = vacancy.get("totalResponsesCount")
    days = (now - datetime.fromisoformat(created)).total_seconds() / 86400 if created else None
    per_day = round(responses / max(days, 1), 2) if responses is not None and days is not None else ""
    return {"created_at": (created or "")[:10], "days_open": round(days, 1) if days is not None else "",
            "responses": responses if responses is not None else "", "responses_per_day": per_day}


def search(session, role, now):
    """Вакансии одной роли со всех страниц выдачи: id → поля из выдачи."""
    found, page = {}, 0
    while page < MAX_PAGES:
        result = fetch_state(session, SEARCH_URL, {
            "professional_role": role, "area": AREA, "search_period": PERIOD_DAYS,
            "items_on_page": PER_PAGE, "page": page})["vacancySearchResult"]
        vacancies = result.get("vacancies") or []
        for vacancy in vacancies:
            found[str(vacancy["vacancyId"])] = search_fields(vacancy, now)
        total = result.get("totalResults") or 0
        page += 1
        if not vacancies or page * PER_PAGE >= total:
            break
    if total > MAX_PAGES * PER_PAGE:
        print(f"  найдено {total}, hh показывает только {MAX_PAGES * PER_PAGE}: сузьте AREA или PERIOD_DAYS")
    return found


def parse_vacancy(vacancy):
    """Нужные поля из JSON страницы вакансии."""
    compensation = vacancy.get("compensation") or {}
    return {
        "name": vacancy.get("name", ""),
        "employer": (vacancy.get("company") or {}).get("name", ""),
        "area": (vacancy.get("area") or {}).get("name", ""),
        "experience": EXPERIENCE.get(vacancy.get("workExperience"), vacancy.get("workExperience") or ""),
        "work_formats": ", ".join(WORK_FORMATS.get(f, f) for f in vacancy.get("workFormats") or []),
        "salary_from": compensation.get("from") or "",
        "salary_to": compensation.get("to") or "",
        "currency": compensation.get("currencyCode") or "",
        "gross": {True: "до вычета", False: "на руки"}.get(compensation.get("gross"), ""),
        "published_at": (vacancy.get("publicationTimeIso") or "")[:10],
        "key_skills": [str(skill) for skill in vacancy.get("keySkills") or []],
    }


def load_card(session, vacancy_id):
    """Карточка вакансии из кэша или со страницы hh."""
    path = CACHE / f"{vacancy_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    state = fetch_state(session, VACANCY_URL.format(vacancy_id))
    card = parse_vacancy(state["vacancyView"]["vacancyFull"]["vacancy"])
    path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return card


def vacancy_row(vacancy_id, directions, card, listed):
    return {**card, **listed, "id": vacancy_id, "directions": ", ".join(sorted(directions)),
            "url": VACANCY_URL.format(vacancy_id), "key_skills": "; ".join(card["key_skills"])}


def skills_top(rows):
    """Частота навыков по направлениям; вакансия из двух направлений считается в обоих."""
    counts, totals, with_skills = defaultdict(Counter), Counter(), Counter()
    for row in rows:
        skills = {skill.strip() for skill in row["key_skills"].split(";") if skill.strip()}
        for direction in row["directions"].split(", "):
            totals[direction] += 1
            with_skills[direction] += bool(skills)
            counts[direction].update(skills)
    top = []
    for direction, counter in counts.items():
        for skill, n in counter.most_common():
            # share — от всех вакансий направления; share_with_skills — только от тех, где навыки заполнены
            top.append({"direction": direction, "skill": skill, "vacancies": n,
                        "share": round(n / totals[direction] * 100, 1),
                        "share_with_skills": round(n / with_skills[direction] * 100, 1)})
    return top


def write_csv(path, rows, columns):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, columns, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # иначе кириллица ломается при перенаправлении вывода
    CACHE.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    now = datetime.now().astimezone()
    found = defaultdict(set)  # id вакансии → направления
    listed = {}  # id вакансии → поля из выдачи (дата создания, отклики)
    rows = []
    try:
        for direction, role in DIRECTIONS.items():
            vacancies = search(session, role, now)
            print(f"{direction}: {len(vacancies)} вакансий")
            listed.update(vacancies)
            for vacancy_id in vacancies:
                found[vacancy_id].add(direction)
        cached = sum(1 for vacancy_id in found if (CACHE / f"{vacancy_id}.json").exists())
        print(f"Всего уникальных: {len(found)}, уже в кэше: {cached}. Загружаю остальные карточки…")
        for number, (vacancy_id, directions) in enumerate(found.items(), 1):
            rows.append(vacancy_row(vacancy_id, directions, load_card(session, vacancy_id), listed[vacancy_id]))
            if number % 50 == 0:
                print(f"  карточек: {number} из {len(found)}")
    except Blocked as error:
        print(f"Остановлено: {error}")
        print("Загруженное сохранено в кэше. Подождите час-другой или откройте hh в браузере, затем запустите снова.")
        if not rows:
            sys.exit(1)
        print(f"Записываю то, что успели собрать: {len(rows)} вакансий.")

    write_csv(DATA / "vacancies.csv", rows, VACANCY_COLUMNS)
    pairs = [{"id": row["id"], "directions": row["directions"], "skill": skill.strip()}
             for row in rows for skill in row["key_skills"].split(";") if skill.strip()]
    write_csv(DATA / "skills.csv", pairs, ["id", "directions", "skill"])
    write_csv(DATA / "skills_top.csv", skills_top(rows), ["direction", "skill", "vacancies", "share", "share_with_skills"])
    without = sum(1 for row in rows if not row["key_skills"])
    print(f"Готово: {len(rows)} вакансий, без ключевых навыков {without}. Файлы в {DATA}")


if __name__ == "__main__":
    main()
