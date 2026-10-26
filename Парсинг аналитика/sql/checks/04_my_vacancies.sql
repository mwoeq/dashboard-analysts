-- Подходящие мне вакансии: без опыта или 1–3 года, мои навыки закрывают от 60% ключевых навыков вакансии.
-- Список моих навыков — в my_skills ниже: добавляйте выученное (например, 'power bi') и перезапускайте.
-- Сравнение без учёта регистра и «ё».

CREATE OR REPLACE TEMP TABLE my_skills AS
SELECT lower(replace(skill, 'ё', 'е')) AS skill
FROM (VALUES
    ('SQL'), ('Python'), ('Pandas'), ('MS Excel'), ('Excel'), ('PostgreSQL'), ('ETL'),
    ('Анализ данных'), ('Аналитика'), ('Аналитическое мышление'), ('Работа с большим объемом информации'),
    ('Визуализация данных'), ('Yandex DataLens'), ('Подготовка отчетов'), ('Аналитические исследования'),
    ('Работа с базами данных'), ('Базы данных'), ('Анализ бизнес показателей'),
    ('BPMN'), ('UML'), ('Системный анализ'), ('Бизнес-анализ'), ('Сбор и анализ требований'),
    ('Анализ требований'), ('Разработка технических заданий'), ('Написание технических заданий'),
    ('Моделирование бизнес процессов'), ('Описание бизнес-процессов'), ('Бизнес-моделирование'),
    ('REST'), ('REST API'), ('Postman'), ('JSON'), ('XML'),
    ('Atlassian Jira'), ('Jira'), ('Confluence'), ('Atlassian Confluence'), ('Agile'), ('Scrum'),
    ('Документирование'), ('MS PowerPoint'), ('Деловая коммуникация')
) AS t(skill);

-- не мой уровень или не аналитика, хотя роль и опыт подходят (работодатели размечают неаккуратно)
CREATE OR REPLACE TEMP VIEW my_level AS
SELECT * FROM vacancy_directions
WHERE experience IN ('Нет опыта', '1–3 года')
  AND NOT regexp_matches(lower(name), 'senior|lead|dba|дизайнер|руководител|head');

-- 1. Подходящие вакансии с заполненными навыками: сначала с большим покрытием, затем с меньшей конкуренцией
WITH vs AS (
    SELECT v.id, v.direction, k.skill,
           lower(replace(k.skill, 'ё', 'е')) IN (SELECT skill FROM my_skills) AS have
    FROM my_level v
    JOIN skills k ON k.id = v.id AND k.direction = v.direction
),
cover AS (
    SELECT id, direction,
           count(*) FILTER (WHERE have)                                   AS matched,
           count(*)                                                       AS total,
           string_agg(skill, ', ') FILTER (WHERE NOT have)                AS missing
    FROM vs
    GROUP BY id, direction
)
SELECT v.direction, v.name, v.employer, v.experience,
       round(c.matched * 100.0 / c.total)                                 AS cover_pct,
       c.matched || ' из ' || c.total                                     AS skills_matched,
       c.missing,
       v.salary_from, v.salary_to, v.gross,
       v.work_formats, v.days_open, v.responses, v.responses_per_day,
       v.url
FROM cover c
JOIN my_level v ON v.id = c.id AND v.direction = c.direction
WHERE c.matched * 1.0 / c.total >= 0.6
ORDER BY CASE v.direction WHEN 'данные' THEN 1 WHEN 'системный' THEN 2 ELSE 3 END,
         cover_pct DESC, v.responses_per_day;

-- 2. Вакансии того же уровня без заполненных навыков: проверить вручную по названию и тексту
SELECT direction, name, employer, experience, salary_from, salary_to,
       work_formats, days_open, responses_per_day, url
FROM my_level
WHERE NOT has_skills
ORDER BY CASE direction WHEN 'данные' THEN 1 WHEN 'системный' THEN 2 ELSE 3 END,
         responses_per_day;
