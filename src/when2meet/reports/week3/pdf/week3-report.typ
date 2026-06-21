#set page(paper: "a4", margin: (x: 2.5cm, y: 2cm))
#set par(leading: 0.65em, justify: true)
#set text(font: "New Computer Modern", size: 10.5pt)
#set heading(numbering: "1.")

#let team = yaml("data/team.yaml").at("team")
#let links = yaml("data/links.yaml").at("links")
#let submission = yaml("data/submission.yaml").at("submission")
#let tools = yaml("data/ai_usage.yaml").at("tools")
#let evidence-images = yaml("data/evidence.yaml").at("images")

#let img-base = "../images"

#set document(
  title: submission.at("project_name"),
  author: "When2Meet SWP Team",
)

#align(center)[
  #text(size: 18pt, weight: "bold")[SWP Assignment 3]
  #v(0.4em)
  #text(size: 13pt)[#submission.at("project_name")]
  #v(0.3em)
  #text(size: 11pt)[Team number: #submission.at("team_number")]
]

#v(1em)

#text(weight: "bold")[Team members]

#v(0.5em)

#{
  set text(size: 9pt, hyphenate: false)
  set par(justify: false)
  table(
    columns: (3.2cm, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    table.header(
      [*Name*],
      [*University email*],
    ),
    ..for m in team {
      (
        [#m.at("name")],
        [#raw(m.at("email"))],
      )
    },
  )
}

#v(1em)

#text(weight: "bold")[Scrum roles and technical focus]

#v(0.5em)

#{
  set text(size: 9pt, hyphenate: false)
  set par(justify: false)
  table(
    columns: (3cm, 3.4cm, 2.4cm, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    table.header(
      [*Name*],
      [*GitHub*],
      [*Scrum role*],
      [*Tech*],
    ),
    ..for m in team {
      (
        [#m.at("name")],
        [#link("https://github.com/" + m.at("github"))[#m.at("github")]],
        [#m.at("scrum_role")],
        [#m.at("tech_responsibility")],
      )
    },
  )
}

#v(1em)

#text(weight: "bold")[Week 3 contributions]

#v(0.5em)

#{
  set text(size: 9pt, hyphenate: false)
  set par(justify: false)
  table(
    columns: (3.2cm, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    table.header(
      [*Name*],
      [*Contributions this week*],
    ),
    ..for m in team {
      (
        [#m.at("name")],
        [
          #for c in m.at("contributions") [
            - #c
          ]
        ],
      )
    },
  )
}

#pagebreak()

= Repository submission

*Commit hash (protected default branch):* #raw(submission.at("commit_hash"))

- Week 3 report index: #link(submission.at("readme_permalink"))[README.md permalink]
- Product tree at submission commit: #link(submission.at("tree_permalink"))[monorepo/src/when2meet permalink]
- License: #link(links.at("license"))[MIT License]

= Live artifact links

#table(
  columns: (3.8cm, 1fr),
  stroke: 0.5pt,
  inset: 6pt,
  [*Artifact*], [*URL*],
  [Product Backlog board], [#link(links.at("product_backlog"))[GitHub Project \#4]],
  [Sprint 1 milestone], [#link(links.at("sprint_milestone"))[milestone/1]],
  [MVP v1 release], [#link(links.at("release"))[when2meet-v1.0.0]],
  [MVP v1 frontend], [#link(links.at("mvp_frontend"))[pre.innohassle.ru/when2meet]],
  [Demo video], [#link(links.at("mvp_video"))[Yandex Disk]],
  [User-story index], [#link(links.at("user_stories"))[docs/user-stories.md]],
  [Roadmap], [#link(links.at("roadmap"))[docs/roadmap.md]],
  [Definition of Done], [#link(links.at("definition_of_done"))[docs/definition-of-done.md]],
  [Changelog], [#link(links.at("changelog"))[CHANGELOG.md]],
  [Reviewed PR (website)], [#link(links.at("pr_309"))[PR \#309]],
  [Reviewed PR (monorepo)], [#link(links.at("pr_70"))[PR \#70]],
)

*Product Backlog size:* #submission.at("backlog_story_points") story points.

*Sprint 1 size:* #submission.at("sprint_story_points") story points completed.

*Test credentials:* #submission.at("test_credentials")

#pagebreak()

= Customer Sprint Review

Private instructor sharing: permitted.

Recording: #link(links.at("recording"))[Yandex Disk]

Repository transcript: #link(submission.at("tree_permalink") + "/reports/week3/customer-review-transcript.md")[customer-review-transcript.md]

== Summary

The customer reviewed the MVP v1 increment on 20 June 2026. Core flows (create meeting, availability grid, heatmap) were demonstrated. Full acceptance was not granted. Requested changes: clarify ``Specific time'' UX; replace manual participants with SSO-linked profiles; replace ``Best time'' purple gradient with a maximum-intersection filter. See #link(submission.at("tree_permalink") + "/reports/week3/customer-review-summary.md")[customer-review-summary.md] for action points and backlog updates.

#pagebreak()

= MIT-licensed public development model

#submission.at("mit_consent")

#pagebreak()

= Evidence screenshots

#for item in evidence-images [
  #figure(
    image(img-base + "/" + item.at("file"), width: 100%),
    caption: [#item.at("caption")],
  )
  #v(0.8em)
]

#pagebreak()

= AI / LLM tools usage

#for t in tools [
  - #t
]
