-- Таблицы проекта для запросов. sql/run.py выполняет этот файл перед каждым запуском,
-- поэтому в запросах можно писать просто FROM vacancies, FROM skills, FROM vacancy_directions.
-- Базы как отдельного сервера нет: DuckDB читает CSV из data/ напрямую (пути — от корня проекта).
-- После нового сбора (python collect.py) запросы сразу видят свежие данные.

-- вакансии: одна строка = вакансия (как в data/vacancies.csv)
-- + has_skills — заполнено ли поле «Ключевые навыки»
-- + salary_mid — середина вилки, если указаны обе границы, иначе та, что есть (только рубли)
CREATE OR REPLACE VIEW vacancies AS
SELECT *,
       key_skills IS NOT NULL AND key_skills <> ''                     AS has_skills,
       CASE WHEN currency = 'RUR' THEN coalesce((salary_from + salary_to) / 2, salary_from, salary_to) END
                                                                        AS salary_mid
FROM read_csv('data/vacancies.csv', delim = ';', header = true,
              types = {'id': 'VARCHAR', 'salary_from': 'DOUBLE', 'salary_to': 'DOUBLE',
                       'created_at': 'DATE', 'published_at': 'DATE', 'days_open': 'DOUBLE',
                       'responses': 'INTEGER', 'responses_per_day': 'DOUBLE'});

-- вакансия × направление: вакансия с двумя ролями даёт две строки.
-- Для подсчётов «по направлениям» берите эту таблицу, а не vacancies.
CREATE OR REPLACE VIEW vacancy_directions AS
SELECT v.*, trim(d) AS direction
FROM vacancies v, unnest(string_split(v.directions, ',')) AS t(d);

-- пары «вакансия — навык» (как в data/skills.csv), с направлением отдельной строкой
CREATE OR REPLACE VIEW skills AS
SELECT s.id, trim(d) AS direction, s.skill
FROM read_csv('data/skills.csv', delim = ';', header = true, types = {'id': 'VARCHAR'}) s,
     unnest(string_split(s.directions, ',')) AS t(d);

-- частота навыков по направлениям, посчитанная collect.py (для сверки со своими запросами)
CREATE OR REPLACE VIEW skills_top AS
SELECT * FROM read_csv('data/skills_top.csv', delim = ';', header = true);



CREATE OR REPLACE VIEW sql1 AS
SELECT * FROM read_csv('data/vacancies.csv', delim = ';', header = true);
