# Selected business evidence iteration

Goal: answer important behavior questions without uploading source repositories or adding local AI analysis.

1. Verify a small behavior note against the frozen public source used in the prior trial. Keep the source-to-note hashes and actual material private. Freeze the note before the new evaluation questions; previous recovery questions are regression-only.
2. Compare the same existing project briefing with and without that note, using two fresh Chat High conversations and no GitHub access. Preserve source scope, provenance, unknowns and failures. This tests the value of the note, not the new CLI.
3. If useful, extend the existing `slice` command with repeated `--include-document PROJECT:PATH` selectors. Select only document bodies already present in the validated manifest, never local filesystem paths. Include explicitly named projects' documents even when heuristic selection does not find them, in a separate evidence section without changing ranking; preserve permission boundaries. Reject unknown/denied/summary-only projects and missing documents; deduplicate and sort selection. Reuse existing document rendering, line numbering and redaction. Default output remains unchanged.
4. Keep the slice document budget bounded, reject excess rather than trimming away failure conditions, and report which document bodies were included or omitted. No source scans, new schema, new state system, remote access or automatic semantic extraction.
5. Verify default behavior, exact selection, privacy/redaction, missing and revoked permissions, budgets, CLI integration and output atomicity. Run the existing full suite and wheel build once after the logical batch. Run isolated installed CLI smoke if available; preserve any environment-specific build limitation.
6. Reproduce the reviewed experiment packet using the implemented CLI and compare content. Save both simple results and technical evidence. Update usage and workflow contracts; no commit/push or stable cloud overwrite.

This iteration does not automatically invalidate notes against the underlying source. Private digest mappings are checked in the experiment; general source-to-note freshness remains an explicit limitation. Review notes before export because behavior descriptions can themselves disclose business secrets.
