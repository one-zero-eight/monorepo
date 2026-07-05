#set page(paper: "a4", margin: (x: 2.5cm, y: 2cm))
#set par(leading: 0.65em, justify: true)
#set text(font: "New Computer Modern", size: 10.5pt)

#let team = yaml("data/team.yaml").at("team")
#let non-participants = yaml("data/team.yaml").at("non_participants")
#let links = yaml("data/links.yaml").at("links")
#let submission = yaml("data/submission.yaml").at("submission")
#let tools = yaml("data/ai_usage.yaml").at("tools")
#let transcript-sections = yaml("data/transcript.yaml").at("transcript")
#let evidence-images = yaml("data/evidence.yaml").at("images")

#set document(
  title: submission.at("project_name"),
  author: "When2Meet SWP Team",
)

#align(center)[
  #text(size: 18pt, weight: "bold")[SWP Assignment 5]
  #v(0.4em)
  #text(size: 13pt)[#submission.at("project_name")]
  #v(0.3em)
  #text(size: 11pt)[Team number: #submission.at("team_number")]
  #v(0.2em)
  #text(size: 10pt)[MVP v2 — Sprint 3]
]

#v(1em)

= Team members

#{
  set text(size: 8.5pt, hyphenate: false)
  table(
    columns: (1.1fr, 2fr, 0.9fr, 1fr, 1.2fr),
    stroke: 0.5pt,
    inset: 5pt,
    table.header(
      [*Name*], [*University email*], [*GitHub*], [*Scrum role*], [*Tech responsibility*],
    ),
    ..for m in team {
      (
        [#m.at("name")],
        [#m.at("email")],
        [#link("https://github.com/" + m.at("github"))[#m.at("github")]],
        [#m.at("scrum_role")],
        [#m.at("tech_responsibility")],
      )
    },
  )
}

#v(0.8em)

== Sprint 3 contributions

#{
  set text(size: 8.5pt)
  table(
    columns: (1.1fr, 2.4fr),
    stroke: 0.5pt,
    inset: 5pt,
    table.header([*Name*], [*Contributions*]),
    ..for m in team {
      (
        [#m.at("name")],
        [#for c in m.at("contributions") [- #c #linebreak()]],
      )
    },
  )
}

#v(0.8em)

= Participation in Sprint Review / UAT recording

#for p in non-participants [
  - *#p.at("name"):* #p.at("note")
]

#pagebreak()

= Repository submission

*Commit hash (protected default branch):* `#submission.at("commit_hash")`

- Week 5 report index: #link(links.at("public").at("week5_readme"))[README.md permalink]
- Product tree at submission commit: #link(links.at("public").at("product_tree"))[monorepo/src/when2meet permalink]

= Private recordings and access

#table(
  columns: (4.5cm, 1fr),
  stroke: 0.5pt,
  inset: 6pt,
  [*Item*], [*Link / note*],
  [Sprint Review + customer UAT recording],
    [#link(links.at("private").at("sprint_review_uat_recording"))[Yandex Disk]],
  [Sprint Review discussion timecode], [#raw(links.at("private").at("uat_timecode_review"))],
  [Customer-executed UAT timecode], [#raw(links.at("private").at("uat_timecode_uat"))],
  [Public Sprint Review summary],
    [#link(links.at("public").at("sprint_review_summary"))[sprint-review-summary.md]],
  [Public Sprint Review transcript],
    [#link(links.at("public").at("sprint_review_transcript"))[sprint-review-transcript.md]],
  [Private access instructions], [#raw(links.at("private").at("private_access_instructions"))],
)

= Public product links

- Deployed product: #link(links.at("public").at("deployed_product"))[#raw(links.at("public").at("deployed_product"))]
- Public sanitized demo video: #link(links.at("public").at("demo_video"))[Yandex Disk]
- Sprint 3 milestone: #link(links.at("public").at("sprint_milestone"))[GitHub milestone]
- Product backlog: #link(links.at("public").at("product_backlog"))[GitHub Project view 19]
- Sprint backlog: #link(links.at("public").at("sprint_backlog"))[GitHub Project view 20]

= Latest protected-default-branch CI (submission commit)

- Tests: #link(links.at("public").at("ci_tests"))[GitHub Actions job]
- Secret scan: #link(links.at("public").at("ci_secret_scan"))[GitHub Actions job]
- Link check (Lychee): #link(links.at("public").at("ci_lychee"))[GitHub Actions job]

#pagebreak()

= Repository and CI evidence

#for item in evidence-images [
  #figure(
    image(item.at("file"), width: 100%),
    caption: [#item.at("caption")],
  )
  #v(0.8em)
]

#pagebreak()

= Sprint Review transcript (sanitized)

Source of truth in the repository:
#link(links.at("public").at("sprint_review_transcript"))[sprint-review-transcript.md]

#for section in transcript-sections [
  == #section.at("section")

  #for entry in section.at("entries") [
    #text(size: 9pt, fill: luma(100))[#entry.at("time")]

    *#entry.at("speaker"):* #entry.at("text")

    #v(0.4em)
  ]
]

#pagebreak()

= AI / LLM tools usage

#for t in tools [
  - #t
]
