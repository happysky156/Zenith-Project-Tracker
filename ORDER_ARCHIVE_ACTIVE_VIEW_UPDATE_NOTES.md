# Order Archive Active View Update

This update adds manual Order Archive display control while keeping the existing Sales, Operation, Order Details, Meeting Mode, Import, and AI business logic unchanged.

## Added

- Operation Board archive view filter:
  - Active only (default)
  - Archived only
  - All
- Order Details archive view filter:
  - Active only (default)
  - Archived only
  - All
- Order Details and Order Costs inherit archive status from Operation Order by Order No.
- AI Project Assistant excludes archived Operation / Order Details records by default.
- AI Project Assistant includes archived records only when the user explicitly asks for archived / historical records.

## Preserved

- Archive is soft archive only; no records are deleted.
- Existing Project / Order Detail archive / restore workflow is preserved.
- Operation Order remains the archive control object.
- Order Details item lines are not individually archived; they are shown or hidden by the linked Order No archive status.
- Meeting Pool logic remains unchanged and continues to rely on active records.
- Import logic remains unchanged.
