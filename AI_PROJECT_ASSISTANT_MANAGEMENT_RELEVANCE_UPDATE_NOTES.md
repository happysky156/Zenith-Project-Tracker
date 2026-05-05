# AI Project Assistant Management Relevance Update

This update keeps the AI Project Assistant read-only and system-record based, while making the answer more management-focused.

## Main changes

- Added strong relevance filtering for exact-key questions.
- Project questions now prioritise exact Project ID records and directly linked order/supplier evidence.
- Supplier Details are included only when linked by supplier_code / supplier_id from the exact project or order evidence.
- Price Comparison rows from unrelated projects are no longer pulled into a project answer just because they share a supplier/client/topic.
- Index Center rows are only included when directly relevant to an index question or project-linked index evidence.
- Added management-style answer guidance: current situation, confirmed facts, main risk/impact, missing or not found, suggested next step, evidence used.
- Added metadata to show when the strong relevance filter is active.

## Safety rules kept

- The assistant is read-only.
- No system records are changed.
- No business logic is changed.
- All answers must be based on current system records.
- Missing information must be described as not found in current system records, not as non-existent in real life.
