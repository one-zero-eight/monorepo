#set page(paper: "a4", margin: (x: 2.5cm, y: 2cm))
#set par(leading: 0.65em, justify: true)
#set text(font: "New Computer Modern", size: 10.5pt)
#set heading(numbering: "1.")

#let team = yaml("data/team.yaml").at("team")
#let links = yaml("data/links.yaml").at("links")
#let submission = yaml("data/submission.yaml").at("submission")
#let tools = yaml("data/ai_usage.yaml").at("tools")
#let stories-data = yaml("data/user_stories.yaml")
#let stories = stories-data.at("stories")
#let mvp-scope = stories-data.at("mvp_v1_scope")
#let transcript-sections = yaml("data/transcript.yaml").at("transcript")
#let smoke = yaml("data/smoke_check.yaml").at("smoke_check")
#let evidence-images = yaml("data/evidence.yaml").at("images")

#let img-base = "../images"

#set document(
  title: submission.at("project_name"),
  author: "When2Meet SWP Team",
)

// ---- 1. Title & team ----

#align(center)[
  #text(size: 18pt, weight: "bold")[SWP Assignment 2]
  #v(0.4em)
  #text(size: 13pt)[#submission.at("project_name")]
  #v(0.3em)
  #text(size: 11pt)[Team number: #submission.at("team_number")]
]

#v(1em)

#text(weight: "bold")[Team members, roles, and Week 2 contributions]

#v(0.5em)

#{
  set text(size: 8.5pt)
  table(
    columns: (2.2cm, 2.8cm, 1.6cm, 1.6cm, 1.6cm, 1fr),
    stroke: 0.5pt,
    inset: 5pt,
    table.header(
      [*Name*],
      [*University email*],
      [*GitHub*],
      [*Scrum role*],
      [*Tech*],
      [*Contributions this week*],
    ),
    ..for m in team {
      (
        [#m.at("name")],
        [#m.at("email")],
        [#link("https://github.com/" + m.at("github"))[#m.at("github")]],
        [#m.at("scrum_role")],
        [#m.at("tech_responsibility")],
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

// ---- 2. Repository submission links ----

= Repository submission

*Commit hash (protected default branch):* `#submission.at("commit_hash")`

- Week 2 report index: #link(submission.at("readme_permalink"))[README.md permalink]
- Product tree at submission commit: #link(submission.at("tree_permalink"))[monorepo/src/when2meet permalink]
- License: #link(links.at("license"))[MIT License]

= Live artifact links

#table(
  columns: (3.5cm, 1fr),
  stroke: 0.5pt,
  inset: 6pt,
  [*Artifact*], [*URL*],
  [Figma prototype], [#link(links.at("figma"))[Figma — mobile mockup]],
  [MVP v0 frontend], [#link(links.at("mvp_frontend"))[pre.innohassle.ru/when-to-meet]],
  [MVP v0 demo video], [#link(links.at("mvp_video"))[Yandex Disk]],
  [OpenAPI spec], [#link(links.at("openapi_repo"))[openapi.yaml in repository]],
  [Postman collection], [#link(links.at("postman_repo"))[postman\_collection.json in repository]],
  [Postman workspace], [#link(links.at("postman_workspace"))[Public view-only workspace]],
  [Swagger UI (hosted)], [#link(links.at("swagger_hosted"))[api.innohassle.ru/when2meet/v0/docs]],
  [Swagger UI (local)], [#raw(links.at("swagger_local"))],
  [Lychee config], [#link(links.at("lychee_config"))[lychee.yaml]],
  [Latest Lychee run], [#link(links.at("lychee_latest_run"))[GitHub Actions run]],
)

= TA access — smoke check

== Hosted frontend

#for step in smoke.at("frontend") [
  - #step
]

== Hosted API

#for step in smoke.at("backend_hosted") [
  - #step
]

== Local API (optional)

#for step in smoke.at("backend_local") [
  - #step
]

*Test credentials:* #submission.at("test_credentials")

#pagebreak()

// ---- 3. User stories ----

= User stories and MVP v1 scope

*Initial proposed MVP v1 scope (Must Have):* #(mvp-scope.join(", "))

#table(
  columns: (1.4cm, 2.2cm, 1fr),
  stroke: 0.5pt,
  inset: 6pt,
  table.header([*ID*], [*MoSCoW*], [*Story*]),
  ..for s in stories {
    (
      [#s.at("id")],
      [#s.at("priority")],
      [#s.at("text")],
    )
  },
)

#pagebreak()

// ---- 4. Customer meeting ----

= Customer meeting recording

Private instructor sharing: permitted.

Recording: #link(links.at("recording"))[Yandex Disk]

Full sanitized transcript is also published in the repository:
#link(submission.at("tree_permalink") + "/reports/week2/customer-meeting-transcript.md")[customer-meeting-transcript.md]

= Customer meeting transcript (sanitized)

#for section in transcript-sections [
  == #section.at("section")

  #for entry in section.at("entries") [
    #text(size: 9pt, fill: luma(100))[#entry.at("time")]

    *#entry.at("speaker"):* #entry.at("text")

    #v(0.4em)
  ]
]

#pagebreak()

// ---- 5. MIT consent ----

= MIT-licensed public development model

#submission.at("mit_consent")

#pagebreak()

// ---- 6. Evidence screenshots ----

= Repository and deployment evidence

#for item in evidence-images [
  #figure(
    image(img-base + "/" + item.at("file"), width: 100%),
    caption: [#item.at("caption")],
  )
  #v(0.8em)
]

#pagebreak()

// ---- 7. AI / LLM usage ----

= AI / LLM tools usage

#for t in tools [
  - #t
]
