from __future__ import unicode_literals
import frappe


def on_submit(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(doc)


def on_cancel(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(doc)


def _update_booking_order(si):
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "gg_booking_order": si.gg_booking_order},
        fields=["total", "outstanding_amount"],
    )
    bo = frappe.get_cached_doc("Booking Order", si.gg_booking_order)
    if bo.docstatus == 2:
        return
    if sum([x.get("total") for x in invoices]) < bo.total_amount:
        bo.payment_status = "Unbilled"
    elif sum([x.get("outstanding_amount") for x in invoices]) == 0:
        bo.payment_status = "Paid"
    else:
        bo.payment_status = "Unpaid"
    bo.save()
