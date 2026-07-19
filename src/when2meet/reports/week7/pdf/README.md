# Week 7 Moodle PDF

Typst sources for the Assignment 6 / Week 7 Moodle submission PDF.

The transcript section is generated from [../sprint-review-transcript.md](../sprint-review-transcript.md).

Slide deck PDF for Moodle (not committed): `When2Meet-presentation-v1-4.pdf`. Local copy may exist under Downloads or beside this folder but is gitignored via `*.pdf`.

`../assignment.md` is local course text only — do not commit it.

## Compile

```bash
typst compile src/when2meet/reports/week7/pdf/week7-report.typ \
  src/when2meet/reports/week7/pdf/week7-report.pdf \
  --root src/when2meet/reports/week7
```

After merging the Week 7 report to protected `main`, update `data/submission.yaml` commit hash and permalinks, then recompile.
