from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable
import re
import uuid

import pandas as pd

from database.connection import execute, get_connection
from database.repositories import write_import_batch
from utils.dates import now_iso
from utils.ids import new_batch_id
from utils.logger import get_logger

logger = get_logger("upgrade_service")


# -----------------------------------------------------------------------------
# Field specifications
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldSpec:
    name: str
    display: str
    description: str
    required: bool = False
    numeric: bool = False
    boolean: bool = False


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    table: str
    id_field: str | None
    key_fields: tuple[str, ...]
    fields: tuple[FieldSpec, ...]
    title: str
    description: str


SUPPLIER_FIELDS = (
    # System-generated / auto-calculated fields. They are displayed in Overview
    # and Activity tabs, but they are not intended to be maintained manually.
    FieldSpec("supplier_id", "Supplier ID", "System-generated supplier unique ID, for example SUP-000001."),
    FieldSpec("supplier_code", "Supplier Code", "Internal supplier code. Optional, because expo/new suppliers may not have one yet."),
    FieldSpec("supplier_name", "Supplier Name", "Supplier company name.", True),
    FieldSpec("supplier_short_name", "Supplier Short Name", "Supplier short name or alias."),
    FieldSpec("company_type", "Company Type", "Factory / Trading Company / Service Provider / Other."),

    FieldSpec("country", "Country", "Country."),
    FieldSpec("province", "Province", "Province."),
    FieldSpec("city", "City", "City."),
    FieldSpec("location_raw", "Location Raw", "Original location or address text from the source file."),
    FieldSpec("address_standardised", "Address Standardised", "Cleaned or standardised address."),
    FieldSpec("website_primary", "Website Primary", "Main supplier website."),
    FieldSpec("website_others", "Website Others", "Other website links."),

    FieldSpec("primary_contact_name", "Primary Contact Name", "Main contact person."),
    FieldSpec("primary_contact_mobile", "Primary Contact Mobile", "Main contact mobile number."),
    FieldSpec("primary_contact_email", "Primary Contact Email", "Main contact email address."),
    FieldSpec("primary_contact_landline", "Primary Contact Landline", "Main contact landline number."),
    FieldSpec("wechat", "WeChat", "WeChat contact."),
    FieldSpec("other_contacts", "Other Contacts", "Other contact persons or contact details."),

    FieldSpec("source_channel", "Source Channel", "Source channel, for example Expo / Website / Referral / Existing Database."),
    FieldSpec("source_ref", "Source Reference", "Source reference, such as exhibition name, website link, email, or old source file."),

    FieldSpec("certificate", "Certificate", "Certificates, such as ISO, BSCI or product certificates."),
    FieldSpec("certificate_remarks", "Certificate Remarks", "Certificate remarks."),
    FieldSpec("export_license", "Export License", "Export licence information."),
    FieldSpec("nda_status", "NDA Status", "NDA status."),
    FieldSpec("nda_file", "NDA File", "NDA file link."),
    FieldSpec("audit_status", "Audit Status", "Factory audit status."),
    FieldSpec("audit_file", "Audit File", "Factory audit file link."),
    FieldSpec("catalogue_status", "Catalogue Status", "Catalogue status."),
    FieldSpec("catalogue_file", "Catalogue File", "Catalogue file link."),

    FieldSpec("main_products", "Main Products", "Main product range."),
    FieldSpec("main_process", "Main Process", "Main production process."),
    FieldSpec("material_capability", "Material Capability", "Material capability."),
    FieldSpec("surface_treatment", "Surface Treatment", "Surface treatment capability."),
    FieldSpec("testing_capability", "Testing Capability", "Testing capability."),
    FieldSpec("capability_tags", "Capability Tags", "Capability tags for screening/searching."),

    FieldSpec("payment_terms", "Payment Terms", "Usual payment terms."),
    FieldSpec("lead_time", "Lead Time", "Usual lead time."),
    FieldSpec("quality_risk", "Quality Risk", "Low / Medium / High."),
    FieldSpec("commercial_risk", "Commercial Risk", "Low / Medium / High."),

    FieldSpec("last_contact_date", "Last Contact Date", "Last contact date."),
    FieldSpec("remark_internal", "Internal Remark", "Internal remark."),

    FieldSpec("active_status", "Active Status", "Auto-calculated from open orders. Do not manually maintain."),
    FieldSpec("active_reason", "Active Reason", "Auto-calculated explanation, e.g. linked open order."),
    FieldSpec("last_order_no", "Last Order No", "Auto-calculated latest linked order."),
    FieldSpec("last_project_id", "Last Project ID", "Auto-calculated latest linked project."),
    FieldSpec("price_comparison_count", "Price Comparison Count", "Auto-calculated supplier quotation count."),
    FieldSpec("order_count", "Order Count", "Auto-calculated linked order count."),
    FieldSpec("risk_summary", "Risk Summary", "Auto-generated summary from risk and quotation/order context."),
    FieldSpec("created_at", "Created At", "System created timestamp."),
    FieldSpec("created_by", "Created By", "System created by."),
    FieldSpec("last_updated_at", "Last Updated At", "System updated timestamp."),
    FieldSpec("last_updated_by", "Last Updated By", "System updated by."),
)

PROJECT_ITEM_FIELDS = (
    FieldSpec("project_id", "Project ID", "Linked Sales Project ID.", True),
    FieldSpec("item_code", "Item Code", "Project-level item code, e.g. ITEM-001.", True),
    FieldSpec("item_name", "Item Name", "Product/item name."),
    FieldSpec("item_description", "Item Description", "Product/item description."),
    FieldSpec("client_item_no", "Client Item No.", "Customer item number."),
    FieldSpec("drawing_no", "Drawing No.", "Drawing number."),
    FieldSpec("drawing_revision", "Drawing Revision", "Drawing revision."),
    FieldSpec("material", "Material", "Material."),
    FieldSpec("surface_treatment", "Surface Treatment", "Surface treatment."),
    FieldSpec("estimated_qty", "Estimated Qty", "Estimated quantity.", numeric=True),
    FieldSpec("unit", "Unit", "Unit of measure."),
    FieldSpec("item_status", "Item Status", "Active / Cancelled / Quoted / Ordered."),
    FieldSpec("remarks", "Remarks", "Free text notes."),
    FieldSpec("created_at", "Created At", "System created timestamp."),
    FieldSpec("created_by", "Created By", "System created by."),
    FieldSpec("last_updated_at", "Last Updated At", "System updated timestamp."),
    FieldSpec("last_updated_by", "Last Updated By", "System updated by."),
)

