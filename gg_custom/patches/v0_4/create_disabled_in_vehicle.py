import frappe
from toolz.curried import merge


def execute():
    if not frappe.db.exists("Custom Field", "Vehicle-disabled"):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "Vehicle",
                "label": "Disabled",
                "fieldname": "disabled",
                "insert_after": "make",
                "fieldtype": "Check",
            }
        ).insert()
