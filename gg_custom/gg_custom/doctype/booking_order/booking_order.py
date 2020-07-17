# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

from gg_custom.api.booking_order import get_history


class BookingOrder(Document):
    def onload(self):
        if self.docstatus == 1:
            self.set_onload("dashboard_info", _get_dashboard_info(self))

    def validate(self):
        if self.status == "Unloaded" and not self.current_station:
            frappe.throw(
                frappe._("Cannot unload without a {}".format(frappe.bold("Station")))
            )
        if self.status == "In Transit" and not self.last_shipping_order:
            frappe.throw(
                frappe._(
                    "Cannot move Booking Order without a {}".format(
                        frappe.bold("Shipping Order")
                    )
                )
            )

    def before_insert(self):
        self.status = "Draft"

    def before_save(self):
        self.total_amount = sum([x.charge_amount for x in self.charges])

    def before_submit(self):
        self.last_shipping_order = None
        self.current_station = self.source_station
        self.status = "Booked"
        self.payment_status = "Unbilled"

    def before_cancel(self):
        if self.status != "Booked":
            frappe.throw(frappe._("Cannot cancel an order when it is in progress"))
        self.status = "Cancelled"
        self.payment_status = None

    def before_update_after_submit(self):
        if self.status in ["Collected"]:
            self.current_station = None

    def set_as_completed(self):
        if self.status != "Unloaded":
            frappe.throw(
                frappe._("Booking Order can only be delivered when it has stopped.")
            )
        if self.current_station != self.destination_station:
            frappe.throw(
                frappe._(
                    "Booking Order can only be delivered when the goods are Unloaded "
                    "at its Destination Station."
                )
            )
        self.status = "Collected"
        self.save()


def _get_dashboard_info(doc):
    invoice = frappe.db.sql(
        """
            SELECT
                SUM(grand_total) AS grand_total,
                SUM(outstanding_amount) AS outstanding_amount
            FROM `tabSales Invoice` WHERE
                docstatus = 1 AND gg_booking_order = %(booking_order)s
        """,
        values={"booking_order": doc.name},
        as_dict=1,
    )[0]
    return {
        "invoice": invoice,
        "history": get_history(doc.name),
    }
