# Commercial Won vs Project Fully Closed Logic Update

This update refines the Commercial Timeline management logic without changing the core Sales / Operation business logic.

## Business rule

- `Won` means **Commercial Won**.
- `Won` does **not** mean the full project/order lifecycle is closed.
- `Project Fully Closed` is marked as done only when linked Operation order(s) are completed / paid closed, or when an explicit Project Fully Closed event exists.

## Timeline changes

- Added lifecycle milestone: `Commercial Won`.
- Renamed final closure milestone display to: `Project Fully Closed`.
- Sales result `Won` now fills `Commercial Won`, not `Project Fully Closed`.
- For won cases with linked Operation orders still in progress, `Project Fully Closed` remains Pending / Current, depending on the lifecycle position.
- For linked Operation orders with `Paid Closed`, `Completed`, `Complete Shipped`, `Closed`, or cancelled terminal status, `Project Fully Closed` can be marked done.

## Safety

- Login behavior unchanged.
- Sales Board logic unchanged.
- Operation Board logic unchanged.
- Meeting Mode logic unchanged.
- Manual Timeline Supplement behavior unchanged.
- Date picker / performance optimization retained.
