-- Обзор выгрузки. Запуск: python sql/run.py sql/checks/01_overview.sql (или Ctrl+Shift+B на открытом файле)

-- сколько вакансий в каждом направлении и у скольких заполнены навыки
SELECT direction,
       count(*)                                   AS vacancies,
       count(*) FILTER (WHERE has_skills)         AS with_skills,
       round(median(responses_per_day) FILTER (WHERE days_open >= 7), 1) AS per_day_median_7d
FROM vacancy_directions
GROUP BY direction
ORDER BY vacancies DESC;

-- топ-15 навыков в направлении «данные»: доля от вакансий с заполненными навыками
SELECT s.skill,
       count(*)                                                       AS vacancies,
       round(count(*) * 100.0 / (SELECT count(*) FROM vacancy_directions
                                 WHERE direction = 'данные' AND has_skills), 1) AS share_pct
FROM skills s
WHERE s.direction = 'данные'
GROUP BY s.skill
ORDER BY vacancies DESC
LIMIT 15;

-- работодатели с наибольшим числом вакансий аналитиков
SELECT employer, count(*) AS vacancies, string_agg(DISTINCT directions, ' | ') AS directions
FROM vacancies
GROUP BY employer
ORDER BY vacancies DESC
LIMIT 15;

-- медианная зарплата (середина вилки, рубли) по направлению и опыту; только вакансии с зарплатой
SELECT direction, experience,
       count(salary_mid)              AS with_salary,
       round(median(salary_mid), -3)  AS salary_median
FROM vacancy_directions
GROUP BY direction, experience
HAVING count(salary_mid) >= 5
ORDER BY direction, experience;
