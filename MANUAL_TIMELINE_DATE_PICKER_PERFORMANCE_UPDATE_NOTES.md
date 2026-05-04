# Manual Timeline Date Picker + Performance Update

This update refines Project Detail > History > Manual Timeline Supplement.

## Changes

- Manual Timeline Supplement saves now set a saved-message flag and rerun once; the expander label changes on the next run so the form is shown collapsed.
- Manual Planned Date, Manual Actual Date, and Manual Waiting Since now use Streamlit date pickers instead of free text inputs.
- Manual input widgets remain inside a Streamlit form so changing date/owner/note fields does not trigger reruns until Save is clicked.
- Milestone selection reads from the already computed lifecycle data instead of recalculating lifecycle/event data.
- Manual supplement rows are fetched once for the project and matched in memory for the selected milestone.
- System-generated actual dates remain locked: Manual Actual Date is disabled whenever an automatic actual date already exists.

## Preserved rules

- System timeline records are the primary source.
- Manual supplements cannot overwrite automatic actual dates.
- Missing / Not Applicable / Need Review lifecycle states remain safe placeholders.
- Sales, Operation, Login, Meeting Mode, Supplier import, and View more logic are unchanged.
