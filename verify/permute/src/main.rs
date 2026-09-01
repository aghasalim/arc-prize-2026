//! A permutation test on the split comparison the README leads with, in Rust
//! with no dependencies.
//!
//! The README says the evaluation tasks are bigger, more colourful and come
//! with fewer demo pairs, and that the difference is deliberate rather than an
//! accident of which 120 tasks are in the split. Nothing in the repository ever
//! tested that. The honest test is a permutation test: shuffle the 1,120 split
//! labels, recompute the difference in means, and see how often chance beats
//! what the real split shows.
//!
//! 200,000 shuffles of 1,120 tasks, three statistics accumulated per shuffle,
//! is 224 million label moves. That is the kind of work Python would make you
//! wait minutes for and this finishes in seconds, which is the only reason it
//! is here rather than in scripts/.
//!
//! The generator is a 64-bit xorshift written out below, so the result does not
//! depend on a library either.
//!
//! cargo run --release -- <repository root>

use std::env;
use std::fs;
use std::process;

const PERMUTATIONS: usize = 200_000;
const SEED: u64 = 0x5152_4152_4331_3232;
const TOL: f64 = 1e-9;

struct Xorshift(u64);

impl Xorshift {
    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }
    /// Unbiased index in 0..n by rejection, so a shuffle of 1120 is not skewed
    /// by the modulo that would have been easier to write.
    fn below(&mut self, n: u64) -> u64 {
        let limit = u64::MAX - (u64::MAX % n) - 1;
        loop {
            let v = self.next_u64();
            if v <= limit {
                return v % n;
            }
        }
    }
}

struct Rows {
    cells: Vec<f64>,
    colours: Vec<f64>,
    pairs: Vec<f64>,
    is_eval: Vec<bool>,
}

fn column(header: &str, name: &str) -> usize {
    header
        .trim()
        .split(',')
        .position(|h| h == name)
        .unwrap_or_else(|| {
            eprintln!("Rust: task_stats.csv has no column {name}");
            process::exit(2);
        })
}

fn read_rows(root: &str) -> Rows {
    let path = format!("{root}/reports/task_stats.csv");
    let text = fs::read_to_string(&path).unwrap_or_else(|e| {
        eprintln!("Rust: cannot read {path}: {e}");
        process::exit(2);
    });
    let mut lines = text.lines();
    let header = lines.next().unwrap_or_default();
    let (c_split, c_cells, c_colours, c_pairs) = (
        column(header, "split"),
        column(header, "input_cells"),
        column(header, "distinct_colours"),
        column(header, "demo_pairs"),
    );
    let mut rows = Rows { cells: vec![], colours: vec![], pairs: vec![], is_eval: vec![] };
    for (i, line) in lines.enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let f: Vec<&str> = line.trim().split(',').collect();
        let get = |c: usize| -> f64 {
            f.get(c)
                .and_then(|v| v.parse::<f64>().ok())
                .unwrap_or_else(|| {
                    eprintln!("Rust: row {} of task_stats.csv is not numeric", i + 2);
                    process::exit(1);
                })
        };
        let split = f.get(c_split).copied().unwrap_or("");
        if split != "training" && split != "evaluation" {
            eprintln!("Rust: row {} has split {:?}", i + 2, split);
            process::exit(1);
        }
        rows.is_eval.push(split == "evaluation");
        rows.cells.push(get(c_cells));
        rows.colours.push(get(c_colours));
        rows.pairs.push(get(c_pairs));
    }
    rows
}

/// Difference of means, evaluation minus training, for one column under one
/// labelling.
fn diff(values: &[f64], labels: &[bool], n_eval: usize) -> f64 {
    let mut sum_eval = 0.0;
    let mut sum_all = 0.0;
    for (v, &e) in values.iter().zip(labels) {
        sum_all += v;
        if e {
            sum_eval += v;
        }
    }
    let n = values.len();
    sum_eval / n_eval as f64 - (sum_all - sum_eval) / (n - n_eval) as f64
}