SUPPLIER_PRICE_FIELDS = (
    FieldSpec("supplier_quote_id", "Supplier Quote ID", "System-generated supplier quotation ID."),
    FieldSpec("project_id", "Project ID", "Linked Project ID.", True),
    FieldSpec("item_code", "Item Code", "Linked Item Code.", True),
    FieldSpec("supplier_id", "Supplier ID", "Linked Supplier ID. Auto-created from supplier name/code when possible."),
    FieldSpec("supplier_code", "Supplier Code", "Internal supplier code, optional."),
    FieldSpec("supplier_name", "Supplier Name", "Supplier name.", True),
    FieldSpec("quote_round", "Quote Round", "Supplier quote round."),
    FieldSpec("quote_date", "Quote Date", "Supplier quote date."),
    FieldSpec("supplier_unit_cost", "Supplier Unit Cost", "Supplier unit cost.", numeric=True),
    FieldSpec("currency", "Currency", "Currency."),
    FieldSpec("moq", "MOQ", "Minimum order quantity."),
    FieldSpec("lead_time", "Lead Time", "Mass production lead time."),
    FieldSpec("sample_lead_time", "Sample Lead Time", "Sample lead time."),
    FieldSpec("price_term", "Price Term", "EXW / FOB / CIF / etc."),
    FieldSpec("tooling_cost", "Tooling Cost", "Tooling cost.", numeric=True),
    FieldSpec("sample_cost", "Sample Cost", "Sample cost.", numeric=True),
    FieldSpec("packing_cost", "Packing Cost", "Packing cost.", numeric=True),
    FieldSpec("supplier_material_basis", "Supplier Material Basis", "Supplier's material price basis."),
    FieldSpec("supplier_quote_validity", "Supplier Quote Validity", "Supplier quotation validity."),
    FieldSpec("price_adjustment_note", "Price Adjustment Note", "Material/FX adjustment note."),
    FieldSpec("missing_info", "Missing Information", "Missing quotation information."),
    FieldSpec("quotation_quality", "Quotation Quality", "Complete / Partial / Poor."),
    FieldSpec("quotation_risk", "Quotation Risk", "Low / Medium / High."),
    FieldSpec("recommended_supplier", "Recommended Supplier", "Yes / No.", boolean=True),
    FieldSpec("selected_supplier", "Selected Supplier", "Yes / No.", boolean=True),
    FieldSpec("selection_reason", "Selection Reason", "Reason for selecting/recommending."),
    FieldSpec("comparison_status", "Comparison Status", "Auto-calculated: Completed / In Progress."),
    FieldSpec("remarks", "Remarks", "Free text notes."),
    FieldSpec("imported_at", "Imported At", "System imported timestamp."),
    FieldSpec("imported_by", "Imported By", "System imported by."),
)

CLIENT_QUOTE_HEADER_FIELDS = (
    FieldSpec("client_quote_id", "Client Quote ID", "System-generated client quotation ID."),
    FieldSpec("project_id", "Project ID", "Linked Project ID.", True),
    FieldSpec("quote_version", "Quote Version", "Auto-generated V1 / V2 / V3 if blank."),
    FieldSpec("quote_date", "Quote Date", "Quotation date."),
    FieldSpec("client_code", "Client Code", "Client code."),
    FieldSpec("client_name", "Client Name", "Client name."),
    FieldSpec("quote_status", "Quote Status", "Draft / Sent / Revised / Accepted / Lost."),
    FieldSpec("price_term", "Price Term", "FOB / CIF / DDP / etc."),
    FieldSpec("quote_currency", "Quote Currency", "Quotation currency."),
    FieldSpec("index_snapshot_date", "Index Snapshot Date", "Index date used for this quotation."),
    FieldSpec("material_snapshot_status", "Material Snapshot Status", "Material index lock status."),
    FieldSpec("fx_snapshot_status", "FX Snapshot Status", "FX lock status."),
    FieldSpec("freight_snapshot_status", "Freight Snapshot Status", "Freight lock status."),
    FieldSpec("quote_valid_until", "Quote Valid Until", "Quotation valid until date."),
    FieldSpec("remarks", "Remarks", "Free text notes."),
    FieldSpec("created_at", "Created At", "System created timestamp."),
    FieldSpec("created_by", "Created By", "System created by."),
    FieldSpec("last_updated_at", "Last Updated At", "System updated timestamp."),
    FieldSpec("last_updated_by", "Last Updated By", "System updated by."),
)

CLIENT_QUOTE_LINE_FIELDS = (
    FieldSpec("client_quote_line_id", "Client Quote Line ID", "System-generated quotation line ID."),
    FieldSpec("client_quote_id", "Client Quote ID", "Linked client quotation header ID.", True),
    FieldSpec("project_id", "Project ID", "Linked Project ID.", True),
    FieldSpec("item_code", "Item Code", "Linked Item Code.", True),
    FieldSpec("item_name", "Item Name", "Item name."),
    FieldSpec("selected_supplier_id", "Selected Supplier ID", "Selected supplier ID."),
    FieldSpec("supplier_quote_id", "Supplier Quote ID", "Linked supplier quote ID."),
    FieldSpec("supplier_unit_cost", "Supplier Unit Cost", "Supplier unit cost.", numeric=True),
    FieldSpec("client_unit_price", "Client Unit Price", "Client selling unit price.", numeric=True),
    FieldSpec("quantity_basis", "Quantity Basis", "Quotation quantity basis.", numeric=True),
    FieldSpec("currency", "Currency", "Currency."),
    FieldSpec("price_term", "Price Term", "FOB / CIF / DDP / etc."),
    FieldSpec("material_index_used", "Material Index Used", "Whether material index is used."),
    FieldSpec("freight_used", "Freight Used", "Whether freight is included."),
    FieldSpec("estimated_revenue", "Estimated Revenue", "Auto-calculated: client unit price × quantity.", numeric=True),
    FieldSpec("estimated_supplier_cost", "Estimated Supplier Cost", "Auto-calculated: supplier unit cost × quantity.", numeric=True),
    FieldSpec("estimated_extra_cost", "Estimated Extra Cost", "Estimated extra cost.", numeric=True),
    FieldSpec("estimated_gp", "Estimated Gross Profit", "Auto-calculated estimated gross profit.", numeric=True),
    FieldSpec("estimated_gp_percent", "Estimated GP %", "Auto-calculated estimated GP percentage.", numeric=True),
    FieldSpec("remarks", "Remarks", "Free text notes."),
)

INDEX_CONFIG_FIELDS = (
    FieldSpec("index_config_id", "Index Config ID", "System-generated index config ID."),
    FieldSpec("index_category", "Index Category", "FX / Metal / Plastic / Freight.", True),
    FieldSpec("index_name", "Index Name", "USD/CNY, Stainless Steel 304, Carbon Steel, etc.", True),
    FieldSpec("display_name", "Display Name", "Display name on Index Center."),
    FieldSpec("unit", "Unit", "CNY/ton, USD/40HQ, rate, etc."),
    FieldSpec("source_name", "Source Name", "Data source name."),
    FieldSpec("source_url", "Source URL", "Data source URL."),
    FieldSpec("fetch_enabled", "Fetch Enabled", "Whether automatic fetch is enabled.", boolean=True),
    FieldSpec("fetch_method", "Fetch Method", "API / Web Parse / Manual / Carry Forward."),
    FieldSpec("fallback_method", "Fallback Method", "Fallback method when fetch fails."),
    FieldSpec("active", "Active", "Whether this index is active.", boolean=True),
    FieldSpec("remarks", "Remarks", "Free text notes."),
)

DAILY_INDEX_FIELDS = (
    FieldSpec("daily_index_id", "Daily Index ID", "System-generated daily index ID."),
    FieldSpec("index_date", "Index Date", "Index date.", True),
    FieldSpec("index_category", "Index Category", "FX / Metal / Plastic / Freight."),
    FieldSpec("index_name", "Index Name", "Index name.", True),
    FieldSpec("index_value", "Index Value", "Daily index value.", True, numeric=True),
    FieldSpec("unit", "Unit", "Unit."),
    FieldSpec("source_name", "Source Name", "Data source name."),
    FieldSpec("source_url", "Source URL", "Source URL."),
    FieldSpec("fetch_method", "Fetch Method", "API / Web Parse / Manual / Carry Forward."),
    FieldSpec("fetch_status", "Fetch Status", "Success / Failed / Manual / Carry Forward."),
    FieldSpec("previous_value", "Previous Value", "Previous value.", numeric=True),
    FieldSpec("change_value", "Change Value", "Change from previous value.", numeric=True),
    FieldSpec("change_percent", "Change Percent", "Change percentage.", numeric=True),
    FieldSpec("error_message", "Error Message", "Fetch error message."),
    FieldSpec("confirmed_by_user", "Confirmed By User", "Manual confirmation flag.", boolean=True),
    FieldSpec("confirmed_at", "Confirmed At", "Confirmed timestamp."),
    FieldSpec("last_updated_at", "Last Updated At", "Updated timestamp."),
    FieldSpec("updated_by", "Updated By", "Updated by."),
)

