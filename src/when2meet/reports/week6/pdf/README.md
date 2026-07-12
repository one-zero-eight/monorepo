# Week 6 Moodle PDF

Typst sources for the Assignment 6 / Week 6 Moodle submission PDF.

The transcript section is generated from [../sprint-review-transcript.md](../sprint-review-transcript.md).

Slide deck PDF for Moodle (not committed): place `When2Meet-presentation-v0-11.pdf` beside this folder for upload. Local copy may exist under `pdf/` but is gitignored.

## Compile

```bash
typst compile src/when2meet/reports/week6/pdf/week6-report.typ \
  src/when2meet/reports/week6/pdf/week6-report.pdf \
  --root src/when2meet/reports/week6
```

Public report links use the `main` branch (no commit-hash permalinks in this pack).
Before Moodle upload, replace `REPLACE_WITH_PRIVATE_SPRINT_REVIEW_RECORDING` in `data/links.yaml` with the private Sprint Review / UAT / transition recording URL.
