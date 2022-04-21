import frappe

from gg_custom.api.booking_order import get_payment_entry_from_invoices
from gg_custom.api.booking_party import get_empty_payment_entry


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    supplier = frappe.get_cached_value("Shipping Vendor", source_name, "supplier")
    invoices = [
        frappe.get_cached_doc("Purchase Invoice", x.get("name"))
        for x in frappe.get_all(
            "Purchase Invoice",
            filters={
                "docstatus": 1,
                "supplier": supplier,
                "outstanding_amount": [">", 0],
            },
            order_by="posting_date, name",
        )
    ]

    if not invoices:
        return get_empty_payment_entry("Supplier", supplier)

    return get_payment_entry_from_invoices("Purchase Invoice", invoices)


def update_supplier(name):
    doc = frappe.get_doc("Shipping Vendor", name)
    if doc and doc.supplier:
        supplier = frappe.get_cached_doc("Supplier", doc.supplier)
        for shipping_vendor_field, supplier_field in [
            ("shipping_vendor_name", "supplier_name"),
            ("primary_address", "supplier_primary_address"),
        ]:
            if supplier and (
                supplier.get(shipping_vendor_field) != doc.get(shipping_vendor_field)
            ):
                frappe.db.set_value(
                    "Supplier",
                    doc.supplier,
                    supplier_field,
                    doc.get(shipping_vendor_field),
                )
