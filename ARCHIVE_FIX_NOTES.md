# v17.27 Project Detail Archive Session-State Fix

This version only changes `pages/4_Project_Detail.py`.

## Issue fixed

When archiving a record from Project Detail, Streamlit raised an error similar to:

```text
streamlit.errors.StreamlitAPIException
st.session_state['detail_include_archived'] = True
```

Reason: `detail_include_archived` is the key of the `Include archived` checkbox. Streamlit does not allow setting a widget-backed session_state key after the widget has already been created in the same script run.

## Fix

The archive button now sets a temporary non-widget flag:

```python
st.session_state["detail_force_include_archived"] = True
```

On the next rerun, before the checkbox is created, the code safely applies:

```python
if st.session_state.pop("detail_force_include_archived", False):
    st.session_state["detail_include_archived"] = True
```

## Business logic unchanged

- Archive still hides records; it does not delete them.
- The existing rule that system records cannot be deleted is unchanged.
- Restore logic is unchanged.
- Search, filters, board logic, meeting logic, and data logic are unchanged.