INDEX_SNAPSHOT_FIELDS = (
    FieldSpec("index_snapshot_id", "Index Snapshot ID", "System-generated snapshot ID."),
    FieldSpec("client_quote_id", "Client Quote ID", "Linked client quotation."),
    FieldSpec("project_id", "Project ID", "Linked project.", True),
    FieldSpec("item_code", "Item Code", "Linked item."),
    FieldSpec("quote_version", "Quote Version", "Linked client quote version."),
    FieldSpec("snapshot_date", "Snapshot Date", "Index snapshot date."),
    FieldSpec("material_index_name", "Material Index Name", "Stainless Steel 304 / Carbon Steel / Zinc / PP / ABS / PVC."),
    FieldSpec("material_index_value", "Material Index Value", "Material index value.", numeric=True),
    FieldSpec("material_index_unit", "Material Index Unit", "Material index unit."),
    FieldSpec("freight_index_name", "Freight Index Name", "Freight index name."),
    FieldSpec("freight_index_value", "Freight Index Value", "Freight index value.", numeric=True),
    FieldSpec("freight_route", "Freight Route", "China Main Port → Israel / China Main Port → Morocco."),
    FieldSpec("freight_unit", "Freight Unit", "USD/40HQ, USD/20GP, etc."),
    FieldSpec("exchange_rate_pair", "Exchange Rate Pair", "For example USD/CNY."),
    FieldSpec("exchange_rate_value", "Exchange Rate Value", "Exchange rate value.", numeric=True),
    FieldSpec("exchange_rate_source", "Exchange Rate Source", "FX source."),
    FieldSpec("source_name", "Source Name", "Index source name."),
    FieldSpec("source_url", "Source URL", "Index source URL."),
    FieldSpec("locked_at", "Locked At", "Snapshot locked timestamp."),
    FieldSpec("locked_by", "Locked By", "Locked by user."),
    FieldSpec("remarks", "Remarks", "Free text notes."),
)

FREIGHT_INDEX_FIELDS = (
    FieldSpec("freight_index_id", "Freight Index ID", "System-generated freight index ID."),
    FieldSpec("index_date", "Index Date", "Date.", True),
    FieldSpec("destination_country", "Destination Country", "Israel / Morocco.", True),
    FieldSpec("destination_port", "Destination Port", "Destination port, optional."),
    FieldSpec("origin_port", "Origin Port", "China Main Port / Ningbo / Shanghai / etc."),
    FieldSpec("container_type", "Container Type", "20GP / 40HQ / LCL."),
    FieldSpec("freight_value", "Freight Value", "Freight value.", True, numeric=True),
    FieldSpec("currency", "Currency", "USD / CNY."),
    FieldSpec("source_type", "Source Type", "Client Quotation / Forwarder / Manual / Carry Forward."),
    FieldSpec("source_note", "Source Note", "Source note."),
    FieldSpec("last_actual_update_date", "Last Actual Update Date", "Last real update date."),
    FieldSpec("carry_forward", "Carry Forward", "Whether value is carried forward from previous day.", boolean=True),
    FieldSpec("remarks", "Remarks", "Free text notes."),
)

ORDER_DETAIL_FIELDS = (
    FieldSpec("order_detail_id", "Order Detail ID", "System-generated order detail ID."),
    FieldSpec("order_no", "Order No", "Linked operation order number.", True),
    FieldSpec("project_id", "Project ID", "Linked Project ID.", True),
    FieldSpec("item_code", "Item Code", "Linked Item Code.", True),
    FieldSpec("client_quote_id", "Client Quote ID", "Linked client quotation."),
    FieldSpec("client_quote_line_id", "Client Quote Line ID", "Linked client quotation line."),
    FieldSpec("supplier_quote_id", "Supplier Quote ID", "Linked supplier quotation."),
    FieldSpec("supplier_id", "Supplier ID", "Linked supplier ID."),
    FieldSpec("supplier_code", "Supplier Code", "Supplier code, display only."),
    FieldSpec("supplier_name", "Supplier Name", "Supplier name."),
    FieldSpec("client_code", "Client Code", "Client code."),
    FieldSpec("po_no", "PO No.", "Client PO number."),
    FieldSpec("customer_item_no", "Customer Item No.", "Customer item number."),
    FieldSpec("supplier_item_no", "Supplier Item No.", "Supplier item number."),
    FieldSpec("order_qty", "Order Qty", "Order quantity.", numeric=True),
    FieldSpec("unit", "Unit", "Unit of measure."),
    FieldSpec("client_unit_price", "Client Unit Price", "Client selling unit price.", numeric=True),
    FieldSpec("supplier_unit_cost", "Supplier Unit Cost", "Supplier cost unit price.", numeric=True),
    FieldSpec("currency", "Currency", "Currency."),
    FieldSpec("sales_revenue", "Sales Revenue", "Auto-calculated sales revenue.", numeric=True),
    FieldSpec("supplier_cost", "Supplier Cost", "Auto-calculated supplier cost.", numeric=True),
    FieldSpec("extra_cost", "Extra Cost", "Auto-calculated extra cost from Order Costs.", numeric=True),
    FieldSpec("gross_profit", "Gross Profit", "Auto-calculated gross profit.", numeric=True),
    FieldSpec("gross_profit_percent", "Gross Profit %", "Auto-calculated GP percentage.", numeric=True),
    FieldSpec("payment_status", "Payment Status", "Payment status."),
    FieldSpec("production_status", "Production Status", "Production status."),
    FieldSpec("inspection_status", "Inspection Status", "Inspection status."),
    FieldSpec("packing_status", "Packing Status", "Packing status."),
    FieldSpec("shipment_status", "Shipment Status", "Shipment status."),
    FieldSpec("order_date", "Order Date", "Order date."),
    FieldSpec("deposit_date", "Deposit Date", "Deposit date."),
    FieldSpec("target_delivery_date", "Target Delivery Date", "Target delivery date."),
    FieldSpec("actual_delivery_date", "Actual Delivery Date", "Actual delivery date."),
    FieldSpec("inspection_date", "Inspection Date", "Inspection date."),
    FieldSpec("shipment_date", "Shipment Date", "Shipment date."),
    FieldSpec("container_no", "Container No.", "Container number."),
    FieldSpec("bl_no", "B/L No.", "Bill of lading number."),
    FieldSpec("main_issue", "Main Issue", "Main issue."),
    FieldSpec("next_step", "Next Step", "Next step."),
    FieldSpec("next_step_owner", "Next Step Owner", "Next step owner."),
    FieldSpec("remarks", "Remarks", "Free text notes."),
    FieldSpec("imported_at", "Imported At", "System imported timestamp."),
    FieldSpec("imported_by", "Imported By", "System imported by."),
)

ORDER_COST_FIELDS = (
    FieldSpec("cost_id", "Cost ID", "System-generated cost ID."),
    FieldSpec("order_no", "Order No", "Linked order number.", True),
    FieldSpec("project_id", "Project ID", "Project ID."),
    FieldSpec("item_code", "Item Code", "Item Code, optional."),
    FieldSpec("cost_type", "Cost Type", "Testing / Courier / Inspection / Freight / Other.", True),
    FieldSpec("cost_description", "Cost Description", "Cost description."),
    FieldSpec("cost_amount", "Cost Amount", "Cost amount.", True, numeric=True),
    FieldSpec("currency", "Currency", "Currency."),
    FieldSpec("paid_by", "Paid By", "Zenith / Client / Supplier."),
    FieldSpec("charge_to_client", "Charge to Client", "Yes / No.", boolean=True),
    FieldSpec("cost_date", "Cost Date", "Cost date."),
    FieldSpec("invoice_no", "Invoice No.", "Invoice number, optional."),
    FieldSpec("remarks", "Remarks", "Free text notes."),
    FieldSpec("created_at", "Created At", "System created timestamp."),
    FieldSpec("created_by", "Created By", "System created by."),
)

