from __future__ import unicode_literals
import frappe
from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency
from erpnext.accounts.doctype.journal_entry.journal_entry import (
    get_default_bank_cash_account,
)

from gg_custom.api.booking_order import get_payment_entry_from_invoices


def get_party_open_orders(party):
    sales_invoices = [
        frappe.get_cached_doc("Sales Invoice", x.get("name"))
        for x in frappe.db.sql(
            """
                SELECT name FROM `tabSales Invoice`
                WHERE docstatus = 1 AND outstanding_amount > 0 AND customer = %(customer)s
            """,
            values={
                "customer": frappe.get_cached_value("Booking Party", party, "customer")
            },
            as_dict=1,
        )
    ]

    booking_orders = [
        frappe.get_cached_doc("Booking Order", name)
        for name in set([x.gg_booking_order for x in sales_invoices if x])
    ]

    return {"booking_orders": booking_orders, "sales_invoices": sales_invoices}


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    customer = frappe.get_cached_value("Booking Party", source_name, "customer")
    invoices = [
        frappe.get_cached_doc("Sales Invoice", x.get("name"))
        for x in frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "customer": customer,
                "outstanding_amount": [">", 0],
            },
            order_by="posting_date, name",
        )
    ]

    if not invoices:
        return get_empty_payment_entry("Customer", customer)

    return get_payment_entry_from_invoices(invoices)


def get_empty_payment_entry(party_type, party):
    company = frappe.db.get_single_value("GG Custom Settings", "company")
    if not company:
        frappe.throw(frappe._("Setup incomplete in GG Custom Settings"))

    if party_type not in ["Customer", "Supplier"]:
        frappe.throw(f"Invalid party type: {party_type}")

    mode_of_payment = "Cash"
    company_account = get_default_bank_cash_account(
        company,
        "Cash",
        mode_of_payment=mode_of_payment,
    )
    party_account = get_party_account(party_type, party, company)
    party_account_currency = get_account_currency(party_account)

    pe = frappe.new_doc("Payment Entry")
    pe.update(
        {
            "doctype": "Payment Entry",
            "payment_type": "Receive" if party_type == "Customer" else "Pay",
            "company": company,
            "cost_center": frappe.get_cached_value("Company", company, "cost_center"),
            "posting_date": frappe.utils.nowdate(),
            "mode_of_payment": mode_of_payment,
            "party_type": party_type,
            "party": party,
            "paid_from": party_account
            if party_type == "Customer"
            else company_account.account,
            "paid_to": company_account.account
            if party_type == "Customer"
            else party_account,
            "paid_from_account_currency": party_account_currency
            if party_type == "Customer"
            else company_account.account_currency,
            "paid_to_account_currency": company_account.account_currency
            if party_type == "Customer"
            else party_account_currency,
            "paid_amount": 0,
            "received_amount": 0,
        }
    )
    pe.setup_party_account_field()
    pe.set_missing_values()
    if party_account and company_account:
        pe.set_exchange_rate()
        pe.set_amounts()

    return pe


def update_customer(name):
    doc = frappe.get_doc("Booking Party", name)
    if doc and doc.customer:
        customer = frappe.get_cached_doc("Customer", doc.customer)
        for booking_party_field, customer_field in [
            ("booking_party_name", "customer_name"),
            ("primary_address", "customer_primary_address"),
        ]:
            if customer and (
                customer.get(booking_party_field) != doc.get(booking_party_field)
            ):
                frappe.db.set_value(
                    "Customer",
                    doc.customer,
                    customer_field,
                    doc.get(booking_party_field),
                )
