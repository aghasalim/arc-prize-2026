/* Recompute the published split means from the per-task rows, in C.
 *
 * reports/split_stats.csv is the two-row table the README quotes. It was
 * produced by the same Python pass that wrote reports/task_stats.csv, so the
 * summary has never been checked against the rows it summarises by anything
 * that did not share the loop that built it. This reads the 1,120 rows and
 * averages them again.
 *
 * Columns are resolved by name from the header, not by position, so adding or
 * reordering a column in either file cannot silently change which number is
 * being compared. Every value is required to match to 1e-9.
 *
 *   cc -std=c99 -O2 -Wall -Wextra -Wpedantic -Werror -o splitmeans splitmeans.c
 *   ./splitmeans <repository root>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define MAXCOL 32
#define MAXLINE 4096
#define TOL 1e-9

struct acc {
    char split[64];
    long n;
    double cells, colours, pairs;
};

/* Split one CSV line in place. Returns the field count. The two files here are
 * plain numeric CSV with no quoting, and anything else is a bug worth failing
 * on, so quoting is deliberately not supported. */
static int split_line(char *line, char *out[MAXCOL])
{
    int n = 0;
    char *p = line;
    line[strcspn(line, "\r\n")] = '\0';
    out[n++] = p;
    for (; *p; p++) {
        if (*p == ',') {
            *p = '\0';
            if (n == MAXCOL) return -1;
            out[n++] = p + 1;
        }
    }
    return n;
}

static int column_of(char *header[MAXCOL], int ncol, const char *name)
{
    for (int i = 0; i < ncol; i++)
        if (strcmp(header[i], name) == 0) return i;
    fprintf(stderr, "C: no column named %s\n", name);
    exit(2);
}

static FILE *open_at(const char *root, const char *rel)
{
    char path[1024];
    FILE *f;
    snprintf(path, sizeof path, "%s/%s", root, rel);
    f = fopen(path, "r");
    if (!f) { fprintf(stderr, "C: cannot open %s\n", path); exit(2); }
    return f;
}

int main(int argc, char **argv)
{
    const char *root = argc > 1 ? argv[1] : ".";
    char line[MAXLINE], *field[MAXCOL];
    struct acc acc[8];
    int nacc = 0, ncol, c_split, c_cells, c_colours, c_pairs, bad = 0;
    long rows = 0;
    FILE *f;

    f = open_at(root, "reports/task_stats.csv");
    if (!fgets(line, sizeof line, f)) { fprintf(stderr, "C: empty task_stats.csv\n"); return 2; }
    ncol = split_line(line, field);
    c_split   = column_of(field, ncol, "split");
    c_cells   = column_of(field, ncol, "input_cells");
    c_colours = column_of(field, ncol, "distinct_colours");
    c_pairs   = column_of(field, ncol, "demo_pairs");

    while (fgets(line, sizeof line, f)) {
        int i, n = split_line(line, field);
        if (n != ncol) {
            fprintf(stderr, "C: row %ld has %d fields, the header has %d\n", rows + 1, n, ncol);
            fclose(f);
            return 1;
        }
        for (i = 0; i < nacc; i++)
            if (strcmp(acc[i].split, field[c_split]) == 0) break;
        if (i == nacc) {
            if (nacc == 8) { fprintf(stderr, "C: too many splits\n"); fclose(f); return 2; }
            snprintf(acc[i].split, sizeof acc[i].split, "%s", field[c_split]);
            acc[i].n = 0; acc[i].cells = acc[i].colours = acc[i].pairs = 0.0;
            nacc++;
        }
        acc[i].n++;
        acc[i].cells   += atof(field[c_cells]);
        acc[i].colours += atof(field[c_colours]);
        acc[i].pairs   += atof(field[c_pairs]);
        rows++;
    }
    fclose(f);
    printf("  read %ld task rows in %d splits\n", rows, nacc);

    f = open_at(root, "reports/split_stats.csv");
    if (!fgets(line, sizeof line, f)) { fprintf(stderr, "C: empty split_stats.csv\n"); return 2; }
    ncol = split_line(line, field);
    c_split   = column_of(field, ncol, "split");
    c_cells   = column_of(field, ncol, "mean_input_cells");
    c_colours = column_of(field, ncol, "mean_distinct_colours");
    c_pairs   = column_of(field, ncol, "mean_demo_pairs");
    {
        int c_n = column_of(field, ncol, "n_tasks");
        int seen = 0;
        while (fgets(line, sizeof line, f)) {
            int i, n = split_line(line, field);
            double d[3], want[3];
            if (n != ncol) { fprintf(stderr, "C: ragged row in split_stats.csv\n"); fclose(f); return 1; }
            for (i = 0; i < nacc; i++)
                if (strcmp(acc[i].split, field[c_split]) == 0) break;
            if (i == nacc) {
                printf("  FAIL split_stats.csv names split %s, which no task row uses\n", field[c_split]);
                bad++;
                continue;
            }
            seen++;
            want[0] = atof(field[c_cells]);
            want[1] = atof(field[c_colours]);
            want[2] = atof(field[c_pairs]);
            d[0] = fabs(acc[i].cells   / (double)acc[i].n - want[0]);
            d[1] = fabs(acc[i].colours / (double)acc[i].n - want[1]);
            d[2] = fabs(acc[i].pairs   / (double)acc[i].n - want[2]);
            if (atol(field[c_n]) != acc[i].n) {
                printf("  FAIL %s: published n_tasks %s, counted %ld rows\n",
                       acc[i].split, field[c_n], acc[i].n);
                bad++;
            }
            if (d[0] < TOL && d[1] < TOL && d[2] < TOL) {
                printf("  ok   %-11s %4ld tasks, cells %.4f, colours %.4f, demos %.4f,"
                       " max |diff| %.1e\n", acc[i].split, acc[i].n,
                       acc[i].cells / acc[i].n, acc[i].colours / acc[i].n,
                       acc[i].pairs / acc[i].n,
                       d[0] > d[1] ? (d[0] > d[2] ? d[0] : d[2]) : (d[1] > d[2] ? d[1] : d[2]));
            } else {
                printf("  FAIL %s: cells diff %.3e, colours diff %.3e, demos diff %.3e\n",
                       acc[i].split, d[0], d[1], d[2]);
                bad++;
            }
        }
        if (seen != nacc) {
            printf("  FAIL task_stats.csv has %d splits, split_stats.csv publishes %d\n", nacc, seen);
            bad++;
        }
    }
    fclose(f);

    if (bad) { printf("C: %d disagreement(s)\n", bad); return 1; }
    printf("C: the published means are the means of the 1120 task rows\n");
    return 0;
}