SAMPLE_TRACKING_FIELDS = (
    FieldSpec("sample_id", "Sample ID", "System-generated sample ID."),
    FieldSpec("project_id", "Project ID", "Linked Project ID.", True),
    FieldSpec("item_code", "Item Code", "Linked Item Code."),
    FieldSpec("supplier_id", "Supplier ID", "Linked Supplier ID."),
    FieldSpec("supplier_code", "Supplier Code", "Supplier code, display only."),
    FieldSpec("supplier_name", "Supplier Name", "Supplier name."),
    FieldSpec("sample_type", "Sample Type", "Initial / Revised / Testing / Pre-production / Mass Production."),
    FieldSpec("sample_round", "Sample Round", "Sample round."),
    FieldSpec("sample_status", "Sample Status", "Not Started / In Progress / Sent / Approved / Rejected / Need Revision."),
    FieldSpec("sample_purpose", "Sample Purpose", "Client Approval / Testing / Reference."),
    FieldSpec("sample_request_date", "Sample Request Date", "Sample request date."),
    FieldSpec("target_sample_date", "Target Sample Date", "Target sample completion date."),
    FieldSpec("sample_sent_date", "Sample Sent Date", "Supplier sent date."),
    FieldSpec("sample_received_date", "Sample Received Date", "Sample received date."),
    FieldSpec("sample_sent_to_client_date", "Sent to Client Date", "Sent to client date."),
    FieldSpec("client_feedback_date", "Client Feedback Date", "Client feedback date."),
    FieldSpec("client_feedback", "Client Feedback", "Client feedback."),
    FieldSpec("sample_issue", "Sample Issue", "Sample issue."),
    FieldSpec("revision_required", "Revision Required", "Yes / No.", boolean=True),
    FieldSpec("next_sample_round_needed", "Next Sample Round Needed", "Yes / No.", boolean=True),
    FieldSpec("testing_required", "Testing Required", "Whether testing is needed.", boolean=True),
    FieldSpec("test_type", "Test Type", "Test type."),
    FieldSpec("test_standard", "Test Standard", "Test standard."),
    FieldSpec("test_lab", "Test Lab", "Test lab."),
    FieldSpec("test_sent_date", "Test Sent Date", "Test sent date."),
    FieldSpec("test_status", "Test Status", "Not Required / Pending / Sent to Lab / Testing / Passed / Failed / Need Retest."),
    FieldSpec("test_result", "Test Result", "Test result."),
    FieldSpec("test_report_link", "Test Report Link", "Test report link."),
    FieldSpec("test_fee", "Test Fee", "Test fee.", numeric=True),
    FieldSpec("test_issue", "Test Issue", "Test issue."),
    FieldSpec("sample_folder_link", "Sample Folder Link", "Sample folder link."),
    FieldSpec("sample_photo_link_1", "Sample Photo Link 1", "Sample photo link 1."),
    FieldSpec("sample_photo_link_2", "Sample Photo Link 2", "Sample photo link 2."),
    FieldSpec("sample_photo_link_3", "Sample Photo Link 3", "Sample photo link 3."),
    FieldSpec("courier_company", "Courier Company", "Courier company."),
    FieldSpec("tracking_no", "Tracking No.", "Tracking number."),
    FieldSpec("next_step", "Next Step", "Next step."),
    FieldSpec("next_step_owner", "Next Step Owner", "Next step owner."),
    FieldSpec("target_date", "Target Date", "Next target date."),
    FieldSpec("remarks", "Remarks", "Free text notes."),
    FieldSpec("last_updated_at", "Last Updated At", "System updated timestamp."),
    FieldSpec("last_updated_by", "Last Updated By", "System updated by."),
)

MODULES: dict[str, ModuleSpec] = {
    "Supplier Details": ModuleSpec("Supplier Details", "supplier_details", "supplier_id", ("supplier_id",), SUPPLIER_FIELDS, "Supplier Details", "Supplier master data shared by Sales and Operation."),
    "Project Items": ModuleSpec("Project Items", "project_items", None, ("project_id", "item_code"), PROJECT_ITEM_FIELDS, "Project Items", "Products/items under one Project ID."),
    "Supplier Price Comparison": ModuleSpec("Supplier Price Comparison", "supplier_price_comparisons", "supplier_quote_id", ("supplier_quote_id",), SUPPLIER_PRICE_FIELDS, "Supplier Price Comparison", "Supplier-side cost quotations."),
    "Client Quotation Header": ModuleSpec("Client Quotation Header", "client_quotation_headers", "client_quote_id", ("client_quote_id",), CLIENT_QUOTE_HEADER_FIELDS, "Client Quotation Header", "One client quotation version per Project ID."),
    "Client Quotation Lines": ModuleSpec("Client Quotation Lines", "client_quotation_lines", "client_quote_line_id", ("client_quote_line_id",), CLIENT_QUOTE_LINE_FIELDS, "Client Quotation Lines", "Item-level quotation lines."),
    "Index Config": ModuleSpec("Index Config", "index_config", "index_config_id", ("index_config_id",), INDEX_CONFIG_FIELDS, "Index Config", "Index list and fetch settings."),
    "Daily Market Indices": ModuleSpec("Daily Market Indices", "daily_market_indices", "daily_index_id", ("daily_index_id",), DAILY_INDEX_FIELDS, "Daily Market Indices", "Daily FX, material and freight values."),
    "Index Snapshot": ModuleSpec("Index Snapshot", "index_snapshots", "index_snapshot_id", ("index_snapshot_id",), INDEX_SNAPSHOT_FIELDS, "Index Snapshot", "Locked quotation index snapshot."),
    "Freight Index": ModuleSpec("Freight Index", "freight_indices", "freight_index_id", ("freight_index_id",), FREIGHT_INDEX_FIELDS, "Freight Index", "Freight values for Israel and Morocco."),
    "Order Details": ModuleSpec("Order Details", "order_details", "order_detail_id", ("order_detail_id",), ORDER_DETAIL_FIELDS, "Order Details", "Order item details linked to Operation Board."),
    "Order Costs": ModuleSpec("Order Costs", "order_costs", "cost_id", ("cost_id",), ORDER_COST_FIELDS, "Order Costs", "Extra costs used for gross profit calculation."),
    "Sample Tracking": ModuleSpec("Sample Tracking", "sample_tracking", "sample_id", ("sample_id",), SAMPLE_TRACKING_FIELDS, "Sample Tracking", "Sample, testing and feedback tracking."),
}

DEFAULT_INDEX_CONFIG = [
    ("FX", "USD/CNY", "USD/CNY", "rate", "Manual / Bank of China", "", "Manual", "Carry Forward"),
    ("Metal", "Stainless Steel 304", "Stainless Steel 304", "CNY/ton", "Manual / Fixed source", "", "Manual", "Carry Forward"),
    ("Metal", "Carbon Steel", "Carbon Steel", "CNY/ton", "Manual / Fixed source", "", "Manual", "Carry Forward"),
    ("Metal", "Zinc", "Zinc", "CNY/ton", "Manual / Fixed source", "", "Manual", "Carry Forward"),
    ("Metal", "Aluminium", "Aluminium", "CNY/ton", "Manual / Fixed source", "", "Manual", "Carry Forward"),
    ("Plastic", "PP", "PP", "CNY/ton", "Manual / Fixed source", "", "Manual", "Carry Forward"),
    ("Plastic", "ABS", "ABS", "CNY/ton", "Manual / Fixed source", "", "Manual", "Carry Forward"),
    ("Plastic", "PVC", "PVC", "CNY/ton", "Manual / Fixed source", "", "Manual", "Carry Forward"),
    ("Freight", "Freight to Israel", "Freight to Israel", "USD/40HQ", "Manual / Forwarder", "", "Manual", "Carry Forward"),
    ("Freight", "Freight to Morocco", "Freight to Morocco", "USD/40HQ", "Manual / Forwarder", "", "Manual", "Carry Forward"),
]


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------

