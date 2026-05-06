# Board + Meeting Status Button Color Fix

Scope:
- Sales Board quick actions
- Operation Board quick actions
- Meeting Mode action buttons

Purpose:
- Red buttons now mean current recorded status only.
- White buttons mean available actions.
- Red is no longer used to mark normal shortcut buttons as important.

Sales Board rules:
- If Result = Won, only Close Won is red.
- If Result = Lost, only Close Lost is red.
- Quote/Sample/Waiting/Risk buttons stay white after a sales result is closed.
- Push To Meeting is red only when Review This Week / Meeting Pool flag is active.
- Open Detail is always white/secondary.

Operation Board rules:
- Execution progress buttons are red only when they match the current phase/result.
- Waiting/Risk buttons are red only when they match the current health status.
- Push To Meeting is red only when Review This Week / Meeting Pool flag is active.
- Open Detail is always white/secondary.

Meeting Mode rules:
- Meeting Actions are white by default.
- Mark Follow-up Done is red when followup_status = Done.
- High-Risk Follow-up is red when the current record is in a saved high-risk/decision/blocked state.
- Other meeting actions are red only when they match the latest saved meeting action.

Unchanged:
- Button click business logic
- Database schema
- Meeting Pool calculation
- Project / Order Detail
- Index Center
- Price Comparison
- Supplier Details
- AI Project Assistant
