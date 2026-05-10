# Business Control System V1 Fix Notes

This package fixes early V1 page issues without changing authentication, core data, or existing business logic.

## Fixes

1. Sample Board now maps to the existing `Sample Tracking` module.
2. Supplier Board now maps to the existing `Supplier Details` module.
3. Process status labels were cleaned: no Phase/read-only wording is shown in process version cards.
4. Effective status text is now `Pending approval` until a version-control workflow is implemented.
5. Import Center template section wording was cleaned.

## Not changed

- Login/authentication logic.
- Existing Sales, Operation, Supplier Details, Sample Tracking, Price Comparison, Index, Order Details business logic.
- Database data is not physically deleted.
- Import Center permission remains restricted to authorised Harley email(s).

## Notes

- Project matching for Mail Intelligence is not yet a persisted feature. It should be implemented as a later `Project Matching` workflow.
- AI Assistant Center is currently the global AI Project Assistant. The old AI Meeting Assistant workflow remains in the archived page and should later be embedded into Meeting Board.
