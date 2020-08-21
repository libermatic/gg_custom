from __future__ import unicode_literals
import frappe


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
