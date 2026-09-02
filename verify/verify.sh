#!/usr/bin/env bash
# Recompute the published numbers in every language here and require agreement.
#
# Every table in this repository comes out of one Python script, and every
# figure reads the file that script wrote. If the counting were wrong, nothing
# downstream would notice, because everything downstream is downstream of the
# same mistake. The tests checked that the code runs, not that it is right.
#
# So the summary tables are rebuilt from the 1,120 task files and from the
# per-task rows by five other languages, and the README is checked against the
# files it quotes. A mistake would have to be made identically in all of them.
#
# Each implementation is skipped with a message if its toolchain is missing, so
# a partial install still runs the rest. CI has all of them.
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

pass=0 fail=0 skip=0

run () {
    local name="$1" tool="$2"; shift 2
    printf '\n=== %s ===\n' "$name"
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'skipped: %s is not installed\n' "$tool"
        skip=$((skip + 1)); return
    fi
    if "$@"; then pass=$((pass + 1)); else fail=$((fail + 1)); fi
}

# SQLite has no assert, so the script prints an ok or FAIL line per check and
# the verdict is taken here. stdin is redirected from /dev/null because sqlite3
# would otherwise read the rest of this script as SQL.
check_sql () {
    local out
    out=$(sqlite3 -init verify/aggregate.sql :memory: "" < /dev/null 2>&1 | tr -d '\r')
    printf '%s\n' "$out"
    if printf '%s' "$out" | grep -q '^FAIL'; then return 1; fi
    local n
    n=$(printf '%s\n' "$out" | grep -c '^ok')
    if [ "$n" -lt 12 ]; then
        printf 'only %s checks ran, expected 12\n' "$n"; return 1
    fi
}

check_c () {
    cc -std=c99 -O2 -Wall -Wextra -Wpedantic -Werror \
       -o "${TMPDIR:-/tmp}/splitmeans" verify/splitmeans.c -lm || return 1
    "${TMPDIR:-/tmp}/splitmeans" "$root"
}

check_go () { ( cd verify/gocheck && go run . -root "$root" ); }

check_rust () { ( cd verify/permute && cargo run --release --quiet -- "$root" ); }

run "SQL, the summary from the task rows"  sqlite3 check_sql
run "C, the split means, columns by name"  cc      check_c
run "Go, every task file and every row"    go      check_go
run "R, intervals on the two claims"       Rscript Rscript verify/verify.R "$root"
run "Rust, 200k label permutations"        cargo   check_rust
run "Ruby, the README against the files"   ruby    ruby verify/claims.rb "$root"
run "Python, point estimates and solve rates" python3 python3 verify/check.py "$root"
run "JS, the README against the files"    node    node verify/claims.mjs "$root"

printf '\n%s\n' "----------------------------------------"
printf '%d passed, %d failed, %d skipped\n' "$pass" "$fail" "$skip"
[ "$fail" -eq 0 ] || exit 1
[ "$pass" -gt 0 ] || { echo "nothing ran"; exit 1; }
