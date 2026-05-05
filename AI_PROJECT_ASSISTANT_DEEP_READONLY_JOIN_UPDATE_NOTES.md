# AI Project Assistant Deep Read-only Join Update

This update strengthens AI Project Assistant as a read-only business record analysis assistant.

## Purpose

The assistant can now connect already-loaded system records using deterministic join keys before sending evidence to the AI model. This fixes cases where a project answer found Order Details with a supplier code, but did not include the matching Supplier Details row in final answer records.

## Safety boundaries

- No database writes are performed.
- No business logic is changed.
- The assistant only joins records that already exist in the current system data.
- The assistant does not create facts, modify status, select suppliers, or update records.
- If information is not found in system records, the answer must say it was not found in current system records.

## Join keys used

- project_id
- supplier_code
- supplier_id
- order_no
- rfq_item_ref
- item_option
- index_name / index_code

## Main behavior change

For broad project questions such as `Show all information for project SDG-26-013`, the assistant now:

1. Finds direct records for the project.
2. Extracts join keys such as supplier_code from Order Details or Price Comparison.
3. Adds related Supplier Details, Price Comparison, Order Details, and Index Center records when connected by approved keys.
4. Sends the expanded evidence bundle to the AI model.
5. Keeps deterministic joined records visible in final answer records.

Example:

```text
Order Details.supplier_code = SD185
→ Supplier Details.supplier_code = SD185
```

## Files changed

- services/ai_project_service.py
