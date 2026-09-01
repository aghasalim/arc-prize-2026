# Statistical inference on the two claims the README makes about its numbers,
# in base R with no packages.
#
# The README says the training-to-evaluation collapse "is not sampling noise on
# 120 tasks" and that the evaluation tasks are measurably bigger. Both are
# inferential claims and neither had an interval anywhere in the repository.
# This recomputes the point estimates from reports/task_stats.csv by a different
# route, then puts intervals on them:
#
#   1. a bootstrap interval on the 2.05x input-cell ratio, resampling tasks
#      within each split,
#   2. the exact binomial probability of solving 0 of 120 if the evaluation
#      split were as solvable as the training split, and a Clopper-Pearson
#      upper bound on the evaluation solve rate,
#   3. the published percentages, recomputed from the counts.
#
# Rscript verify/verify.R <repository root>

args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args) > 0) args[1] else "."
tol <- 1e-9
bad <- 0
ok <- function(fmt, ...) cat(sprintf(paste0("  ok   ", fmt, "\n"), ...))
fail <- function(fmt, ...) {
  bad <<- bad + 1
  cat(sprintf(paste0("  FAIL ", fmt, "\n"), ...))
}

tasks <- read.csv(file.path(root, "reports", "task_stats.csv"), stringsAsFactors = FALSE)
published <- read.csv(file.path(root, "reports", "split_stats.csv"), stringsAsFactors = FALSE)
stopifnot(nrow(tasks) > 0, nrow(published) == 2)

# 1. the point estimates, by aggregate rather than by a loop.
for (i in seq_len(nrow(published))) {
  s <- published$split[i]
  rows <- tasks[tasks$split == s, ]
  got <- c(nrow(rows), mean(rows$input_cells), mean(rows$distinct_colours), mean(rows$demo_pairs))
  want <- c(published$n_tasks[i], published$mean_input_cells[i],
            published$mean_distinct_colours[i], published$mean_demo_pairs[i])
  d <- max(abs(got - want))
  if (d < tol) {
    ok("%-11s %4d tasks, cells %.4f, colours %.4f, demos %.4f, max |diff| %.1e",
       s, got[1], got[2], got[3], got[4], d)
  } else {
    fail("%s: recomputed %s against published %s", s,
         paste(sprintf("%.6f", got), collapse = "/"), paste(sprintf("%.6f", want), collapse = "/"))
  }
}

train <- tasks$input_cells[tasks$split == "training"]
eval_ <- tasks$input_cells[tasks$split == "evaluation"]
ratio <- mean(eval_) / mean(train)
if (round(ratio, 2) == 2.05) {
  ok("input-cell ratio %.4f rounds to the published 2.05x", ratio)
} else {
  fail("input-cell ratio is %.4f, the README says 2.05", ratio)
}

# 2. a bootstrap interval on that ratio. 120 evaluation tasks is a small sample
# and the README leans on the ratio, so the width is worth knowing.
set.seed(20260101)
B <- 4000
boot <- replicate(B, mean(sample(eval_, replace = TRUE)) / mean(sample(train, replace = TRUE)))
ci <- unname(quantile(boot, c(0.025, 0.975)))
if (ci[1] > 1) {
  ok("bootstrap 95%% CI on the ratio [%.3f, %.3f] from %d resamples, entirely above 1", ci[1], ci[2], B)
} else {
  fail("bootstrap 95%% CI on the ratio [%.3f, %.3f] includes 1", ci[1], ci[2])
}

# 3. the solve rates, and whether 0 of 120 needs an explanation.
report <- function(split) {
  path <- file.path(root, "reports", paste0("eval_", split, ".json"))
  txt <- paste(readLines(path, warn = FALSE), collapse = "")
  num <- function(key) {
    m <- regmatches(txt, regexpr(paste0('"', key, '"[[:space:]]*:[[:space:]]*[0-9.]+'), txt))
    as.numeric(sub('.*:[[:space:]]*', '', m))
  }
  list(n = num("n_tasks"), solved = num("solved"), pct = num("solved_pct"),
       fitwrong = num("fit_demos_but_wrong"), none = num("no_candidate_found"),
       attempt1 = num("attempt1_solved"))
}
tr <- report("training")
ev <- report("evaluation")

for (r in list(tr, ev)) {
  if (abs(round(100 * r$solved / r$n, 2) - r$pct) < tol) {
    ok("%d of %d solved is %.2f%%, as published", r$solved, r$n, r$pct)
  } else {
    fail("%d of %d is %.4f%%, published %.2f%%", r$solved, r$n, 100 * r$solved / r$n, r$pct)
  }
}

# The README's 7%: 3 of the 42 tasks where a program fit every demo pair.
believed <- tr$solved + tr$fitwrong
share <- 100 * tr$fitwrong / believed
if (believed == 42 && round(share) == 7) {
  ok("fit-but-wrong is %d of %d believed rules, %.1f%%, rounds to the published 7%%",
     tr$fitwrong, believed, share)
} else {
  fail("fit-but-wrong is %d of %d, %.1f%%", tr$fitwrong, believed, share)
}
if (abs(100 * tr$none / tr$n - 95.8) < 0.05) {
  ok("no candidate on %d of %d training tasks, %.1f%%, as published", tr$none, tr$n, 100 * tr$none / tr$n)
} else {
  fail("no candidate on %d of %d training tasks", tr$none, tr$n)
}
if (ev$none == ev$n) {
  ok("no candidate on %d of %d evaluation tasks, the published 100%%", ev$none, ev$n)
} else {
  fail("no candidate on %d of %d evaluation tasks", ev$none, ev$n)
}
if (tr$solved - tr$attempt1 == 1) {
  ok("the second attempt bought %d task, %d of %d were already solved on attempt 1",
     tr$solved - tr$attempt1, tr$attempt1, tr$solved)
} else {
  fail("the second attempt bought %d tasks", tr$solved - tr$attempt1)
}

# The inference the README asserts in prose: 0 of 120 is not what the training
# rate would have produced.
p_train <- tr$solved / tr$n
p0 <- dbinom(0, ev$n, p_train)
upper <- binom.test(0, ev$n)$conf.int[2]
ok("if evaluation were as solvable as training (p = %.3f), P(0 of %d) = %.4f",
   p_train, ev$n, p0)
ok("exact 95%% upper bound on the evaluation solve rate, 0 of %d, is %.2f%%", ev$n, 100 * upper)
if (p0 >= 0.05) {
  fail("0 of %d is not unusual under the training rate (p = %.3f), the README calls it a collapse", ev$n, p0)
}

if (bad > 0) {
  cat(sprintf("\nR: %d disagreement(s)\n", bad))
  quit(status = 1)
}
cat("\nR: the point estimates hold and the two inferential claims survive an interval\n")
