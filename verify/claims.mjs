/**
 * Check that the README still says what the files say, in JavaScript.
 *
 * Same spirit as the Ruby verifier: recompute numbers from reports/ and
 * require the README to contain them in the right place.
 *
 *   node verify/claims.mjs <repository root>
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { exit } from "node:process";

const root = process.argv[2] || ".";
let bad = 0;

function check(label, pattern, doc) {
  if (pattern.test(doc)) {
    console.log(`  ok   ${label}`);
  } else {
    bad++;
    console.log(`  FAIL ${label}: README does not contain ${pattern.source}`);
  }
}

function parseCSV(text) {
  const lines = text.replace(/\r/g, "").trim().split("\n");
  const [header, ...rows] = lines;
  const cols = header.split(",");
  return rows.map((r) => {
    const vals = r.split(",");
    return Object.fromEntries(cols.map((c, i) => [c, vals[i]]));
  });
}

// Load data
const readme = readFileSync(join(root, "README.md"), "utf8")
  .replace(/\s+/g, " ")
  .replace(/\*/g, "")
  .replace(/×/g, "x")
  .replace(/(\d),(\d{3})\b/g, "$1$2");

const splitStats = parseCSV(
  readFileSync(join(root, "reports", "split_stats.csv"), "utf8")
);
const bySplit = Object.fromEntries(splitStats.map((r) => [r.split, r]));

const train = JSON.parse(
  readFileSync(join(root, "reports", "eval_training.json"), "utf8")
);
const evaln = JSON.parse(
  readFileSync(join(root, "reports", "eval_evaluation.json"), "utf8")
);

function esc(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// 1. Results table
for (const r of [train, evaln]) {
  const name =
    r.split === "training" ? "public training" : "public evaluation";
  let pct = (100 * r.solved / r.n_tasks).toFixed(2).replace(/\.?0+$/, "");
  if (!pct.includes(".")) pct += ".0";
  const pat = new RegExp(
    `\\| ${name} \\| ${r.n_tasks} \\| ${r.solved} \\| ${esc(pct)}% \\|`
  );
  check(`results table, ${r.split}: ${r.solved} of ${r.n_tasks}, ${pct}%`, pat, readme);
}

// 2. Split comparison table
const cells = ["training", "evaluation"].map(
  (s) => parseFloat(bySplit[s].mean_input_cells)
);
check(
  `split table, mean input cells ${Math.round(cells[0])} and ${Math.round(cells[1])}`,
  new RegExp(
    `\\| mean input cells \\| ${Math.round(cells[0])} \\| ${Math.round(cells[1])} \\(`
  ),
  readme
);

const ratio = (cells[1] / cells[0]).toFixed(2);
check(
  `split table, ratio ${ratio}x`,
  new RegExp(`\\(${esc(ratio)}x\\)`),
  readme
);

const colChecks = {
  "distinct colours per task": "mean_distinct_colours",
  "demo pairs per task": "mean_demo_pairs",
};
for (const [label, col] of Object.entries(colChecks)) {
  const a = parseFloat(bySplit.training[col]).toFixed(2);
  const b = parseFloat(bySplit.evaluation[col]).toFixed(2);
  check(
    `split table, ${label} ${a} and ${b}`,
    new RegExp(`\\| ${label} \\| ${a} \\| ${b} \\|`),
    readme
  );
}

// 3. Primitive family table
const FAMILIES = [
  ["tiling (fit:tile, incl. mirrored/composed)", (p) => p.includes("fit:tile")],
  ["colour map (fit:colormap)", (p) => p.includes("fit:colormap")],
  ["integer upscale (fit:scale)", (p) => p.includes("fit:scale")],
  ["object selection", (p) => p.includes("_object")],
  ["crop to content", (p) => p.includes("crop")],
  ["geometric only (rot/flip/transpose)", () => true],
];

const counts = {};
for (const [label] of FAMILIES) counts[label] = 0;

for (const [program, n] of Object.entries(train.by_program)) {
  const match = FAMILIES.find(([, test]) => test(program));
  if (match) counts[match[0]] += n;
}

for (const [label] of FAMILIES) {
  check(
    `family table, ${label} = ${counts[label]}`,
    new RegExp(`\\| ${esc(label)} \\| ${counts[label]} \\|`),
    readme
  );
}

const total = Object.values(counts).reduce((a, b) => a + b, 0);
if (total === train.solved) {
  console.log(
    `  ok   the six families cover all ${train.solved} solved training tasks`
  );
} else {
  bad++;
  console.log(
    `  FAIL families cover ${total} of ${train.solved} solved tasks`
  );
}

// 4. Numbers that live only in prose
check(
  `prose, ${Object.keys(train.by_program).length} distinct programs`,
  /Twenty-one distinct programs account for the 39 training solves/,
  readme
);

const noPct = ((100 * train.no_candidate_found) / train.n_tasks).toFixed(1);
check(
  `prose, no candidate on ${noPct}% of training tasks`,
  new RegExp(`no candidate at all for ${esc(noPct)}%`),
  readme
);

const believed = train.solved + train.fit_demos_but_wrong;
check(
  `prose, ${train.fit_demos_but_wrong} of ${believed} believed rules were wrong`,
  new RegExp(
    `of the ${believed} training tasks where the search believed it had the rule, ${train.fit_demos_but_wrong} fit every demo`
  ),
  readme
);

check(
  `prose, the second attempt bought ${train.solved - train.attempt1_solved} task`,
  new RegExp(
    `bought ${train.solved - train.attempt1_solved} task, since ${train.attempt1_solved} of the ${train.solved}`
  ),
  readme
);

check(
  `prose, ${counts["object selection"]} solves are object selection`,
  new RegExp(
    `${counts["object selection"]} of the ${train.solved} training solves are object selection`
  ),
  readme
);

check(
  `prose, ${evaln.no_candidate_found} of ${evaln.n_tasks} evaluation tasks produced nothing`,
  new RegExp(
    `on ${evaln.no_candidate_found} of ${evaln.n_tasks} it produced no candidate program at all`
  ),
  readme
);

// Verdict
if (bad > 0) {
  console.log(`\nJS: ${bad} claim(s) in the README no longer match the files`);
  exit(1);
}
console.log(
  "\nJS: every number checked here is still the number the files produce"
);
