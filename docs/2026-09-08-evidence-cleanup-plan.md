# Evidence cleanup after private question testing

## Scope

1. Keep the user's original screenshots in private storage and draft an anonymous presentation plan; no public assets or uploads in this iteration.
2. Remove redundant excerpt extraction from documents already attached in full. Preserve explicit configured prose and metadata-only behavior.
3. Use one constraint label across cards, full context and question slices so configured records cannot become confirmed facts in shorter output.
4. Clean verified obsolete prose in a new private configuration, preserving the original comparison snapshots and permission selections.
5. Test refresh-to-render behavior, retained configuration, and safe handling of changed document bodies; build a local patch release and inspect a real refreshed candidate.

No automatic semantic conflict resolution, new inference engine, model calls, business-project changes, or Git publication. A successful refresh is engineering evidence, not a new online answer comparison.

## Result

Implemented as local version 0.2.4. All 416 tests passed in the frozen source copy, with no skips; both existing gold suites and synthetic scan/build/slice checks passed. A cross-test-file import exposed by isolated pytest collection was removed by making the attachment fixture self-contained.

The wheel built successfully. The host interpreter lacks the standard-library `venv` module, so the standard candidate runner stopped at environment creation. Offline `uv --target` installation followed by `python -I -S` verified installed-package origin, synthetic scan/build/slice, and byte-identical full briefing output from the same real manifest. The original runner failure remains in the private logs; it was not reclassified as a pass.

The real refreshed candidate retains all 51 selected documents with unchanged visibility and attachment permissions, includes observed document updates, and removes verified stale copied prose through a new private configuration. Historical snapshots remain unchanged. Screenshots and the anonymization plan remain private and unpublished; no original screenshot is ready for public use.
