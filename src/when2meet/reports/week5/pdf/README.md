# Week 5 Moodle PDF

Typst sources for the Assignment 5 Moodle submission PDF.

The transcript section is generated from [../sprint-review-transcript.md](../sprint-review-transcript.md).

## Compile

```bash
typst compile src/when2meet/reports/week5/pdf/week5-report.typ \
  src/when2meet/reports/week5/pdf/week5-report.pdf \
  --root src/when2meet/reports/week5
```

Before compiling, update `data/submission.yaml` and public permalinks in `data/links.yaml` with the final submission commit hash.