fn published_means(root: &str) -> Vec<(String, f64, f64, f64)> {
    let path = format!("{root}/reports/split_stats.csv");
    let text = fs::read_to_string(&path).unwrap_or_else(|e| {
        eprintln!("Rust: cannot read {path}: {e}");
        process::exit(2);
    });
    let mut out = vec![];
    let mut lines = text.lines();
    let header = lines.next().unwrap_or_default();
    let idx = |name: &str| column(header, name);
    let (c_split, c_cells, c_colours, c_pairs) = (
        idx("split"),
        idx("mean_input_cells"),
        idx("mean_distinct_colours"),
        idx("mean_demo_pairs"),
    );
    for line in lines {
        if line.trim().is_empty() {
            continue;
        }
        let f: Vec<&str> = line.trim().split(',').collect();
        let num = |c: usize| f[c].parse::<f64>().unwrap_or(f64::NAN);
        out.push((f[c_split].to_string(), num(c_cells), num(c_colours), num(c_pairs)));
    }
    out
}

fn main() {
    let root = env::args().nth(1).unwrap_or_else(|| ".".to_string());
    let rows = read_rows(&root);
    let n = rows.cells.len();
    let n_eval = rows.is_eval.iter().filter(|&&e| e).count();
    if n == 0 || n_eval == 0 || n_eval == n {
        eprintln!("Rust: need both splits, got {n_eval} evaluation of {n} rows");
        process::exit(1);
    }
    println!("  {n} tasks, {n_eval} of them evaluation");

    let mut failures = 0;

    // The observed means, recomputed here from the rows, must be the published
    // ones before the test on them means anything.
    let columns: [(&str, &Vec<f64>); 3] = [
        ("input cells", &rows.cells),
        ("distinct colours", &rows.colours),
        ("demo pairs", &rows.pairs),
    ];
    for (split, cells, colours, pairs) in published_means(&root) {
        let want = [cells, colours, pairs];
        let mut worst: f64 = 0.0;
        for (i, (_, values)) in columns.iter().enumerate() {
            let wanted_eval = split == "evaluation";
            let (mut sum, mut count) = (0.0, 0usize);
            for (v, &e) in values.iter().zip(&rows.is_eval) {
                if e == wanted_eval {
                    sum += v;
                    count += 1;
                }
            }
            worst = worst.max((sum / count as f64 - want[i]).abs());
        }
        if worst < TOL {
            println!("  ok   {split:<11} published means reproduced, max |diff| {worst:.1e}");
        } else {
            println!("  FAIL {split}: published means differ by up to {worst:.3e}");
            failures += 1;
        }
    }

    let observed: Vec<f64> = columns
        .iter()
        .map(|(_, v)| diff(v, &rows.is_eval, n_eval))
        .collect();

    // Shuffle the labels, not the values, so all three statistics come from the
    // same permutation and the run costs one shuffle rather than three.
    let mut rng = Xorshift(SEED);
    let mut labels = rows.is_eval.clone();
    let mut extreme = [0usize; 3];
    for _ in 0..PERMUTATIONS {
        for i in (1..n).rev() {
            let j = rng.below(i as u64 + 1) as usize;
            labels.swap(i, j);
        }
        for (k, (_, values)) in columns.iter().enumerate() {
            if diff(values, &labels, n_eval).abs() >= observed[k].abs() {
                extreme[k] += 1;
            }
        }
    }

    for (k, (name, _)) in columns.iter().enumerate() {
        let p = extreme[k] as f64 / PERMUTATIONS as f64;
        let shown = if extreme[k] == 0 {
            format!("< {:.1e}", 1.0 / PERMUTATIONS as f64)
        } else {
            format!("= {p:.5}")
        };
        println!(
            "  ok   {name:<17} evaluation minus training {:+9.4}, permutation p {shown} ({} of {} shuffles as extreme)",
            observed[k], extreme[k], PERMUTATIONS
        );
        // The README treats the first two as real differences. If a shuffle of
        // the labels reproduces them this often, they are not.
        if k < 2 && p >= 0.05 {
            println!("  FAIL {name}: p = {p:.5}, the README calls this difference deliberate");
            failures += 1;
        }
    }

    if failures > 0 {
        println!("\nRust: {failures} disagreement(s)");
        process::exit(1);
    }
    println!("\nRust: {PERMUTATIONS} label shuffles do not reproduce the published split difference");
}
