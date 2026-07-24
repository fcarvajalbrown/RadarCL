# Writing release notes

How a RadarCL release gets its text. Read this before writing any of it.
The build and publish commands live in the Releases section of
[CLAUDE.md](../CLAUDE.md); this file covers only the writing.

## One source, copied

[CHANGELOG.md](../CHANGELOG.md) is the source. A version's section in that
file **is** the release notes, verbatim. Write it once, in the changelog,
then paste that section into the GitHub Release.

Never maintain a separate narrative for the Release page. Two documents
holding the same content drift apart, and the one nobody looks at is the
one that ends up lying.

## Process, in this order

1. **Invoke the `voz-de-felipe` skill.** Actually invoke it. Writing "in
   his style" from memory is what produces the generic draft this file
   exists to prevent.
2. **Write the entry** into CHANGELOG.md using the template below.
3. **Run the humanizer pass** from the global CLAUDE.md, the AI-tell
   checklist, over the finished draft.
4. **Show it to Felipe** before publishing. Do not pipe an unreviewed
   draft into `gh release create`.

## Structure: two layers, two readers

This comes out of how the practice actually converged (Keep a Changelog,
Common Changelog, and the release-notes guidance surveyed 2026-07-24):
notes have to serve someone skimming for "should I upgrade" and someone
looking for one specific fix. Do not pick one. Layer them.

**Layer 1, the opening paragraph.** Two to four sentences, in Felipe's
voice, entering through something concrete. This is the layer a human
reads. It answers: what changed, and why does it matter to me?

**Layer 2, the categorised lists.** Flat, factual, verb-first, one change
per line. No voice, no rhetoric. This is the layer someone scans looking
for their bug.

Do not put voice into layer 2 and do not put a bullet list into layer 1.
Mixing them is what makes release notes read as either a corporate
changelog or a blog post, and neither is useful.

## Template

```markdown
## [X.Y.Z] - AAAA-MM-DD

<Layer 1. Dos a cuatro frases. Abre por lo concreto: el error que se vio,
el comando que ahora existe, la cifra que cambió. No abre por la versión
ni por el módulo. Cierra corto.>

### Añadido
- <Qué se puede hacer ahora que antes no. Enlaza el ADR si la decisión
  detrás es discutible.>

### Cambiado
- <Qué se comporta distinto. Si rompe algo, di exactamente qué hay que
  hacer para migrar.>

### Corregido
- <Qué estaba mal y qué se ve ahora. El síntoma primero, la causa
  después.>

### Eliminado
- <Qué ya no está.>
```

Categories come from Keep a Changelog. Use only the ones that apply: a
release that fixes three things has one heading, not four. Never invent an
empty category to look complete.

Order the categories by what a user notices first, not by layer of the
codebase and not by commit order. A change to the graphical interface
outranks a refactor of the crawler every time.

## Rules

Release notes go out under Felipe's name on a public repository, so they
are **not** exempt from the writing rules the way ADRs, specs and this
file are.

- **Spanish.** Version numbers, flag names, file paths, ADR filenames and
  code identifiers stay as they are.
- **No em dash (raya) anywhere.** It is the number-one AI tell and Felipe
  never uses it. Commas, parentheses, or a new sentence.
- **No emojis.** Including in headings.
- **Never close on an open rhetorical question.** Tell number two. Close
  declaratively.
- **Vary sentence length** in layer 1. Long clauses landing on a short
  blunt line. Uniform rhythm reads as generated.
- **Concrete over abstract.** Name the file, the flag, the number, the
  ADR. "Mejoras de rendimiento y estabilidad" is not a release note.
- **Banned vocabulary:** robusto, integral, sin fisuras, vanguardia,
  holístico, agilizar, empoderar, en constante evolución. Banned openers:
  "Es importante destacar que", "Cabe mencionar", "En el panorama
  actual". Banned closer: "En resumen" / "En conclusión".
- **Never invent.** No performance claims, no adoption numbers, no
  quotes. A number that was not measured does not go in. Dates come from
  `git log`, not from memory.
- **No commit log.** GitHub already links the diff. If a commit message is
  the best available description of a change, that change was too small
  to list.
- **Link the ADR for anything counterintuitive.** The 0.3.5 entry links
  ADR-0010 because a CSV and a JSON of the same run having different row
  counts looks like a bug until you read why.
- **State the caveats.** The executable is unsigned, so SmartScreen warns,
  and PyInstaller builds trip antivirus heuristics. Saying so costs
  nothing and prevents an issue being filed.

## Breaking changes

A breaking change is not a bullet. It gets its own paragraph under
`### Cambiado`, saying what breaks, and the exact steps to migrate. This
is the one case where length is not a problem. RadarCL is pre-1.0, so a
0.1 bump can carry one; say so plainly rather than relying on the version
number to communicate it.

## Discoverability

Release pages are indexed, and they are the freshness signal a search
engine reads as "this project is alive". Two things follow, both confirmed
in the 2026-07-24 survey:

- **Front-load the real words** into layer 1. What the tool does and what
  changed, in the first two sentences, not below the lists. This is the
  same principle as the repository description in the global CLAUDE.md.
- **Link the release from somewhere.** Changelog entries rank badly
  because nothing points at them except the changelog index, so search
  engines treat them as orphans. The README links to CHANGELOG.md; keep
  that link, and keep the changelog linked from the release.

## Sources

Surveyed 2026-07-24 rather than assumed:

- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [Common Changelog](https://github.com/vweevers/common-changelog)
- [Semantic Versioning](https://semver.org/)
- [How to write excellent release notes (Aha!)](https://www.aha.io/roadmapping/guide/launch/how-to-write-excellent-release-notes)
- [Changelog SEO (ReleasePad)](https://www.releasepad.io/blog/changelog-seo-how-to-make-your-release-notes-rank-in-google/)
