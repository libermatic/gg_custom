import frappe


def execute():
    frappe.db.set_single_value("Accounts Settings", "delete_linked_ledger_entries", 1)
