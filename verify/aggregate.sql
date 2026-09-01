-- Recompute the two summary tables in the README from the rows they were
-- summarised from, in SQLite.
--
-- The split table in the README (mean input cells, distinct colours, demo pairs)
-- is reports/split_stats.csv, which scripts/split_stats.py produced by averaging
-- reports/task_stats.csv in the same pass that wrote it. One pass means one
-- opinion. This averages the 1,120 task rows again with GROUP BY and requires
-- the answer to match to 1e-9.
--
-- The primitive family table in the README is a grouping of the 21 distinct
-- programs in reports/eval_training.json. That grouping exists only in the
-- README prose, so this rebuilds it from by_program with json_each and prints
-- the counts, and checks the families still partition the 39 solves.
--
-- Every line of output starts with ok or FAIL. verify.sh fails the run on any
-- FAIL and on a short count of oks.

.mode csv
.import --csv reports/task_stats.csv task_stats
.import --csv reports/split_stats.csv split_stats

.mode list
.headers off

CREATE TEMP TABLE recomputed AS
SELECT split,
       COUNT(*)                              AS n_tasks,
       AVG(CAST(input_cells AS REAL))        AS mean_input_cells,
       AVG(CAST(distinct_colours AS REAL))   AS mean_distinct_colours,
       AVG(CAST(demo_pairs AS REAL))         AS mean_demo_pairs
FROM task_stats
GROUP BY split;

-- Row count first: an average over the wrong number of rows is still a number.
SELECT CASE WHEN (SELECT COUNT(*) FROM task_stats) = 1120
            THEN 'ok    task_stats.csv has 1120 task rows'
            ELSE 'FAIL  task_stats.csv has ' || (SELECT COUNT(*) FROM task_stats) || ' rows, expected 1120'
       END;

SELECT CASE WHEN COUNT(*) = 0 THEN 'ok    no task id appears twice'
            ELSE 'FAIL  ' || COUNT(*) || ' duplicated task ids' END
FROM (SELECT task_id FROM task_stats GROUP BY task_id HAVING COUNT(*) > 1);

SELECT CASE
    WHEN r.n_tasks = CAST(p.n_tasks AS INTEGER)
     AND ABS(r.mean_input_cells      - CAST(p.mean_input_cells AS REAL))      < 1e-9
     AND ABS(r.mean_distinct_colours - CAST(p.mean_distinct_colours AS REAL)) < 1e-9
     AND ABS(r.mean_demo_pairs       - CAST(p.mean_demo_pairs AS REAL))       < 1e-9
    THEN 'ok    ' || r.split || ': ' || r.n_tasks || ' tasks, cells ' ||
         PRINTF('%.4f', r.mean_input_cells) || ', colours ' ||
         PRINTF('%.4f', r.mean_distinct_colours) || ', demos ' ||
         PRINTF('%.4f', r.mean_demo_pairs) || ' all within 1e-9 of the published row'
    ELSE 'FAIL  ' || r.split || ': recomputed ' || r.n_tasks || '/' ||
         PRINTF('%.6f', r.mean_input_cells) || '/' ||
         PRINTF('%.6f', r.mean_distinct_colours) || '/' ||
         PRINTF('%.6f', r.mean_demo_pairs) || ' against published ' ||
         p.n_tasks || '/' || p.mean_input_cells || '/' ||
         p.mean_distinct_colours || '/' || p.mean_demo_pairs
    END
FROM recomputed r JOIN split_stats p USING (split)
ORDER BY r.split DESC;

-- The README says evaluation inputs are 2.05x the size of training inputs.
SELECT CASE WHEN ROUND(e.mean_input_cells / t.mean_input_cells, 2) = 2.05
            THEN 'ok    evaluation inputs are ' ||
                 PRINTF('%.4f', e.mean_input_cells / t.mean_input_cells) ||
                 'x training, rounds to the published 2.05'
            ELSE 'FAIL  ratio is ' || PRINTF('%.4f', e.mean_input_cells / t.mean_input_cells)
       END
FROM recomputed t, recomputed e
WHERE t.split = 'training' AND e.split = 'evaluation';

-- The primitive families, rebuilt from the program names.
CREATE TEMP TABLE programs AS
SELECT key AS program, CAST(value AS INTEGER) AS tasks
FROM json_each((SELECT json_extract(readfile('reports/eval_training.json'), '$.by_program')));

CREATE TEMP TABLE families AS
SELECT CASE
         WHEN program LIKE '%fit:tile%'     THEN 'tiling'
         WHEN program LIKE '%fit:colormap%' THEN 'colour map'
         WHEN program LIKE '%fit:scale%'    THEN 'integer upscale'
         WHEN program LIKE '%_object%'      THEN 'object selection'
         WHEN program LIKE '%crop%'         THEN 'crop to content'
         ELSE 'geometric only'
       END AS family,
       SUM(tasks) AS tasks
FROM programs GROUP BY family;

SELECT 'ok    family ' || PRINTF('%-17s', family) || ' ' || tasks || ' tasks'
FROM families ORDER BY tasks DESC, family;

SELECT CASE WHEN (SELECT SUM(tasks) FROM families) =
                 (SELECT json_extract(readfile('reports/eval_training.json'), '$.solved'))
            THEN 'ok    the families partition all ' || (SELECT SUM(tasks) FROM families) ||
                 ' solved training tasks, from ' || (SELECT COUNT(*) FROM programs) ||
                 ' distinct programs'
            ELSE 'FAIL  families sum to ' || (SELECT SUM(tasks) FROM families) ||
                 ', solved is ' ||
                 (SELECT json_extract(readfile('reports/eval_training.json'), '$.solved'))
       END;
