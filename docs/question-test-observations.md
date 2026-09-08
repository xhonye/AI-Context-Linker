# Anonymized question-test observations

AI Context Linker prepares reviewable evidence for an online conversation. These
maintainer observations explain why selected documents and behavior notes were
added. They are not an independent benchmark, a privacy certification or proof
that Linker can replace another tool for every task.

## What the experiments changed

1. In an early comparison, missing business documents caused an answer to suggest
   rebuilding an existing capability. Different project coverage prevented a fair
   ranking by project count. Historical records also needed clearer labeling.
2. After both packages carried the selected business documents, the core answers
   became comparable. Explicit references helped expose stale configured prose.
   One initially negative evidence assessment was corrected after inspecting the
   original frozen documents. Only the corrected result card is included here.
3. A later comparison with access to a pinned public repository explained a
   failure path absent from the briefings. This demonstrated the value of relevant
   evidence, not a need to publish private repositories.
4. The next pair compared the same briefing with and without a small reviewed
   behavior note. Neither conversation received repository source. Input grew
   from 40,675 to 44,514 UTF-8 bytes (+3,839 bytes, 9.44%). The enhanced answer
   covered more previously missing failure/recovery and state-transition details.

## How to interpret the latest pair

- Two fresh ordinary Chat conversations received the same question body and one
  overview plus two detail questions. Neutral A/B names hid the assignment, but
  the extra note and formatting were visible, so concealment was incomplete.
- Both menus showed Latest and High effort before sending. Exact backend model
  identity was unavailable. Account personalization was not audited or disabled.
- Both uploaded files were read back and matched the reviewed local packets.
  Returned fact hashes identified the intended snapshots.
- An engineering agent checked the note against a frozen, already-public source
  before selecting this round's questions. These were new questions in the same
  operation family, not an independent held-out generalization benchmark.
- Evaluation used a manually assembled packet. The installed CLI subsequently
  preserved every selected document line; wrapper wording and placement differ.
  The smaller note-only output has not received its own online comparison.
- More evidence helped this pair; it does not establish repeatable speed gains,
  broad model superiority, business runtime acceptance or full baseline parity.

## Privacy and product boundary

The public cards are AI-redrawn anonymized interpretations of earlier results,
not edited evidence screenshots. Original screenshots, prompts, answers, real
manifests, identities and source-to-note mappings remain outside this repository.
This page publishes only reviewed aggregate observations.

Private projects do not need to move to GitHub. Start with explicitly selected,
permitted material. A behavior note may itself reveal business secrets; removing
names or passing a pattern scan is insufficient. Source changes require renewed
note review: the compiler hashes attached text but does not certify its meaning
or automatically invalidate it against underlying implementation changes.

The compiler has no automatic network upload or local-model analysis. Use the
[synthetic behavior-note template](../examples/behavior-note/README.md) and the
[document selection workflow](../README.md#include-documents-for-offline-follow-up).
