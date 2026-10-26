-- Зарплаты и требования по уровням: стажёр/без опыта, джун (1–3 года), мидл (3–6), сеньор (6+).
-- Уровень — по опыту из вакансии; стажёром считается и вакансия со «стаж», «intern», «практикант» в названии.
-- Зарплата — середина вилки в рублях; часть вакансий указывает «на руки», часть «до вычета» (net_share — доля «на руки»).

-- зарплаты: 25-й процентиль, медиана, 75-й процентиль
WITH v AS (
    SELECT *,
           CASE WHEN lower(name) SIMILAR TO '.*(стаж|intern|практикант).*' OR experience = 'Нет опыта' THEN '1 стажёр/без опыта'
                WHEN experience = '1–3 года' THEN '2 джун'
                WHEN experience = '3–6 лет'  THEN '3 мидл'
                ELSE '4 сеньор' END AS lvl
    FROM vacancy_directions
)
SELECT direction, lvl,
       count(*)                                      AS vacancies,
       count(salary_mid)                             AS with_salary,
       round(quantile_cont(salary_mid, 0.25), -3)    AS p25,
       round(median(salary_mid), -3)                 AS median,
       round(quantile_cont(salary_mid, 0.75), -3)    AS p75,
       round(avg(CASE gross WHEN 'на руки' THEN 1.0 WHEN 'до вычета' THEN 0 END), 2) AS net_share
FROM v
GROUP BY direction, lvl
ORDER BY direction, lvl;

-- требования: топ-9 навыков на каждом уровне, доля от вакансий с заполненными навыками
WITH v AS (
    SELECT *,
           CASE WHEN lower(name) SIMILAR TO '.*(стаж|intern|практикант).*' OR experience = 'Нет опыта' THEN '1 стажёр/без опыта'
                WHEN experience = '1–3 года' THEN '2 джун'
                WHEN experience = '3–6 лет'  THEN '3 мидл'
                ELSE '4 сеньор' END AS lvl
    FROM vacancy_directions
),
tot AS (
    SELECT direction, lvl, count(*) FILTER (WHERE has_skills) AS n FROM v GROUP BY 1, 2
),
r AS (
    SELECT v.direction, v.lvl, k.skill, count(*) AS cnt,
           row_number() OVER (PARTITION BY v.direction, v.lvl ORDER BY count(*) DESC) AS rn
    FROM v JOIN skills k ON k.id = v.id AND k.direction = v.direction
    GROUP BY 1, 2, 3
)
SELECT r.direction, r.lvl, t.n AS with_skills,
       string_agg(r.skill || ' ' || CAST(round(r.cnt * 100.0 / t.n) AS INT) || '%', ', ' ORDER BY r.rn) AS top_skills
FROM r JOIN tot t ON t.direction = r.direction AND t.lvl = r.lvl
WHERE r.rn <= 9
GROUP BY 1, 2, 3
ORDER BY 1, 2;
