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
  #text(size: 18pt, weight: "bold")[SWP Assignment 6 — Week 6]
  #v(0.4em)
  #text(size: 13pt)[#submission.at("project_name")]
  #v(0.3em)
  #text(size: 11pt)[Team number: #submission.at("team_number")]
  #v(0.2em)
  #text(size: 10pt)[Week 6 Trial Release — Sprint 4]
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

== Sprint 4 contributions

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

All listed team members participated in Sprint 4 product, documentation, reporting, or presentation work. Nobody was inactive for the whole Sprint.

#pagebreak()

= Repository submission

Public report links use the protected default branch (`main`). Commit-hash permalinks are intentionally omitted from this submission pack.

- Week 6 report index: #link(submission.at("readme_link"))[README.md]
- Product tree: #link(submission.at("tree_link"))[monorepo/src/when2meet]

= Private recordings, presentation, and access

#table(
  columns: (4.5cm, 1fr),
  stroke: 0.5pt,
  inset: 6pt,
  [*Item*], [*Link / note*],
  [Sprint Review + transition + UAT recording],
    [#raw(links.at("private").at("sprint_review_uat_recording"))],
  [Sprint 4 demonstration timecode], [#raw(links.at("private").at("uat_timecode_review"))],
  [Transition / docs / UAT confirmation timecode], [#raw(links.at("private").at("uat_timecode_transition"))],
  [Rehearsed presentation video (standing)],
    [#link(links.at("private").at("rehearsed_presentation_video"))[Yandex Disk]],
  [Rehearsed demo (presentation)],
    [#link(links.at("public").at("rehearsed_demo"))[Yandex Disk]],
  [Slide deck PDF], [Submitted on Moodle only — When2Meet-presentation-v0-11.pdf (not committed to the public repository)],
  [Public Sprint Review summary],
    [#link(links.at("public").at("sprint_review_summary"))[sprint-review-summary.md]],
  [Public Sprint Review transcript],
    [#link(links.at("public").at("sprint_review_transcript"))[sprint-review-transcript.md]],
  [Private access instructions], [#raw(links.at("private").at("private_access_instructions"))],
)

= Public product links

- Deployed product: #link(links.at("public").at("deployed_product"))[#raw(links.at("public").at("deployed_product"))]
- Hosted documentation: #link(links.at("public").at("hosted_docs"))[#raw(links.at("public").at("hosted_docs"))]
- Customer handover: #link(links.at("public").at("customer_handover"))[customer-handover.md]
- Changelog / trial release: #link(links.at("public").at("changelog"))[CHANGELOG.md]
- Sprint 4 milestone: #link(links.at("public").at("sprint_milestone"))[GitHub milestone]
- Product backlog: #link(links.at("public").at("product_backlog"))[GitHub Project view 19]
- Sprint backlog: #link(links.at("public").at("sprint_backlog"))[GitHub Project view 20]

= Customer documentation and UAT (Week 6)

- Customer reviewed `README.md` and `docs/customer-handover.md` and confirmed they match her expectations.
- Team executed UAT scenarios from `docs/user-acceptance-tests.md`; customer stated the service works as expected.
- Handover level: Ready for independent use. Customer-confirmation status: Accepted.

= Latest protected-default-branch CI

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
