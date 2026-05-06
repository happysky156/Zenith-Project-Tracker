# Board and Meeting Action Status Color Update

Scope: UI status-color logic only.

## Updated

### Sales Board / Operation Board
- Quick Action buttons now default to secondary style (white background / black text).
- A button becomes primary/red only when it matches the current saved field state of that Sales project or Operation order.
- If the related field is blank, unknown, or does not match the button meaning, the button remains normal.
- After a button is clicked, the existing action logic updates the record as before; after rerun, the corresponding current-state button becomes red.

### Meeting Mode
- Meeting Actions no longer become red because an action is high-impact.
- Meeting Action buttons now default to secondary style.
- A Meeting Action becomes primary/red only when it reflects the current saved meeting state, such as the latest recorded meeting action, follow-up done, or high-risk follow-up state.

## Preserved

- All Sales / Operation action update logic is unchanged.
- Meeting action business logic is unchanged.
- Meeting Pool logic is unchanged.
- Database schema is unchanged.
- Index Center, Price Comparison, Supplier Details, AI Project Assistant, Import Center, and Project Detail logic are unchanged.
