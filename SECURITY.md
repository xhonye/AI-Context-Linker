# Security Policy

## Supported versions

Security fixes currently target the latest released version.

## Reporting a vulnerability

Use the repository's private GitHub Security Advisory flow. Do not open a public issue containing secrets, private paths, personal data, or a working data-exfiltration example.

Include the affected version, minimal synthetic reproduction, expected boundary, and observed behavior. Remove all real project content before submitting.

## Security boundary

The core compiler must remain local and network-free. It accepts only an explicit manifest, rejects unsupported fields and common unsafe strings, and writes only to a caller-supplied directory. These controls reduce accidental disclosure but do not replace human review of a real manifest before cloud synchronization.
