import frappe


def execute():
    frappe.db.set_value("Accounts Settings", None, "delete_linked_ledger_entries", 1)
