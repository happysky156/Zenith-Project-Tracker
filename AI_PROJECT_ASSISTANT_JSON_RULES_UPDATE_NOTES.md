# AI Project Assistant JSON + Read-only Rules Update

This update keeps AI Project Assistant read-only and does not change Sales, Operation, Meeting, Index, Supplier, Price Comparison, or Order business logic.

Changes:
- Adds stricter read-only cross-module analysis rules to the AI prompt.
- Adds module source priority, join keys, review rules, answer templates, not-found handling, and evidence requirements.
- Adds deterministic readonly_analysis_context to the AI evidence payload.
- Reduces invalid JSON risk by using concise schema instructions and increasing default AI max tokens.
- Adds conservative JSON extraction fallback in services/ai_client.py.
- If AI API is unavailable or returns invalid JSON, the page now shows a deterministic system-record answer instead of a generic fallback.

Safety rules retained:
- AI cannot create, update, delete, or assume system data.
- AI can only use the system evidence provided.
- If information is not found in system records, the answer must say it was not found in current system records.
- Cross-module joining is only allowed by system keys such as project_id, supplier_code, supplier_id, order_no, rfq_item_ref, item_option, and index_name/index_code.