def ensure_ready() -> None:
    from database.schema import init_extension_db
    init_extension_db()


def field_names(module_name: str, include_system: bool = True) -> list[str]:
    fields = [f.name for f in MODULES[module_name].fields]
    if not include_system:
        fields = [f for f in fields if not f.endswith("_at") and not f.endswith("_by")]
    return fields


def field_display_map(module_name: str) -> dict[str, str]:
    return {f.name: f.display for f in MODULES[module_name].fields}


def required_fields(module_name: str) -> list[str]:
    return [f.name for f in MODULES[module_name].fields if f.required]


IMPORT_EXCLUDED_FIELDS: dict[str, set[str]] = {
    "Supplier Details": {
        "supplier_id",
        "active_status",
        "active_reason",
        "last_order_no",
        "last_project_id",
        "price_comparison_count",
        "order_count",
        "risk_summary",
        "created_at",
        "created_by",
        "last_updated_at",
        "last_updated_by",
    }
}


def import_field_names(module_name: str) -> list[str]:
    excluded = IMPORT_EXCLUDED_FIELDS.get(module_name, set())
    return [field for field in field_names(module_name) if field not in excluded]


def import_required_fields(module_name: str) -> list[str]:
    excluded = IMPORT_EXCLUDED_FIELDS.get(module_name, set())
    return [field for field in required_fields(module_name) if field not in excluded]


def numeric_fields(module_name: str) -> set[str]:
    return {f.name for f in MODULES[module_name].fields if f.numeric}


def bool_fields(module_name: str) -> set[str]:
    return {f.name for f in MODULES[module_name].fields if f.boolean}


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _fetchone_dict(cur) -> dict[str, Any] | None:
    row = cur.fetchone()
    return dict(row) if row else None


def _normalize_text(value: Any) -> str | None:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return None
    return text


def _to_float(value: Any) -> float | None:
    text = _normalize_text(value)
    if text is None:
        return None
    try:
        return float(str(text).replace(",", ""))
    except Exception:
        return None


def _to_bool(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    if text in {"yes", "y", "true", "1", "selected", "recommended", "active"}:
        return 1
    if text in {"no", "n", "false", "0", "inactive", ""}:
        return 0
    return None


def _normalize_for_module(module_name: str, field: str, value: Any) -> Any:
    if field in numeric_fields(module_name):
        return _to_float(value)
    if field in bool_fields(module_name):
        return _to_bool(value)
    return _normalize_text(value)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def _sequence_id(prefix: str, table: str, field: str) -> str:
    ensure_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT {field} FROM {table} WHERE {field} LIKE ? ORDER BY {field} DESC LIMIT 1", (f"{prefix}-%",))
    row = cur.fetchone()
    conn.close()
    if row:
        raw = str(row[field])
        match = re.search(r"(\d+)$", raw)
        if match:
            return f"{prefix}-{int(match.group(1)) + 1:06d}"
    return f"{prefix}-000001"


def _clear_cache() -> None:
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass


def _insert_or_update(table: str, id_field: str | None, key_fields: tuple[str, ...], record: dict[str, Any]) -> str:
    ensure_ready()
    conn = get_connection()
    cur = conn.cursor()

    existing = None
    if id_field and record.get(id_field):
        execute(cur, f"SELECT * FROM {table} WHERE {id_field} = ?", (record[id_field],))
        existing = _fetchone_dict(cur)
    elif key_fields:
        where = " AND ".join(f"{field} = ?" for field in key_fields)
        values = tuple(record.get(field) for field in key_fields)
        if all(values):
            execute(cur, f"SELECT * FROM {table} WHERE {where}", values)
            existing = _fetchone_dict(cur)

    fields = [f for f, v in record.items() if v is not None]
    if existing:
        update_fields = [f for f in fields if f not in set(key_fields)]
        if not update_fields:
            conn.close()
            return "skipped"
        assignments = ", ".join(f"{field} = ?" for field in update_fields)
        values = [record.get(field) for field in update_fields]
        where_key = id_field if id_field and existing.get(id_field) else key_fields[0]
        values.append(existing.get(where_key))
        execute(cur, f"UPDATE {table} SET {assignments} WHERE {where_key} = ?", values)
        action = "updated"
    else:
        placeholders = ", ".join(["?"] * len(fields))
        execute(cur, f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})", [record.get(f) for f in fields])
        action = "inserted"

    conn.commit()
    conn.close()
    _clear_cache()
    return action


# -----------------------------------------------------------------------------
# Project ID Create
# -----------------------------------------------------------------------------

def generate_next_project_id(prefix: str = "SDG", year: int | None = None) -> dict[str, Any]:
    ensure_ready()
    yy = str(year or datetime.now().year)[-2:]
    pattern = re.compile(rf"^{re.escape(prefix)}-{yy}-(\d{{3}})$", re.IGNORECASE)
    conn = get_connection()
    cur = conn.cursor()
    ids: list[str] = []
    for sql in [
        "SELECT project_id FROM sales_projects",
        "SELECT project_id FROM operation_orders",
        "SELECT project_id FROM project_items",
        "SELECT project_id FROM supplier_price_comparisons",
        "SELECT project_id FROM client_quotation_headers",
        "SELECT project_id FROM order_details",
        "SELECT project_id FROM sample_tracking",
    ]:
        try:
            execute(cur, sql)
            ids.extend(str(row["project_id"]) for row in cur.fetchall() if row["project_id"])
        except Exception:
            pass
    conn.close()
    max_seq = 0
    for value in ids:
        match = pattern.match(str(value).strip())
        if match:
            max_seq = max(max_seq, int(match.group(1)))
    next_seq = max_seq + 1
    return {
        "project_id": f"{prefix}-{yy}-{next_seq:03d}",
        "project_id_year": yy,
        "project_id_sequence": f"{next_seq:03d}",
        "checked_records": len(set(ids)),
        "created_at": now_iso(),
    }


# -----------------------------------------------------------------------------
# Supplier resolution and upserts
# -----------------------------------------------------------------------------

def get_supplier_by_code_or_name(supplier_code: str | None = None, supplier_name: str | None = None) -> dict[str, Any] | None:
    ensure_ready()
    supplier_code = _normalize_text(supplier_code)
    supplier_name = _normalize_text(supplier_name)
    conn = get_connection()
    cur = conn.cursor()
    row = None
    if supplier_code:
        execute(cur, "SELECT * FROM supplier_details WHERE lower(supplier_code) = lower(?) LIMIT 1", (supplier_code,))
        row = _fetchone_dict(cur)
    if row is None and supplier_name:
        execute(cur, "SELECT * FROM supplier_details WHERE lower(supplier_name) = lower(?) LIMIT 1", (supplier_name,))
        row = _fetchone_dict(cur)
    conn.close()
    return row


def ensure_supplier(supplier_name: str | None, supplier_code: str | None = None, operator: str | None = None) -> str | None:
    supplier_name = _normalize_text(supplier_name)
    supplier_code = _normalize_text(supplier_code)
    if not supplier_name and not supplier_code:
        return None
    existing = get_supplier_by_code_or_name(supplier_code=supplier_code, supplier_name=supplier_name)
    if existing:
        return existing.get("supplier_id")
    supplier_id = _sequence_id("SUP", "supplier_details", "supplier_id")
    now = now_iso()
    record = {
        "supplier_id": supplier_id,
        "supplier_code": supplier_code,
        "supplier_name": supplier_name or supplier_code,
        "source_channel": "Imported",
        "created_at": now,
        "created_by": operator,
        "last_updated_at": now,
        "last_updated_by": operator,
    }
    _insert_or_update("supplier_details", "supplier_id", ("supplier_id",), record)
    return supplier_id


