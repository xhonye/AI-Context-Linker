# Script layouts, custom documents, and monorepo projects

These options are local configuration. They do not execute source files, call a
model, upload anything, or approve a candidate snapshot.

## Flat Python scripts

If `scripts/check_engine.py` imports its sibling `tickmarks.py` by bare name,
declare the directory that your application puts on Python's import path:

```json
{
  "architecture_visibility": "modules-symbols",
  "python_import_roots": ["scripts"]
}
```

`python_import_roots` defaults to empty. Each entry must name an existing,
project-relative directory, with no parent traversal or links; at most 16 unique
entries are accepted. `.` names the project root. These are resolution hints over
already indexed files, not extra scan roots, and do not bypass excluded trees or
read limits. Existing package and `src`/`lib`/`app` layouts remain supported.

Without a declared root, a possible sibling is listed in `unresolved_imports`
with reason `local-import-root-not-declared`, rather than called a third-party
package. Multiple matching module identities produce `ambiguous-local-module`;
the compiler does not guess search-path precedence. Supply roots that describe
the intended application environment and review any remaining ambiguity. Static
resolution cannot prove runtime behavior under arbitrary `sys.path` mutations,
import hooks, or conditional imports.

UTF-8 source files with and without a BOM are supported. Failed files appear in
`parse_errors` in the scan report, manifest, full project briefing, and architecture
slice. Only project-relative identities and `syntax-error`, `encoding-error`, or
`read-error` are recorded; source snippets and exception messages are omitted.
Legacy manifests containing only `parse_failures` remain readable.

## Explicit custom Markdown evidence

Select each nonstandard document in **both** lists:

```json
{
  "allow_files": ["README.md", "SKILL.md", "docs/glossary.md"],
  "attach_files": ["SKILL.md", "docs/glossary.md"]
}
```

The default metadata allowlist and empty attachment list are unchanged. Custom
documents require `cloud_visibility: allow`, normalized project-relative `.md`
paths, and explicit attachment selection. Source files, hidden/sensitive paths,
parent traversal, links, missing files, and over-limit documents are rejected.
The existing limits remain eight documents, 64 KiB each, and 256 KiB per project.
Review the original content and the redacted candidate before sharing: size
limits and redaction cannot determine whether all business information is safe.

Custom documents travel as line-numbered, untrusted evidence. They do not become
approved action state or automatically derived instructions/relationships.
The separate Skill-root adapter still requires approved neutral summaries and
does not automatically publish raw Skill descriptions. Full briefings include
selected attachments; question slices require explicit `--include-document`
selection, as before.

## A subproject inside a monorepo

Keep the skill's documents and architecture scoped to the skill directory.
Declare a **separate, explicitly allowed project** for repository-level dependency
metadata. The following is a `projects` array inside a normal workspace config;
paths are relative to that config file:

```json
[
  {
    "id": "repository",
    "path": "./monorepo",
    "summary": "Repository-level dependency declarations; not every child uses every dependency.",
    "sensitivity": "internal",
    "cloud_visibility": "allow",
    "redaction_profile": "standard",
    "allow_files": [],
    "dependency_files": ["pyproject.toml"],
    "architecture_visibility": "disabled"
  },
  {
    "id": "skill",
    "path": "./monorepo/skills/sample",
    "sensitivity": "internal",
    "cloud_visibility": "allow",
    "redaction_profile": "standard",
    "allow_files": ["SKILL.md"],
    "attach_files": ["SKILL.md"],
    "architecture_visibility": "modules-only",
    "python_import_roots": ["scripts"]
  }
]
```

Only include `python_import_roots` when that directory exists and is an intended
import root. Repository-level dependency-derived relationships belong to
`repository`, not to `skill`. The current dependency adapter derives relationships
to uniquely identified projects in the workspace; it does not export a complete
third-party dependency inventory. Review the root project's ordinary Git and
filename-inventory signals too: this is an explicitly allowed project, not a
dependency-only sandbox. Source parsing and document attachments remain disabled
for the repository entry above.

`dependency_files` remains limited to supported manifests in each declared
project root. `../pyproject.toml` is deliberately rejected. Reading an ancestor
inside the same Git repository is still a larger information boundary and does
not prove that its dependencies belong to a child. A future dependency-only
shared-root adapter needs a separate scoped design; this recipe does not claim
that feature has been implemented.
