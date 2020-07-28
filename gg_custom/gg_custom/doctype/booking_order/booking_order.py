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
            self.set_onload(
                "no_of_deliverable_packages", _get_deliverable_packages(self)
            )

    def before_insert(self):
        self.status = "Draft"

    def before_save(self):
        self.total_amount = sum([x.charge_amount for x in self.charges])

    def before_submit(self):
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

    def on_submit(self):
        frappe.get_doc(
            {
                "doctype": "Booking Log",
                "posting_datetime": self.booking_datetime,
                "booking_order": self.name,
                "station": self.source_station,
                "activity": "Booked",
                "no_of_packages": self.no_of_packages,
                "weight_actual": self.weight_actual,
                "goods_value": self.goods_value,
            }
        ).insert()

    def on_cancel(self):
        for (log_name,) in frappe.get_all(
            "Booking Log", filters={"booking_order": self.name}, as_list=1
        ):
            frappe.delete_doc("Booking Log", log_name)

    def deliver(self, no_of_packages, posting_datetime=None):
        no_of_deliverable_packages = _get_deliverable_packages(self)
        if no_of_packages > no_of_deliverable_packages:
            frappe.throw(
                frappe._(
                    "Cannot deliver more than {} packages".format(
                        no_of_deliverable_packages
                    )
                )
            )

        weight_actual = (
            self.weight_actual / self.no_of_packages * no_of_packages
            if self.no_of_packages
            else 0
        )
        goods_value = (
            self.goods_value / self.no_of_packages * no_of_packages
            if self.no_of_packages
            else 0
        )

        _posting_datetime = posting_datetime or frappe.utils.now()
        frappe.get_doc(
            {
                "doctype": "Booking Log",
                "posting_datetime": _posting_datetime,
                "booking_order": self.name,
                "station": self.destination_station,
                "activity": "Collected",
                "no_of_packages": -no_of_packages,
                "weight_actual": -weight_actual,
                "goods_value": -goods_value,
            }
        ).insert()

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


def _get_deliverable_packages(doc):
    return (
        frappe.get_all(
            "Booking Log",
            filters={"booking_order": doc.name, "station": doc.destination_station},
            fields=["sum(no_of_packages) as no_of_packages"],
            as_list=1,
            debug=1,
        )[0][0]
        or 0
    )

