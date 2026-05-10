# RFQ Working File + RFQ Control Layer Update Notes

## Purpose
This update keeps the existing company RFQ working-file method and upgrades it with a light RFQ control layer.

Positioning:
- Old flow: RFQ Working File, used for free notes, customer original requirements, pictures, WeCom links and project file interface.
- New flow: RFQ Control Layer, used for RFQ status, missing information, risk level, owner, next step, due date, requirement checklist and system tracking.

The new flow does not fully replace the old RFQ file. It absorbs the useful parts of the old file and adds standardised control areas.

## Main changes

### 1. QP-01 template upgraded
The `QP-01 RFQ Requirement Control Template` now contains:
- `RFQ Working File`: familiar project working-file structure with project links, basic information, original requirement notes and task/action log.
- `RFQ Control Summary`: structured control layer for RFQ ID, project ID, working file link, customer, product description, RFQ gate status, missing information, risk level, owner, next step and due date.
- `Requirement Checklist`: structured confirmation table for drawing, specification, quantity, packaging, testing, compliance, sample, inspection and missing information.
- `Risk Review`: Harley/Maria/Ehab risk ownership table.
- `Template`: technical import/export field sheet for future system integration.
- `Field Guide`: field explanations.
- `Instructions`: usage notes.

### 2. Quality Process Management page updated
The `QP-01 RFQ` tab now shows a clean explanation of:
- RFQ Working File
- RFQ Control Layer
- How the old flow is retained
- What new control points are added

### 3. Control points updated
QP-01 control points now start with:
1. Receive RFQ and open RFQ Working File.
2. Record original requirement notes and project file links.
3. Complete RFQ Control Summary and requirement checklist.
4. Continue supplier quotation and risk review.

## No core logic changed
This update does not change:
- database schema
- import logic
- Sales Board logic
- Operation Board logic
- Order Details logic
- Supplier Details logic
- Import Center permission logic

Import Center remains protected according to the current setting.
