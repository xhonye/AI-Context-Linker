# Security Policy

## Supported versions

Security fixes currently target the latest released version.

## Reporting a vulnerability

Use the repository's private GitHub Security Advisory flow. Do not open a public issue containing secrets, private paths, personal data, or a working data-exfiltration example.

Include the affected version, minimal synthetic reproduction, expected boundary, and observed behavior. Remove all real project content before submitting.

## Security boundary

The scanner and compiler must remain local and network-free. Newly discovered projects default to `deny` and are not eligible for collection until the user explicitly sets sensitivity, cloud visibility, and a redaction profile; `summary-only` additionally requires an approved summary, while denied projects and their relationships never enter publishable artifacts. An optional per-project code-relationship adapter may inspect a bounded set of code and config files only when `code_relationship_scan` is explicitly enabled; it skips hidden, test, dependency, generated, sensitive, linked, and reparse-point paths, and publishes neither source text nor absolute roots. Optional Skill discovery reads only bounded YAML frontmatter through its closing delimiter, publishes names plus explicitly approved neutral summaries, audits but never publishes raw descriptions, and never reads instruction bodies or supporting files. Private review-state and relationship-candidate inputs are bounded, explicit JSON files; AI relationship candidates go only to a private review queue and never enter the formal graph automatically. The scanner also rejects sensitive observed paths, prompt-like Skill metadata, path traversal, and symlink escapes, and disables Git filesystem monitors and submodule recursion before producing private review artifacts. The compiler accepts only an explicit manifest, verifies its fact hash, excludes AI-candidate relationships from default output, rejects unsupported fields and common unsafe strings, and writes only to a caller-supplied directory.

Review artifacts are rejected when their path visibly targets a common Google Drive, OneDrive, Dropbox, or iCloud directory. This is a guardrail, not universal cloud-folder detection.

Approved snapshot history must remain outside cloud-synced directories. A scan never approves its own output; use the separate approval command only after reviewing the candidate manifest, semantic changes, and relationship queue.

These controls reduce accidental disclosure; they do not make arbitrary natural language safe. Treat README and other project metadata as untrusted input and review every real candidate manifest before cloud synchronization.
