# Week 4 Moodle PDF

Typst sources for the Assignment 4 Moodle submission PDF.

## Compile

```bash
typst compile src/when2meet/reports/week4/pdf/week4-report.typ \
  src/when2meet/reports/week4/pdf/week4-report.pdf \
  --root src/when2meet/reports/week4
```

Before compiling, update `data/submission.yaml` and public permalinks in `data/links.yaml` with the final submission commit hash.