def _auto_quote_version(project_id: str) -> str:
    ensure_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, "SELECT quote_version FROM client_quotation_headers WHERE project_id = ?", (project_id,))
    max_version = 0
    for row in cur.fetchall():
        match = re.search(r"(\d+)$", str(row["quote_version"] or ""))
        if match:
            max_version = max(max_version, int(match.group(1)))
    conn.close()
    return f"V{max_version + 1}"


def _prepare_record(module_name: str, raw: dict[str, Any], operator: str | None = None) -> dict[str, Any]:
    spec = MODULES[module_name]
    record = {field.name: _normalize_for_module(module_name, field.name, raw.get(field.name)) for field in spec.fields}
    now = now_iso()

    if module_name == "Supplier Details":
        existing = None
        if not record.get("supplier_id"):
            existing = get_supplier_by_code_or_name(record.get("supplier_code"), record.get("supplier_name"))
            record["supplier_id"] = existing.get("supplier_id") if existing else _sequence_id("SUP", spec.table, "supplier_id")
        else:
            existing = get_supplier_by_code_or_name(record.get("supplier_code"), record.get("supplier_name"))
        if existing and not record.get("supplier_name"):
            record["supplier_name"] = existing.get("supplier_name")
        if not existing:
            record["created_at"] = record.get("created_at") or now
            record["created_by"] = record.get("created_by") or operator
        record["last_updated_at"] = now
        record["last_updated_by"] = operator

    elif module_name == "Project Items":
        record["created_at"] = record.get("created_at") or now
        record["created_by"] = record.get("created_by") or operator
        record["last_updated_at"] = now
        record["last_updated_by"] = operator

    elif module_name == "Supplier Price Comparison":
        record["supplier_id"] = record.get("supplier_id") or ensure_supplier(record.get("supplier_name"), record.get("supplier_code"), operator)
        if not record.get("supplier_quote_id"):
            record["supplier_quote_id"] = _new_id("SPQ")
        selected = bool(record.get("selected_supplier"))
        recommended = bool(record.get("recommended_supplier"))
        record["comparison_status"] = "Completed" if selected or recommended else "In Progress"
        record["imported_at"] = record.get("imported_at") or now
        record["imported_by"] = record.get("imported_by") or operator

    elif module_name == "Client Quotation Header":
        if not record.get("client_quote_id"):
            record["client_quote_id"] = _new_id("CQ")
        if not record.get("quote_version") and record.get("project_id"):
            record["quote_version"] = _auto_quote_version(str(record["project_id"]))
        record["quote_status"] = record.get("quote_status") or "Draft"
        record["created_at"] = record.get("created_at") or now
        record["created_by"] = record.get("created_by") or operator
        record["last_updated_at"] = now
        record["last_updated_by"] = operator

    elif module_name == "Client Quotation Lines":
        if not record.get("client_quote_line_id"):
            record["client_quote_line_id"] = _new_id("CQL")
        qty = _to_float(record.get("quantity_basis")) or 0
        client_price = _to_float(record.get("client_unit_price")) or 0
        supplier_cost = _to_float(record.get("supplier_unit_cost")) or 0
        extra = _to_float(record.get("estimated_extra_cost")) or 0
        record["estimated_revenue"] = client_price * qty if qty or client_price else record.get("estimated_revenue")
        record["estimated_supplier_cost"] = supplier_cost * qty if qty or supplier_cost else record.get("estimated_supplier_cost")
        if record.get("estimated_revenue") is not None and record.get("estimated_supplier_cost") is not None:
            gp = float(record.get("estimated_revenue") or 0) - float(record.get("estimated_supplier_cost") or 0) - extra
            record["estimated_gp"] = gp
            revenue = float(record.get("estimated_revenue") or 0)
            record["estimated_gp_percent"] = (gp / revenue * 100) if revenue else None

    elif module_name == "Index Config":
        if not record.get("index_config_id"):
            record["index_config_id"] = _new_id("IDXCFG")
        record["fetch_enabled"] = record.get("fetch_enabled") if record.get("fetch_enabled") is not None else 0
        record["active"] = record.get("active") if record.get("active") is not None else 1

    elif module_name == "Daily Market Indices":
        if not record.get("daily_index_id"):
            record["daily_index_id"] = _new_id("DIDX")
        record["index_date"] = record.get("index_date") or date.today().isoformat()
        record["fetch_status"] = record.get("fetch_status") or "Manual"
        record["last_updated_at"] = now
        record["updated_by"] = record.get("updated_by") or operator
        _apply_previous_index_values(record)

    elif module_name == "Index Snapshot":
        if not record.get("index_snapshot_id"):
            record["index_snapshot_id"] = _new_id("SNAP")
        record["locked_at"] = record.get("locked_at") or now
        record["locked_by"] = record.get("locked_by") or operator

    elif module_name == "Freight Index":
        if not record.get("freight_index_id"):
            record["freight_index_id"] = _new_id("FRT")
        record["index_date"] = record.get("index_date") or date.today().isoformat()

    elif module_name == "Order Details":
        if not record.get("order_detail_id"):
            record["order_detail_id"] = _new_id("OD")
        record["supplier_id"] = record.get("supplier_id") or ensure_supplier(record.get("supplier_name"), record.get("supplier_code"), operator)
        record["imported_at"] = record.get("imported_at") or now
        record["imported_by"] = record.get("imported_by") or operator
        _recalculate_order_record(record)

    elif module_name == "Order Costs":
        if not record.get("cost_id"):
            record["cost_id"] = _new_id("COST")
        record["created_at"] = record.get("created_at") or now
        record["created_by"] = record.get("created_by") or operator

    elif module_name == "Sample Tracking":
        if not record.get("sample_id"):
            record["sample_id"] = _new_id("SMP")
        record["supplier_id"] = record.get("supplier_id") or ensure_supplier(record.get("supplier_name"), record.get("supplier_code"), operator)
        record["last_updated_at"] = now
        record["last_updated_by"] = operator

    return record


