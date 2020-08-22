# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from toolz.curried import merge

from gg_custom.api.booking_order import (
    get_history,
    make_sales_invoice,
    get_loading_conversion_factor,
)


class BookingOrder(Document):
    def onload(self):
        if self.docstatus == 1:
            self.set_onload("dashboard_info", _get_dashboard_info(self))
            self.set_onload("deliverable", _get_deliverable(self))

    def validate(self):
        if not self.freight or not self.freight_total:
            frappe.throw(frappe._("Freight cannot be empty or zero"))

    def before_insert(self):
        self.status = "Draft"

    def before_save(self):
        self.set_totals()

    def before_submit(self):
        self.status = "Booked"
        self.payment_status = "Unbilled"

    def before_cancel(self):
        if self.payment_status == "Paid":
            frappe.throw(
                frappe._("Cannot cancel an order when it has already been Paid")
            )
        self.status = "Cancelled"
        self.payment_status = None

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
        ).insert(ignore_permissions=True)
        if self.auto_bill_to:
            frappe.flags.args = {
                "bill_to": self.auto_bill_to.lower(),
                "taxes_and_charges": None,
            }
            invoice = make_sales_invoice(self.name)
            invoice.insert(ignore_permissions=True)
            invoice.submit()

    def on_cancel(self):
        for (log_name,) in frappe.get_all(
            "Booking Log", filters={"booking_order": self.name}, as_list=1
        ):
            frappe.delete_doc("Booking Log", log_name, ignore_permissions=True)

        for (si_name,) in frappe.get_all(
            "Sales Invoice",
            filters={"docstatus": 1, "gg_booking_order": self.name},
            as_list=1,
        ):
            si = frappe.get_doc("Sales Invoice", si_name)
            if si.status == "Paid":
                frappe.throw(
                    frappe._(
                        "Cannot cancel Paid invoice {}".format(
                            frappe.get_desk_link("Sales Invoice", si_name)
                        )
                    )
                )
            si.cancel()

    def set_totals(self):
        self.freight_total = sum([x.amount for x in self.freight])
        self.charge_total = sum([x.charge_amount for x in self.charges])
        self.total_amount = self.freight_total + self.charge_total

    def deliver(self, unit, qty, posting_datetime=None):
        deliverable = _get_deliverable(self)
        if qty > deliverable.get("qty"):
            frappe.throw(frappe._("Cannot deliver more than {} units".format(qty)))

        conversion_factor = get_loading_conversion_factor(
            qty, unit, self.no_of_packages, self.weight_actual
        )
        if not conversion_factor:
            frappe.throw(frappe._("Invalid conversion factor"))

        no_of_packages = self.no_of_packages * conversion_factor
        weight_actual = self.weight_actual * conversion_factor
        goods_value = self.goods_value * conversion_factor

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
        ).insert(ignore_permissions=True)

        self.set_as_completed()

    def set_as_completed(self):
        delivered = _get_delivered_packages(self)
        if self.no_of_packages == delivered.get(
            "no_of_packages"
        ) and self.weight_actual == delivered.get("weight_actual"):
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


def _get_deliverable(doc):
    result = frappe.get_all(
        "Booking Log",
        filters={"booking_order": doc.name, "station": doc.destination_station,},
        fields=[
            "sum(no_of_packages) as no_of_packages",
            "sum(weight_actual) as weight_actual",
            "max(loading_unit) as unit",
        ],
    )[0]

    if result:
        if result.get("unit") == "Packages":
            return merge(result, {"qty": result.get("no_of_packages")})
        if result.get("unit") == "Weight":
            return merge(result, {"qty": result.get("weight_actual")})

    return {"qty": 0, "unit": None}


def _get_delivered_packages(doc):
    return (
        frappe.get_all(
            "Booking Log",
            filters={"activity": "Collected", "booking_order": doc.name},
            fields=[
                "-sum(no_of_packages) as no_of_packages",
                "-sum(weight_actual) as weight_actual",
            ],
            as_list=1,
        )[0]
        or {}
    )

