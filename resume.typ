#let data-file = sys.inputs.at("data", default: "data.json")
#let data = json(data-file)

#set document(
  author: data.first_name + " " + data.last_name,
  title: data.first_name + " " + data.last_name + " - Resume",
)

#set page(
  paper: "us-letter",
  margin: (x: 0.4in, top: 0.4in, bottom: 0.4in),
)

#set text(
  font: "New Computer Modern",
  size: 9.8pt,
)

#set par(
  justify: true,
  leading: 0.48em,
)

#set list(
  marker: [•],
  spacing: 3.2pt,
  tight: true,
)

// Section header with full-width rule
#let resume-section(title) = {
  v(5pt)
  text(size: 10.5pt, weight: "bold", upper(title))
  v(-7pt)
  line(length: 100%, stroke: 0.5pt)
  v(1pt)
}

// Subheading row with left/right alignment
#let resume-entry(left-top, right-top, left-bottom, right-bottom) = {
  block(width: 100%, breakable: false)[
    #grid(
      columns: (1fr, auto),
      align: (left, right),
      [*#left-top*], [#right-top],
      [#if left-bottom != "" { emph(left-bottom) }], [#if right-bottom != "" { emph(right-bottom) }],
    )
  ]
}

// ---------------- HEADER ----------------
#align(center)[
  #text(size: 17pt, weight: "bold")[#data.first_name #data.last_name] \
  #v(-5pt)
  #if "location" in data and data.location != "" [
    #text(size: 9.5pt)[#data.location] \
    #v(-5pt)
  ]
  #text(size: 9.5pt)[
    #if "phone" in data and data.phone != "" [ #data.phone ]
    #if "email" in data and data.email != "" [
      #text(fill: luma(120))[|] #link("mailto:" + data.email)[#data.email]
    ]
    #if "linkedin" in data and data.linkedin != "" [
      #text(fill: luma(120))[|] #link("https://" + data.linkedin)[#data.linkedin]
    ]
    #if "github" in data and data.github != "" [
      #text(fill: luma(120))[|] #link("https://" + data.github)[#data.github]
    ]
  ]
]

#v(-4pt)

// ---------------- EDUCATION ----------------
#if "education" in data and data.education.len() > 0 [
  #resume-section("Education")
  #for edu in data.education [
    #resume-entry(
      edu.institution,
      edu.dates,
      edu.degree,
      edu.at("location", default: ""),
    )
    #if "details" in edu [
      #v(-2pt)
      #list(..edu.details)
    ]
    #v(2pt)
  ]
]

// ---------------- EXPERIENCE ----------------
#if "experience" in data and data.experience.len() > 0 [
  #resume-section("Experience")
  #for exp in data.experience [
    #resume-entry(
      exp.organization,
      exp.dates,
      exp.title,
      exp.at("location", default: ""),
    )
    #if "bullets" in exp [
      #v(-2pt)
      #list(..exp.bullets)
    ]
    #v(2pt)
  ]
]

// ---------------- PROJECTS ----------------
#if "projects" in data and data.projects.len() > 0 [
  #resume-section("Projects")
  #for proj in data.projects [
    #resume-entry(
      proj.name,
      proj.dates,
      proj.at("type", default: ""),
      "",
    )
    #if "bullets" in proj [
      #v(-2pt)
      #list(..proj.bullets)
    ]
    #v(2pt)
  ]
]

// ---------------- TECHNICAL SKILLS ----------------
#if "skills" in data [
  #resume-section("Technical Skills")
  #v(-1pt)
  #if type(data.skills) == dictionary [
    #grid(
      columns: 1,
      row-gutter: 3.5pt,
      ..data.skills.pairs().map(pair => [
        *#pair.at(0):* #if type(pair.at(1)) == array { pair.at(1).join(", ") } else { str(pair.at(1)) }
      ])
    )
  ] else if type(data.skills) == array [
    #data.skills.join(", ")
  ]
]