def _apply_previous_index_values(record: dict[str, Any]) -> None:
    if not record.get("index_name") or not record.get("index_date"):
        return
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT index_value
        FROM daily_market_indices
        WHERE index_name = ? AND index_date < ?
        ORDER BY index_date DESC
        LIMIT 1
        """,
        (record.get("index_name"), record.get("index_date")),
    )
    row = _fetchone_dict(cur)
    conn.close()
    previous = _to_float(row.get("index_value")) if row else None
    value = _to_float(record.get("index_value"))
    record["previous_value"] = previous
    if previous is not None and value is not None:
        record["change_value"] = value - previous
        record["change_percent"] = ((value - previous) / previous * 100) if previous else None


def _extra_cost_for_order(order_no: str | None, project_id: str | None, item_code: str | None) -> float:
    if not order_no and not project_id:
        return 0.0
    ensure_ready()
    clauses = []
    params: list[Any] = []
    if order_no:
        clauses.append("order_no = ?")
        params.append(order_no)
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if item_code:
        clauses.append("(item_code = ? OR item_code IS NULL OR item_code = '')")
        params.append(item_code)
    where = " AND ".join(clauses) if clauses else "1=0"
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT cost_amount FROM order_costs WHERE {where}", tuple(params))
    total = sum(_to_float(row["cost_amount"]) or 0 for row in cur.fetchall())
    conn.close()
    return total


def _recalculate_order_record(record: dict[str, Any]) -> dict[str, Any]:
    qty = _to_float(record.get("order_qty")) or 0
    client_unit = _to_float(record.get("client_unit_price")) or 0
    supplier_unit = _to_float(record.get("supplier_unit_cost")) or 0
    sales_revenue = client_unit * qty if qty or client_unit else _to_float(record.get("sales_revenue"))
    supplier_cost = supplier_unit * qty if qty or supplier_unit else _to_float(record.get("supplier_cost"))
    extra_cost = _extra_cost_for_order(record.get("order_no"), record.get("project_id"), record.get("item_code"))
    if sales_revenue is not None:
        record["sales_revenue"] = sales_revenue
    if supplier_cost is not None:
        record["supplier_cost"] = supplier_cost
    record["extra_cost"] = extra_cost
    if sales_revenue is not None and supplier_cost is not None:
        gp = float(sales_revenue or 0) - float(supplier_cost or 0) - extra_cost
        record["gross_profit"] = gp
        record["gross_profit_percent"] = (gp / float(sales_revenue) * 100) if sales_revenue else None
    return record


def upsert_module_record(module_name: str, raw: dict[str, Any], operator: str | None = None) -> str:
    spec = MODULES[module_name]
    record = _prepare_record(module_name, raw, operator=operator)
    for field in required_fields(module_name):
        if record.get(field) is None:
            raise ValueError(f"Missing required field: {field}")
    action = _insert_or_update(spec.table, spec.id_field, spec.key_fields, record)
    if module_name in {"Order Costs", "Order Details"}:
        recalculate_order_details(record.get("order_no"), record.get("project_id"), record.get("item_code"))
    return action


def recalculate_order_details(order_no: str | None = None, project_id: str | None = None, item_code: str | None = None) -> None:
    ensure_ready()
    clauses = []
    params: list[Any] = []
    if order_no:
        clauses.append("order_no = ?")
        params.append(order_no)
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if item_code:
        clauses.append("item_code = ?")
        params.append(item_code)
    where = " AND ".join(clauses) if clauses else "1=1"
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT * FROM order_details WHERE {where}", tuple(params))
    rows = _rows_to_dicts(cur.fetchall())
    for row in rows:
        updated = _recalculate_order_record(row)
        execute(
            cur,
            """
            UPDATE order_details
            SET sales_revenue = ?, supplier_cost = ?, extra_cost = ?, gross_profit = ?, gross_profit_percent = ?
            WHERE order_detail_id = ?
            """,
            (
                updated.get("sales_revenue"),
                updated.get("supplier_cost"),
                updated.get("extra_cost"),
                updated.get("gross_profit"),
                updated.get("gross_profit_percent"),
                updated.get("order_detail_id"),
            ),
        )
    conn.commit()
    conn.close()
    _clear_cache()


# -----------------------------------------------------------------------------
# Import support
# -----------------------------------------------------------------------------

def guess_mapping(columns: list[str], module_name: str) -> dict[str, str | None]:
    normalized = {re.sub(r"[^a-z0-9]", "", str(col).lower()): col for col in columns}
    mapping: dict[str, str | None] = {}
    display_map = field_display_map(module_name)
    for field in import_field_names(module_name):
        keys = {
            re.sub(r"[^a-z0-9]", "", field.lower()),
            re.sub(r"[^a-z0-9]", "", display_map.get(field, field).lower()),
        }
        match = None
        for key in keys:
            if key in normalized:
                match = normalized[key]
                break
        mapping[field] = match
    return mapping


def apply_import_mapping(df: pd.DataFrame, mapping: dict[str, str | None], module_name: str, source_file: str) -> tuple[pd.DataFrame, int]:
    rows: list[dict[str, Any]] = []
    blank_rows = 0
    required = import_required_fields(module_name)
    for idx, row in df.iterrows():
        item: dict[str, Any] = {field: None for field in field_names(module_name)}
        for target, source_col in mapping.items():
            if source_col and source_col in df.columns:
                item[target] = row[source_col]
        item["source_file"] = source_file
        item["_source_row_number"] = idx + 2
        if all(_normalize_text(item.get(field)) is None for field in required):
            blank_rows += 1
            continue
        rows.append(item)
    return pd.DataFrame(rows), blank_rows


def validate_import_dataframe(mapped_df: pd.DataFrame, module_name: str) -> dict[str, Any]:
    errors: list[str] = []
    required = import_required_fields(module_name)
    if mapped_df.empty:
        return {"ready": False, "errors": ["No records to import."], "missing_required_rows": 0, "total": 0}
    missing_required_rows = 0
    for _, row in mapped_df.iterrows():
        missing = [field for field in required if _normalize_text(row.get(field)) is None]
        if missing:
            missing_required_rows += 1
            errors.append(f"Row {int(row.get('_source_row_number') or 0)}: missing {', '.join(missing)}")
    return {
        "ready": missing_required_rows == 0,
        "errors": errors,
        "missing_required_rows": missing_required_rows,
        "total": int(len(mapped_df)),
    }


def import_module_dataframe(mapped_df: pd.DataFrame, module_name: str, operator: str | None = None, source_file: str | None = None) -> dict[str, int]:
    inserted = 0
    updated = 0
    failed = 0
    errors: list[str] = []
    for _, row in mapped_df.iterrows():
        try:
            raw = {field: row.get(field) for field in field_names(module_name)}
            action = upsert_module_record(module_name, raw, operator=operator)
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
        except Exception as exc:
            failed += 1
            errors.append(f"Row {int(row.get('_source_row_number') or 0)}: {exc}")
    write_import_batch(
        {
            "batch_id": new_batch_id(),
            "source_file": source_file or "extension_import.xlsx",
            "import_time": now_iso(),
            "imported_by": operator,
            "import_type": module_name,
            "new_count": inserted,
            "update_count": updated,
            "failed_count": failed,
            "notes": "; ".join(errors[:5]) if errors else "extension import",
        }
    )
    return {"inserted": inserted, "updated": updated, "failed": failed, "errors_count": len(errors)}


# -----------------------------------------------------------------------------
# Reads and summaries
# -----------------------------------------------------------------------------

def list_module_records(module_name: str, limit: int = 500, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ensure_ready()
    spec = MODULES[module_name]
    filters = filters or {}
    clauses: list[str] = []
    params: list[Any] = []
    for field, value in filters.items():
        if value in (None, ""):
            continue
        if field.endswith("__contains"):
            field_name = field.replace("__contains", "")
            clauses.append(f"lower({field_name}) LIKE lower(?)")
            params.append(f"%{value}%")
        else:
            clauses.append(f"{field} = ?")
            params.append(value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order_field = "last_updated_at" if any(f.name == "last_updated_at" for f in spec.fields) else "created_at" if any(f.name == "created_at" for f in spec.fields) else spec.fields[0].name
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT * FROM {spec.table} {where} ORDER BY {order_field} DESC LIMIT ?", tuple(params + [int(limit)]))
    rows = _rows_to_dicts(cur.fetchall())
    conn.close()
    if module_name == "Order Details":
        for row in rows:
            _recalculate_order_record(row)
    if module_name == "Supplier Details":
        rows = [_decorate_supplier_active(row) for row in rows]
    return rows


def _decorate_supplier_active(supplier: dict[str, Any]) -> dict[str, Any]:
    supplier_id = supplier.get("supplier_id")
    supplier_code = supplier.get("supplier_code")
    supplier_name = supplier.get("supplier_name")
    conn = get_connection()
    cur = conn.cursor()
    clauses = []
    params: list[Any] = []
    if supplier_id:
        clauses.append("supplier_id = ?")
        params.append(supplier_id)
    if supplier_code:
        clauses.append("lower(supplier_code) = lower(?)")
        params.append(supplier_code)
    if supplier_name:
        clauses.append("lower(supplier_name) = lower(?)")
        params.append(supplier_name)
    where = " OR ".join(clauses) if clauses else "1=0"

    execute(
        cur,
        f"""
        SELECT order_no, project_id, shipment_status, payment_status, production_status, imported_at
        FROM order_details
        WHERE ({where})
        ORDER BY imported_at DESC
        LIMIT 500
        """,
        tuple(params),
    )
    linked = _rows_to_dicts(cur.fetchall())

    execute(cur, f"SELECT COUNT(*) AS count_value FROM supplier_price_comparisons WHERE ({where})", tuple(params))
    price_row = _fetchone_dict(cur) or {}
    price_count = int(price_row.get("count_value") or 0)

    conn.close()

    closed_tokens = {"paid", "closed", "cancelled", "canceled", "shipped complete", "complete"}
    active_orders = []
    for row in linked:
        status_text = " ".join(str(row.get(k) or "") for k in ["shipment_status", "payment_status", "production_status"]).lower()
        if not any(token in status_text for token in closed_tokens):
            active_orders.append(row)

    supplier["active_status"] = "Active" if active_orders else "Inactive"
    supplier["active_reason"] = ", ".join(row.get("order_no") or "" for row in active_orders[:3]) if active_orders else "No open linked order"
    supplier["last_order_no"] = linked[0].get("order_no") if linked else supplier.get("last_order_no")
    supplier["last_project_id"] = linked[0].get("project_id") if linked else supplier.get("last_project_id")
    supplier["price_comparison_count"] = price_count
    supplier["order_count"] = len(linked)

    risk_parts = []
    if supplier.get("quality_risk"):
        risk_parts.append(f"Quality: {supplier.get('quality_risk')}")
    if supplier.get("commercial_risk"):
        risk_parts.append(f"Commercial: {supplier.get('commercial_risk')}")
    if price_count == 0:
        risk_parts.append("No supplier quotation yet")
    if active_orders:
        risk_parts.append(f"Open orders: {len(active_orders)}")
    supplier["risk_summary"] = "; ".join(risk_parts) if risk_parts else "No major risk flag"
    return supplier


def get_project_extension_rows(project_id: str) -> dict[str, list[dict[str, Any]]]:
    return {
        "Project Items": list_module_records("Project Items", filters={"project_id": project_id}),
        "Supplier Price Comparison": list_module_records("Supplier Price Comparison", filters={"project_id": project_id}),
        "Client Quotation Header": list_module_records("Client Quotation Header", filters={"project_id": project_id}),
        "Client Quotation Lines": list_module_records("Client Quotation Lines", filters={"project_id": project_id}),
        "Index Snapshot": list_module_records("Index Snapshot", filters={"project_id": project_id}),
        "Order Details": list_module_records("Order Details", filters={"project_id": project_id}),
        "Order Costs": list_module_records("Order Costs", filters={"project_id": project_id}),
        "Sample Tracking": list_module_records("Sample Tracking", filters={"project_id": project_id}),
    }


def get_operation_extension_rows(order_no: str, project_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    rows = {
        "Order Details": list_module_records("Order Details", filters={"order_no": order_no}),
        "Order Costs": list_module_records("Order Costs", filters={"order_no": order_no}),
    }
    if project_id:
        rows["Client Quotation Header"] = list_module_records("Client Quotation Header", filters={"project_id": project_id})
        rows["Client Quotation Lines"] = list_module_records("Client Quotation Lines", filters={"project_id": project_id})
        rows["Index Snapshot"] = list_module_records("Index Snapshot", filters={"project_id": project_id})
    return rows


def get_related_suppliers(record_type: str, record_id: str, project_id: str | None = None) -> list[dict[str, Any]]:
    ensure_ready()
    project_id = project_id or (record_id if record_type == "Sales" else None)
    supplier_ids: set[str] = set()
    supplier_names: set[str] = set()
    conn = get_connection()
    cur = conn.cursor()
    queries: list[tuple[str, tuple[Any, ...]]] = []
    if project_id:
        queries.extend([
            ("SELECT supplier_id, supplier_name FROM supplier_price_comparisons WHERE project_id = ?", (project_id,)),
            ("SELECT supplier_id, supplier_name FROM order_details WHERE project_id = ?", (project_id,)),
            ("SELECT supplier_id, supplier_name FROM sample_tracking WHERE project_id = ?", (project_id,)),
        ])
    if record_type == "Operation":
        queries.append(("SELECT supplier_id, supplier_name FROM order_details WHERE order_no = ?", (record_id,)))
    for sql, params in queries:
        execute(cur, sql, params)
        for raw_row in cur.fetchall():
            row = dict(raw_row)
            if row.get("supplier_id"):
                supplier_ids.add(str(row["supplier_id"]))
            if row.get("supplier_name"):
                supplier_names.add(str(row["supplier_name"]))
    clauses = []
    params: list[Any] = []
    if supplier_ids:
        placeholders = ", ".join(["?"] * len(supplier_ids))
        clauses.append(f"supplier_id IN ({placeholders})")
        params.extend(sorted(supplier_ids))
    if supplier_names:
        placeholders = ", ".join(["?"] * len(supplier_names))
        clauses.append(f"supplier_name IN ({placeholders})")
        params.extend(sorted(supplier_names))
    if not clauses:
        conn.close()
        return []
    execute(cur, f"SELECT * FROM supplier_details WHERE {' OR '.join(clauses)}", tuple(params))
    rows = [_decorate_supplier_active(dict(row)) for row in cur.fetchall()]
    conn.close()
    return rows


def today_indices() -> list[dict[str, Any]]:
    today = date.today().isoformat()
    rows = list_module_records("Daily Market Indices", limit=200, filters={"index_date": today})
    if rows:
        return rows
    return []


def seed_default_index_config() -> int:
    ensure_ready()
    inserted = 0
    for category, name, display, unit, source, url, method, fallback in DEFAULT_INDEX_CONFIG:
        existing = list_module_records("Index Config", limit=1, filters={"index_name": name})
        if existing:
            continue
        upsert_module_record(
            "Index Config",
            {
                "index_category": category,
                "index_name": name,
                "display_name": display,
                "unit": unit,
                "source_name": source,
                "source_url": url,
                "fetch_enabled": 0,
                "fetch_method": method,
                "fallback_method": fallback,
                "active": 1,
            },
            operator="System",
        )
        inserted += 1
    return inserted


def carry_forward_daily_indices(target_date: str | None = None, operator: str = "System") -> dict[str, int]:
    target_date = target_date or date.today().isoformat()
    seed_default_index_config()
    configs = [row for row in list_module_records("Index Config", limit=500) if int(row.get("active") or 0) == 1]
    created = 0
    skipped = 0
    for cfg in configs:
        existing = list_module_records("Daily Market Indices", limit=1, filters={"index_date": target_date, "index_name": cfg.get("index_name")})
        if existing:
            skipped += 1
            continue
        previous = _latest_daily_index_before(cfg.get("index_name"), target_date)
        if previous:
            upsert_module_record(
                "Daily Market Indices",
                {
                    "index_date": target_date,
                    "index_category": cfg.get("index_category"),
                    "index_name": cfg.get("index_name"),
                    "index_value": previous.get("index_value"),
                    "unit": cfg.get("unit"),
                    "source_name": previous.get("source_name") or cfg.get("source_name"),
                    "source_url": previous.get("source_url") or cfg.get("source_url"),
                    "fetch_method": "Carry Forward",
                    "fetch_status": "Carry Forward",
                    "error_message": "No new value; carried forward from previous available record.",
                },
                operator=operator,
            )
            created += 1
        else:
            skipped += 1
    return {"created": created, "skipped": skipped}


def _latest_daily_index_before(index_name: str | None, before_date: str) -> dict[str, Any] | None:
    if not index_name:
        return None
    ensure_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT * FROM daily_market_indices
        WHERE index_name = ? AND index_date < ?
        ORDER BY index_date DESC
        LIMIT 1
        """,
        (index_name, before_date),
    )
    row = _fetchone_dict(cur)
    conn.close()
    return row


def build_summary_metrics(rows: Iterable[dict[str, Any]], field: str | None = None) -> dict[str, Any]:
    items = list(rows)
    metrics = {"Total": len(items)}
    if field:
        metrics.update({str(row.get(field) or "-"): 0 for row in items})
        for row in items:
            metrics[str(row.get(field) or "-")] += 1
    return metrics
