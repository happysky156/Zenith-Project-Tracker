# AI Project Assistant Management Polish Update

This update is a small refinement on top of the Management Relevance version.

## Purpose

Improve answer wording without changing business logic, database writes, or module page behaviour.

## Changes

- Keep strong relevance filtering and read-only join expansion unchanged.
- Improve prompt wording so Direct Answer prioritises blocked point, risk/impact, and next step.
- Rename the answer section from "Missing or Not Found" to "Information Gaps in Current System Records".
- Make project-index wording more precise:
  - Use "No project-linked Index Snapshot or Index Center records were found" for project questions.
  - Avoid implying the whole Index Center is empty.
- Make Order Details handling safer for multiple item rows:
  - Extension rows are no longer deduplicated only by Project ID / Order No.
  - Multiple Order Details item lines under the same order can remain in final evidence.
  - The prompt tells the AI to summarise item count and not imply only one item unless only one row exists.
- Add deterministic wording polish for common AI phrasing without adding any business facts.

## Safety

No database write logic was changed. AI Project Assistant remains read-only and can only answer based on system records.
