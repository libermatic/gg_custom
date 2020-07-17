from __future__ import unicode_literals
import frappe


def on_submit(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(doc)


def on_cancel(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(doc, cancel=True)


def _update_booking_order(si, cancel=False):
    bo = frappe.get_cached_doc("Booking Order", si.gg_booking_order)
    bo.payment_status = "Unpaid" if not cancel else "Unbilled"
    bo.save()
