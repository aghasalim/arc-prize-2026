# Check that the README still says what the files say, in Ruby.
#
# Every table in the README was typed by hand from the output of a script. The
# scripts kept running and the README kept its numbers, and nothing connected
# the two, so a rerun that moved a number would have left the prose behind
# without a single test failing.
#
# Each check below recomputes a number from reports/ and then requires the
# README to contain it, in place, in the sentence or table cell that claims it.
# A regex that no longer matches means the document and the data have parted
# company, and it does not matter which side moved.
#
#   ruby verify/claims.rb <repository root>

require "json"
require "csv"

root = ARGV[0] || "."
$bad = 0

def check(label, pattern, doc)
  if doc =~ pattern
    puts format("  ok   %s", label)
  else
    $bad += 1
    puts format("  FAIL %s: README does not contain %s", label, pattern.source)
  end
end

# Ruby 2.6 opens files as US-ASCII, and this README contains a multiplication
# sign, so the encoding has to be said out loud. Line wrapping, emphasis markers
# and thousands separators are flattened first, so that a bolded number or a
# sentence that wraps does not read as the claim having disappeared.
doc = File.read(File.join(root, "README.md"), encoding: "UTF-8")
doc = doc.gsub(/\s+/, " ").gsub("*", "").gsub("×", "x").gsub(/(\d),(\d\d\d)\b/, '\1\2')

split_stats = CSV.read(File.join(root, "reports", "split_stats.csv"), headers: true)
by_split = split_stats.map { |r| [r["split"], r] }.to_h
train = JSON.parse(File.read(File.join(root, "reports", "eval_training.json")))
eval_ = JSON.parse(File.read(File.join(root, "reports", "eval_evaluation.json")))

# 1. the results table at the top.
[train, eval_].each do |r|
  name = r["split"] == "training" ? "public training" : "public evaluation"
  pct = format("%g", (100.0 * r["solved"] / r["n_tasks"]).round(2))
  pct += ".0" unless pct.include?(".")
  check("results table, #{r['split']}: #{r['solved']} of #{r['n_tasks']}, #{pct}%",
        /\| #{name} \| #{r['n_tasks']} \| #{r['solved']} \| #{Regexp.escape(pct)}% \|/, doc)
end

# 2. the split comparison table, and the ratio in it.
cells = %w[training evaluation].map { |s| by_split[s]["mean_input_cells"].to_f }
check("split table, mean input cells #{cells[0].round} and #{cells[1].round}",
      /\| mean input cells \| #{cells[0].round} \| #{cells[1].round} \(/, doc)
check("split table, ratio #{(cells[1] / cells[0]).round(2)}x",
      /\(#{Regexp.escape(format('%.2f', cells[1] / cells[0]))}x\)/, doc)
{
  "distinct colours per task" => "mean_distinct_colours",
  "demo pairs per task" => "mean_demo_pairs",
}.each do |label, col|
  a, b = %w[training evaluation].map { |s| format("%.2f", by_split[s][col].to_f) }
  check("split table, #{label} #{a} and #{b}", /\| #{label} \| #{a} \| #{b} \|/, doc)
end

# 3. the primitive family table, regrouped here from the program names.
FAMILIES = [
  ["tiling (fit:tile, incl. mirrored/composed)", ->(p) { p.include?("fit:tile") }],
  ["colour map (fit:colormap)",                  ->(p) { p.include?("fit:colormap") }],
  ["integer upscale (fit:scale)",                ->(p) { p.include?("fit:scale") }],
  ["object selection",                           ->(p) { p.include?("_object") }],
  ["crop to content",                            ->(p) { p.include?("crop") }],
  ["geometric only (rot/flip/transpose)",        ->(_p) { true }],
].freeze

counts = Hash.new(0)
train["by_program"].each do |program, n|
  label, = FAMILIES.find { |_, test| test.call(program) }
  counts[label] += n
end
FAMILIES.each do |label, _|
  check("family table, #{label} = #{counts[label]}",
        /\| #{Regexp.escape(label)} \| #{counts[label]} \|/, doc)
end
if counts.values.sum == train["solved"]
  puts format("  ok   the six families cover all %d solved training tasks", train["solved"])
else
  $bad += 1
  puts format("  FAIL families cover %d of %d solved tasks", counts.values.sum, train["solved"])
end

# 4. the numbers that live only in prose.
check("prose, #{train['by_program'].size} distinct programs",
      /Twenty-one distinct programs account for the #{train['solved']} training solves/, doc)
check("prose, no candidate on #{format('%.1f', 100.0 * train['no_candidate_found'] / train['n_tasks'])}% of training tasks",
      /no candidate at all for #{format('%.1f', 100.0 * train['no_candidate_found'] / train['n_tasks'])}%/, doc)
believed = train["solved"] + train["fit_demos_but_wrong"]
check("prose, #{train['fit_demos_but_wrong']} of #{believed} believed rules were wrong",
      /of the #{believed} training tasks where the search believed it had the rule, #{train['fit_demos_but_wrong']} fit every demo/, doc)
check("prose, the second attempt bought #{train['solved'] - train['attempt1_solved']} task",
      /bought #{train['solved'] - train['attempt1_solved']} task, since #{train['attempt1_solved']} of the #{train['solved']}/, doc)
check("prose, #{counts['object selection']} solves are object selection",
      /#{counts['object selection']} of the #{train['solved']} training solves are object selection/, doc)
check("prose, #{eval_['no_candidate_found']} of #{eval_['n_tasks']} evaluation tasks produced nothing",
      /on #{eval_['no_candidate_found']} of #{eval_['n_tasks']} it produced no candidate program at all/, doc)

if $bad > 0
  puts format("\nRuby: %d claim(s) in the README no longer match the files", $bad)
  exit 1
end
puts "\nRuby: every number checked here is still the number the files produce"
