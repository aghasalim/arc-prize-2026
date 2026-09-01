// Structural validation of every task file under data/, plus an independent
// recomputation of the scoreboard in reports/eval_*.json.
//
// The 1,120 task JSONs are the input to every number this repository publishes,
// and nothing checked they are well formed. arc/grid.py calls np.array on each
// grid, which turns a ragged grid into an object array rather than an error, and
// a colour outside 0-9 or an empty grid would flow straight through the search.
// This walks all of them and rejects ragged rows, out-of-range colours, empty
// grids, dimensions outside the ARC 1-30 limit, and missing train/test keys.
//
// The second half re-derives two published tables. reports/task_stats.csv is
// the per-task row level behind the README's split comparison, and it was
// written by the same Python loop that read the JSON, so nothing independent
// had ever confirmed a single row of it. Here every row is recomputed from the
// task file itself. Then the scoreboard is re-derived. arc/evaluate.py counts solved,
// fit-but-wrong and no-candidate in one pass and writes them next to the id
// lists it built alongside them. If that counting were wrong, every table and
// figure downstream would repeat the same wrong number, because they all read
// this one file. Here the counts are rebuilt from the id lists and the program
// histogram, and the split totals are checked against the files on disk.
package main

import (
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const (
	maxColour = 9
	maxSide   = 30 // ARC-AGI-2 grids are at most 30 by 30
)

type pair struct {
	Input  [][]int `json:"input"`
	Output [][]int `json:"output"`
}

type task struct {
	Train []pair `json:"train"`
	Test  []pair `json:"test"`
}

type report struct {
	Split            string         `json:"split"`
	NTasks           int            `json:"n_tasks"`
	MaxDepth         int            `json:"max_depth"`
	Solved           int            `json:"solved"`
	SolvedPct        float64        `json:"solved_pct"`
	Attempt1Solved   int            `json:"attempt1_solved"`
	FitDemosButWrong int            `json:"fit_demos_but_wrong"`
	NoCandidateFound int            `json:"no_candidate_found"`
	ByProgram        map[string]int `json:"by_program"`
	SolvedIDs        []string       `json:"solved_ids"`
	FitwrongIDs      []string       `json:"fitwrong_ids"`
}

// grid returns every structural problem with one grid rather than the first, so
// a bad file is diagnosed in one pass.
func checkGrid(where string, g [][]int) []string {
	var problems []string
	if len(g) == 0 {
		return []string{where + ": grid has no rows"}
	}
	width := len(g[0])
	if width == 0 {
		problems = append(problems, where+": first row is empty")
	}
	if len(g) > maxSide || width > maxSide {
		problems = append(problems,
			fmt.Sprintf("%s: %dx%d exceeds the %d by %d limit", where, len(g), width, maxSide, maxSide))
	}
	for r, row := range g {
		if len(row) != width {
			problems = append(problems,
				fmt.Sprintf("%s: row %d has %d cells, row 0 has %d", where, r, len(row), width))
		}
		for c, v := range row {
			if v < 0 || v > maxColour {
				problems = append(problems,
					fmt.Sprintf("%s: cell (%d,%d) is colour %d, outside 0-%d", where, r, c, v, maxColour))
			}
		}
	}
	return problems
}

func checkTask(path string) []string {
	raw, err := os.ReadFile(path)
	if err != nil {
		return []string{fmt.Sprintf("unreadable: %v", err)}
	}

	// Decode twice: once into the typed shape, once into a generic map, so an
	// unexpected top-level key or a non-integer cell is caught rather than
	// silently dropped by the typed decode.
	var generic map[string]any
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	if err := dec.Decode(&generic); err != nil {
		return []string{fmt.Sprintf("not a JSON object: %v", err)}
	}
	var problems []string
	for key := range generic {
		if key != "train" && key != "test" {
			problems = append(problems, fmt.Sprintf("unexpected top level key %q", key))
		}
	}

	var t task
	strict := json.NewDecoder(strings.NewReader(string(raw)))
	strict.DisallowUnknownFields()
	if err := strict.Decode(&t); err != nil {
		return append(problems, fmt.Sprintf("does not match the task shape: %v", err))
	}
	if len(t.Train) == 0 {
		problems = append(problems, "no demo pairs")
	}
	if len(t.Test) == 0 {
		problems = append(problems, "no test pairs")
	}
	for i, p := range t.Train {
		problems = append(problems, checkGrid(fmt.Sprintf("train[%d].input", i), p.Input)...)
		problems = append(problems, checkGrid(fmt.Sprintf("train[%d].output", i), p.Output)...)
	}
	for i, p := range t.Test {
		problems = append(problems, checkGrid(fmt.Sprintf("test[%d].input", i), p.Input)...)
		// The public splits ship test outputs. evaluate.py skips a task whose
		// test output is missing, so a missing one would silently shrink the
		// denominator the percentages are computed over.
		problems = append(problems, checkGrid(fmt.Sprintf("test[%d].output", i), p.Output)...)
	}
	return problems
}

func validateSplit(root, split string) (int, int) {
	dir := filepath.Join(root, "data", split)
	files, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil || len(files) == 0 {
		fmt.Fprintf(os.Stderr, "no task files under %s\n", dir)
		os.Exit(2)
	}
	sort.Strings(files)

	bad := 0
	for _, path := range files {
		for _, p := range checkTask(path) {
			bad++
			if bad <= 20 {
				fmt.Printf("  %s: %s\n", filepath.Base(path), p)
			}
		}
	}
	if bad == 0 {
		fmt.Printf("  %-11s %4d files, all grids rectangular, colours 0-9, train and test present\n",
			split, len(files))
	} else {
		fmt.Printf("  %-11s %4d files, %d problems\n", split, len(files), bad)
	}
	return len(files), bad
}

func readReport(root, split string) (report, error) {
	var r report
	raw, err := os.ReadFile(filepath.Join(root, "reports", "eval_"+split+".json"))
	if err != nil {
		return r, err
	}
	return r, json.Unmarshal(raw, &r)
}

// The counts and the id lists in eval_*.json are written by the same loop, so
// they agree by construction only if that loop is right. Rebuilding each count
// from the other fields is what catches a miscount.
func checkScoreboard(root, split string, files int) int {
	r, err := readReport(root, split)
	if err != nil {
		fmt.Fprintf(os.Stderr, "eval_%s.json: %v\n", split, err)
		os.Exit(2)
	}
	bad := 0
	fail := func(format string, args ...any) {
		bad++
		fmt.Printf("  FAIL %s: %s\n", split, fmt.Sprintf(format, args...))
	}

	if r.Split != split {
		fail("labelled %q", r.Split)
	}
	if r.NTasks != files {
		fail("claims %d tasks, data/%s holds %d files", r.NTasks, split, files)
	}
	if got := len(r.SolvedIDs); got != r.Solved {
		fail("solved is %d but solved_ids has %d entries", r.Solved, got)
	}
	sum := 0
	for _, v := range r.ByProgram {
		sum += v
	}
	if sum != r.Solved {
		fail("by_program sums to %d, solved is %d", sum, r.Solved)
	}
	if total := r.Solved + r.FitDemosButWrong + r.NoCandidateFound; total != r.NTasks {
		fail("%d + %d + %d is %d, not the %d tasks in the split",
			r.Solved, r.FitDemosButWrong, r.NoCandidateFound, total, r.NTasks)
	}
	if want := math.Round(100*float64(r.Solved)/float64(r.NTasks)*100) / 100; want != r.SolvedPct {
		fail("solved_pct is %v, recomputed %v", r.SolvedPct, want)
	}
	if r.Attempt1Solved > r.Solved {
		fail("attempt1_solved %d exceeds solved %d", r.Attempt1Solved, r.Solved)
	}
	// fitwrong_ids is truncated to 25 by evaluate.py, so it can only be checked
	// as a lower bound on the count it came from.
	if len(r.FitwrongIDs) > r.FitDemosButWrong {
		fail("fitwrong_ids has %d entries but fit_demos_but_wrong is %d",
			len(r.FitwrongIDs), r.FitDemosButWrong)
	}

	// Every id named must be a task that exists, and no id may be named twice.
	seen := map[string]bool{}
	for _, ids := range [][]string{r.SolvedIDs, r.FitwrongIDs} {
		for _, id := range ids {
			if seen[id] {
				fail("task %s is listed twice", id)
			}
			seen[id] = true
			if _, err := os.Stat(filepath.Join(root, "data", split, id+".json")); err != nil {
				fail("task %s is named but data/%s/%s.json does not exist", id, split, id)
			}
		}
	}

	if bad == 0 {
		fmt.Printf("  %-11s solved %d of %d (%.2f%%), %d fit-but-wrong, %d no candidate, "+
			"%d distinct programs, all consistent\n",
			split, r.Solved, r.NTasks, r.SolvedPct, r.FitDemosButWrong,
			r.NoCandidateFound, len(r.ByProgram))
	}
	return bad
}

// taskStats is the per-task row of reports/task_stats.csv, recomputed here from
// the task JSON. The definitions are the ones scripts/split_stats.py documents:
// demo pairs only, test grids excluded, cells averaged over the demo inputs.
type taskStats struct {
	pairs   int
	cells   float64
	colours int
}

func statsOf(t task) taskStats {
	seen := map[int]bool{}
	total := 0
	for _, p := range t.Train {
		if len(p.Input) > 0 {
			total += len(p.Input) * len(p.Input[0])
		}
		for _, row := range p.Input {
			for _, v := range row {
				seen[v] = true
			}
		}
	}
	return taskStats{pairs: len(t.Train), cells: float64(total) / float64(len(t.Train)), colours: len(seen)}
}

// checkTaskStats walks data/ again and requires every row of task_stats.csv to
// match the file it claims to describe, in both directions.
func checkTaskStats(root string) int {
	f, err := os.Open(filepath.Join(root, "reports", "task_stats.csv"))
	if err != nil {
		fmt.Fprintf(os.Stderr, "task_stats.csv: %v\n", err)
		os.Exit(2)
	}
	defer f.Close()
	rows, err := csv.NewReader(f).ReadAll()
	if err != nil || len(rows) < 2 {
		fmt.Fprintf(os.Stderr, "task_stats.csv: %v\n", err)
		os.Exit(2)
	}
	col := map[string]int{}
	for i, name := range rows[0] {
		col[name] = i
	}
	for _, name := range []string{"split", "task_id", "demo_pairs", "input_cells", "distinct_colours"} {
		if _, ok := col[name]; !ok {
			fmt.Fprintf(os.Stderr, "task_stats.csv has no column %q\n", name)
			os.Exit(2)
		}
	}

	bad := 0
	fail := func(format string, args ...any) {
		bad++
		if bad <= 20 {
			fmt.Printf("  FAIL %s\n", fmt.Sprintf(format, args...))
		}
	}

	seen := map[string]bool{}
	worst := 0.0
	for _, r := range rows[1:] {
		split, id := r[col["split"]], r[col["task_id"]]
		key := split + "/" + id
		if seen[key] {
			fail("%s appears twice in task_stats.csv", key)
			continue
		}
		seen[key] = true
		raw, err := os.ReadFile(filepath.Join(root, "data", split, id+".json"))
		if err != nil {
			fail("%s is in task_stats.csv but %v", key, err)
			continue
		}
		var t task
		if err := json.Unmarshal(raw, &t); err != nil || len(t.Train) == 0 {
			fail("%s: cannot read demo pairs", key)
			continue
		}
		got := statsOf(t)
		pairs, _ := strconv.Atoi(r[col["demo_pairs"]])
		colours, _ := strconv.Atoi(r[col["distinct_colours"]])
		cells, _ := strconv.ParseFloat(r[col["input_cells"]], 64)
		if pairs != got.pairs {
			fail("%s: demo_pairs %d, the file has %d", key, pairs, got.pairs)
		}
		if colours != got.colours {
			fail("%s: distinct_colours %d, the file has %d", key, colours, got.colours)
		}
		if d := math.Abs(cells - got.cells); d > 1e-9 {
			fail("%s: input_cells %v, recomputed %v", key, cells, got.cells)
		} else if d > worst {
			worst = d
		}
	}

	// The other direction: a task file with no row would drop out of the means
	// without changing any number in the file.
	for _, split := range []string{"training", "evaluation"} {
		files, _ := filepath.Glob(filepath.Join(root, "data", split, "*.json"))
		for _, path := range files {
			key := split + "/" + strings.TrimSuffix(filepath.Base(path), ".json")
			if !seen[key] {
				fail("%s has no row in task_stats.csv", key)
			}
		}
	}

	if bad == 0 {
		fmt.Printf("  all %d rows recomputed from the task JSON, worst |diff| on input_cells %.1e\n",
			len(rows)-1, worst)
	}
	return bad
}

func main() {
	root := flag.String("root", ".", "repository root")
	flag.Parse()

	bad := 0
	fmt.Println("structural validation of every task file under data/")
	counts := map[string]int{}
	for _, split := range []string{"training", "evaluation"} {
		n, problems := validateSplit(*root, split)
		counts[split] = n
		bad += problems
	}

	fmt.Println("\nrecomputing every row of reports/task_stats.csv from the task files")
	bad += checkTaskStats(*root)

	fmt.Println("\nrebuilding the scoreboard from reports/eval_*.json")
	for _, split := range []string{"training", "evaluation"} {
		bad += checkScoreboard(*root, split, counts[split])
	}

	if bad > 0 {
		fmt.Printf("\n%d problems\n", bad)
		os.Exit(1)
	}
	fmt.Println("\nGo: the task data is well formed, every task row matches its file, and the scoreboard adds up")
}
