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

No extra project entry or dependency-root setting is needed. For a project with
`cloud_visibility: allow`, the scanner automatically looks for supported dependency
manifests in its ancestor directories, stopping at the nearest Git repository
boundary. This also works when discovery generated an empty `dependency_files`
list for a child directory. Source and document scans stay inside the child.

For example, with this layout:

```text
repository/.git
repository/pyproject.toml
repository/skills/sample/SKILL.md
```

An allowed project rooted at `repository/skills/sample` includes the parsed package
names from `pyproject.toml` in its candidate and full briefing, labeled
**repository-shared declarations; child usage unknown**, with repository-relative
provenance. These declarations do not create child dependency edges or make the
child inherit the repository package identity. Review and approval still happen
before publishing. Package versions, URLs, scripts and raw file bodies are not
exported; declarations are not a complete installed-environment inventory.

Discovery reads at most the nearest ancestor file of each supported name:
`pyproject.toml`, `package.json`, `Cargo.toml`, and `go.mod`, each capped at 128 KiB.
It searches at most 32 ancestors and never goes above a nested repository or
worktree root. A nearer invalid file is reported as unavailable rather than
silently replaced with a more distant file. Unsupported declaration styles are
not inferred. Names omitted by safety or size limits are explicitly noted.

Denied and summary-only projects are not scanned. Explicitly denied/summary-only
ancestor roots, links/reparse points and hidden ancestor paths are not read.
Directories outside Git do not get ancestor discovery. To opt out, set
`discover_shared_dependencies: false`; ordinary use needs no new setting.

`dependency_files` still controls local-root metadata used for direct relationship
derivation. When omitted, supported filenames are detected locally; an explicit
empty list disables that local adapter. It does not disable shared discovery.
Explicit `../pyproject.toml` paths remain rejected: automatic discovery is limited
to the bounded ancestor-manifest surface, not arbitrary parent-file access.
