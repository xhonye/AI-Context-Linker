# High-value evidence with private repositories

Status: selected-document delivery implemented in 0.2.5 after an exploratory High Chat comparison on 2026-09-08. A reviewed behavior note improved detail coverage without GitHub access in either conversation. This is one same-operation-family experiment, not independent generalization or replacement acceptance. No export permission is expanded.

## Observed difference

Two context packages and direct access to a pinned public repository answered the same overview, lifecycle and data-recovery questions in three fresh ordinary Chat conversations at High effort. Both packages answered the shared rules and correctly stopped at an undocumented failure path. The direct-repository conversation retrieved the implementation and explained its recovery sequence and remaining limits. It took longer and its final answer lacked convenient per-claim source links. This is a depth gain on one selected public project, not general superiority on private or cross-project questions.

## Product implication

A short overview should orient the conversation and identify missing evidence. The useful lesson is access to relevant behavior evidence, not GitHub hosting itself. Private projects should work without uploading their repositories. Only explicitly approved, minimized material may enter Chat context. An already-public repository is an optional comparison source, never a prerequisite.

Prefer a few concrete statements about inputs, outcomes, failure handling, recovery, data ownership and current blockers over additional module lists, Git activity or repeated governance text. Local code structure summaries cannot establish implementation behavior, and a project-relative path alone is not a cloud-readable source.

Do not turn the compiler into another repository host, retrieval server or local reasoning service on this evidence. Existing slices and metadata attachments remain useful; first measure whether their combination with direct source access helps.

## High-value content to retain

- User-visible behavior: trigger, preconditions, success, failure, cancellation/undo and consequential limits. A restore description needs its failure path, not just the statement that backups exist.
- Current approved state: goal, blocker, next action, owner decision, observation time and expiry. Existing review/session-state adapters already serve this family; do not add a second state system.
- Evidence grade: documented contract, implementation inspected, test source inspected, test actually passed, or real-use acceptance. Include version/freshness and unresolved gaps without promoting one grade into another.
- Data and dependency boundaries: who owns the fact, which component consumes it, what is shared, and what is deliberately not synchronized. Publish only the granularity permitted for the project.

An engineering agent can prepare these notes while making a change and checking code/tests, using authorized access. This does not mean deploying a local AI model or making Linker a reasoning engine. Treat the notes as reviewable interpretations until checked; keep raw source out of the onward Chat package. Using a cloud engineering agent is not a promise that all processing occurs on-device.

## Smallest next test

Use the same frozen source baseline to prepare a small, reviewed behavior note for a few selected operations. Keep the actual private source-to-note mapping outside the repository and cloud directory. A permitted nested metadata file such as `docs/chat-context/README.md` can use existing `allow_files` plus `attach_files`; the filename does not confer approval and real private notes must not be committed to a public repository.

Compare the original briefing against that briefing plus the reviewed note, with no GitHub access in either Chat. Write the note from the selected operations and their failures before choosing new held-out questions. Use the earlier failing question only as a labeled regression. Measure useful correct details per supplied text length, missing facts, unsupported claims, source-review cost and disclosure scope. Do not claim a win merely for inserting the answer to a known test question.

The original slice omitted all attached document bodies. The manually assembled comparison favored adding a short reviewed note. Version 0.2.5 therefore adds repeated `--include-document PROJECT:PATH` selectors using the existing renderer and allowed attachments. Default output and heuristic ranking remain unchanged. Explicit documents are rendered separately even when their project was not chosen by the question heuristic; no source files are opened. The selection is bounded to eight documents and 256 KiB of body text and fails instead of truncating. The experiment demonstrates the usefulness of supplied evidence, not compiler-generated semantics.

Current fact hashes bind the attached note text, not every source file that justified it. For the first experiment, retain a private source-file digest mapping and re-review notes when those files change. Automatic source-to-note freshness is a proposed follow-up, not an existing guarantee.

When a question needs missing evidence, Chat should return a short question or evidence identifier. An authorized local engineering step then prepares a minimal addition for review. Chat must not request arbitrary filesystem paths or execute commands through Linker. If the approved note set is already in the designated cloud folder, Chat can search that set; it cannot thereby inspect local originals.

## Privacy limits

Start with selected content, not whole-source upload followed by attempted scrubbing. Generalize identities, exact paths, internal endpoints and examples only where the remaining behavior is permitted to share. Keep the private reverse mapping local. A behavior summary can itself disclose proprietary rules or plans; replacement of names does not make it safe by definition. Existing deny/summary-only boundaries still apply, and omitted sensitive behavior remains unknown to Chat.

Regex checks help catch known secrets and paths but cannot reliably classify business secrets. Review the complete outgoing packet, including filenames, source references and combinations of facts. The experiment uploaded only the reviewed briefing and behavior note derived from the already-public frozen baseline; no repository archive, raw source, logs, database or transcript was supplied to either test Chat. Never derive cloud publication permission from a Git remote, and do not describe a private cloud folder as local-only storage.

Public reports use anonymized aggregates. Raw prompts, source snapshots, answers, timings and identity mappings remain in private evaluation storage.
