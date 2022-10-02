# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from toolz.curried import compose, excepts, first, map, filter

from gg_custom.api.booking_order import (
    get_history,
    make_sales_invoice,
    get_loading_conversion_factor,
    get_deliverable,
)


class BookingOrder(Document):
    def onload(self):
        if self.docstatus == 1:
            self.set_onload("dashboard_info", _get_dashboard_info(self))

    def validate(self):
        if not self.freight or not self.freight_total:
            frappe.throw(frappe._("Freight cannot be empty or zero"))
        for row in self.freight:
            if row.based_on == "Packages" and not row.no_of_packages:
                frappe.throw(
                    frappe._(
                        "No of Packages cannot be zero when based on Packages in row #{}".format(
                            row.idx
                        )
                    )
                )
            if row.based_on == "Weight" and not row.weight_actual:
                frappe.throw(
                    frappe._(
                        "Weight Actual cannot be zero when based on Weight in row #{}".format(
                            row.idx
                        )
                    )
                )

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
        for row in self.freight:
            frappe.get_doc(
                {
                    "doctype": "Booking Log",
                    "posting_datetime": self.booking_datetime,
                    "booking_order": self.name,
                    "station": self.source_station,
                    "activity": "Booked",
                    "no_of_packages": row.no_of_packages,
                    "weight_actual": row.weight_actual,
                    "bo_detail": row.name,
                }
            ).insert(ignore_permissions=True)
        if self.auto_bill_to:
            frappe.flags.args = {
                "bill_to": self.auto_bill_to.lower(),
                "taxes_and_charges": None,
            }
            invoice = make_sales_invoice(
                self.name, posting_datetime=self.booking_datetime
            )
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
            si.flags.ignore_permissions = True
            si.cancel()

    def on_update_after_submit(self):
        prev_doc = self.get_doc_before_save()
        for row in self.freight:
            prev_rows = [x for x in prev_doc.freight if x.name == row.name]
            if not prev_rows or prev_rows[0].item_description != row.item_description:
                _update_loading_operations(row)
                _update_invoices(row)

    def set_totals(self):
        self.freight_total = sum([x.amount for x in self.freight])
        self.charge_total = sum([x.charge_amount for x in self.charges])
        self.total_amount = self.freight_total + self.charge_total

    @frappe.whitelist()
    def deliver(self, bo_detail, qty, unit, posting_datetime=None):
        deliverable = get_deliverable(bo_detail, self.destination_station)
        if qty > deliverable.get("qty"):
            frappe.throw(frappe._("Cannot deliver more than {} units".format(qty)))

        get_row = compose(
            excepts(StopIteration, first, lambda _: {}),
            filter(lambda x: x.get("name") == bo_detail),
        )
        row = get_row(self.freight)
        if not row:
            frappe.throw(frappe._("Invalid item"))

        conversion_factor = get_loading_conversion_factor(
            qty, unit, row.get("no_of_packages"), row.get("weight_actual")
        )
        if not conversion_factor:
            frappe.throw(frappe._("Invalid conversion factor"))

        no_of_packages = row.get("no_of_packages") * conversion_factor
        weight_actual = row.get("weight_actual") * conversion_factor

        _posting_datetime = posting_datetime or frappe.utils.now()
        frappe.get_doc(
            {
                "doctype": "Booking Log",
                "posting_datetime": _posting_datetime,
                "booking_order": self.name,
                "station": self.destination_station,
                "activity": "Collected",
                "loading_unit": unit,
                "no_of_packages": -no_of_packages,
                "weight_actual": -weight_actual,
                "bo_detail": bo_detail,
            }
        ).insert(ignore_permissions=True)

        self.set_as_completed()

    @frappe.whitelist()
    def set_as_completed(self):
        def is_collected(row):
            delivered = _get_delivered_packages(row.name)
            return row.no_of_packages == delivered.get(
                "no_of_packages"
            ) and row.weight_actual == delivered.get("weight_actual")

        if all([is_collected(x) for x in self.freight]):
            self.status = "Collected"
            self.save()


def _get_dashboard_info(doc):
    SalesInvoice = frappe.qb.DocType("Sales Invoice")
    q = (
        frappe.qb.from_(SalesInvoice)
        .where(
            (SalesInvoice.docstatus == 1) & (SalesInvoice.gg_booking_order == doc.name)
        )
        .select(
            Sum(SalesInvoice.grand_total, "grand_total"),
            Sum(SalesInvoice.outstanding_amount, "outstanding_amount"),
        )
    )
    invoice = q.run(as_dict=1)[0]
    return {
        "invoice": invoice,
        "history": get_history(doc.name),
    }


def _get_delivered_packages(bo_detail):
    return (
        frappe.get_all(
            "Booking Log",
            filters={"activity": "Collected", "bo_detail": bo_detail},
            fields=[
                "-sum(no_of_packages) as no_of_packages",
                "-sum(weight_actual) as weight_actual",
            ],
        )[0]
        or {}
    )


def _update_loading_operations(freight):
    lobos = frappe.get_all(
        "Loading Operation Booking Order",
        filters={
            "docstatus": ("<", 2),
            "bo_detail": freight.name,
        },
        as_list=1,
    )
    for (name,) in lobos:
        frappe.db.set_value(
            "Loading Operation Booking Order",
            name,
            "description",
            freight.item_description,
        )


def _update_invoices(freight):
    siis = frappe.get_all(
        "Sales Invoice Item",
        filters={
            "docstatus": ("<", 2),
            "gg_bo_detail": freight.name,
        },
        as_list=1,
    )
    for (name,) in siis:
        frappe.db.set_value(
            "Sales Invoice Item",
            name,
            "description",
            freight.item_description,
        )
