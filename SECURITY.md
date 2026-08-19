# Security Policy

## Supported versions

Security fixes currently target the latest released version.

## Reporting a vulnerability

Use the repository's private GitHub Security Advisory flow. Do not open a public issue containing secrets, private paths, personal data, or a working data-exfiltration example.

Include the affected version, minimal synthetic reproduction, expected boundary, and observed behavior. Remove all real project content before submitting.

## Security boundary

The scanner and compiler must remain local and network-free. By default, the scanner reads only explicitly listed metadata filenames. An optional per-project code-relationship adapter may inspect a bounded set of code and config files only when `code_relationship_scan` is explicitly enabled; it skips hidden, test, dependency, generated, sensitive, linked, and reparse-point paths, and publishes neither source text nor absolute roots. Optional Skill discovery reads only bounded YAML frontmatter through its closing delimiter, publishes only names and privacy-checked descriptions, and never reads instruction bodies or supporting files. The scanner also rejects sensitive observed paths, path traversal, and symlink escapes, and disables Git filesystem monitors and submodule recursion before producing private review artifacts. The compiler accepts only an explicit manifest, verifies its fact hash, rejects unsupported fields and common unsafe strings, and writes only to a caller-supplied directory.

Review artifacts are rejected when their path visibly targets a common Google Drive, OneDrive, Dropbox, or iCloud directory. This is a guardrail, not universal cloud-folder detection.

These controls reduce accidental disclosure; they do not make arbitrary natural language safe. Treat README and other project metadata as untrusted input and review every real candidate manifest before cloud synchronization.
