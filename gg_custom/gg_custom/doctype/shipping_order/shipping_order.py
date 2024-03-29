# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from toolz.curried import (
    unique,
    pluck,
    map,
    compose,
)

from gg_custom.api.shipping_order import get_history, get_order_contents


class ShippingOrder(Document):
    def onload(self):
        if self.docstatus == 1:
            self.set_onload("dashboard_info", _get_dashboard_info(self))

    def validate(self):
        if self.initial_station == self.final_station:
            frappe.throw(frappe._("Initial and Final Stations cannot be same."))

        if any(
            [
                x.get("station") in [self.initial_station, self.final_station]
                for x in self.transit_stations
            ]
        ):
            frappe.throw(
                frappe._(
                    "Transit Station cannot be either the Initial or Final Station."
                )
            )

        if len(list(unique([x.get("station") for x in self.transit_stations]))) != len(
            self.transit_stations
        ):
            frappe.throw(frappe._("Same Transit Station selected multiple times."))

        existing = frappe.db.exists(
            "Shipping Order",
            {
                "docstatus": 1,
                "status": ("in", ["In Transit", "Stopped"]),
                "vehicle": self.vehicle,
                "name": ("!=", self.name),
            },
        )
        if existing:
            frappe.throw(
                frappe._(
                    "{} is already engaged with {}.".format(
                        frappe.get_desk_link("Vehicle", self.vehicle),
                        frappe.get_desk_link("Shipping Order", existing),
                    )
                )
            )

        if self.status == "Stopped" and not self.current_station:
            frappe.throw(
                frappe._(
                    "Cannot set status to {} without a {}.".format(
                        frappe.bold(self.status), frappe.bold("Station")
                    )
                )
            )

        allowed_stations = [self.initial_station, self.final_station] + [
            x.get("station") for x in self.transit_stations
        ]
        if self.current_station and self.current_station not in allowed_stations:
            frappe.throw(
                frappe._(
                    "Current Station {} not present in Shipping Order itinerary".format(
                        frappe.get_desk_link("Station", self.current_station)
                    )
                )
            )

    def before_save(self):
        if not self.transporter:
            self.shipping_order_charge_template = None
            self.charges = []

    def before_insert(self):
        self.status = "Draft"

    def before_submit(self):
        self.status = "Stopped"
        self.current_station = self.initial_station

    def on_submit(self):
        frappe.get_doc(
            {
                "doctype": "Shipping Log",
                "posting_datetime": frappe.utils.now(),
                "shipping_order": self.name,
                "station": self.initial_station,
                "activity": "Stopped",
            }
        ).insert(ignore_permissions=True)

    def before_update_after_submit(self):
        if self.status in ["Completed"]:
            self.current_station = None
            self.next_station = None

    def before_cancel(self):
        if frappe.db.exists(
            "Loading Operation", {"docstatus": 1, "shipping_order": self.name}
        ):
            frappe.throw(
                frappe._(
                    "Cannot cancel because Loading Operation already exists for this Shipping Order."
                )
            )
        self.status = "Cancelled"

    def on_cancel(self):
        for (log_name,) in frappe.get_all(
            "Shipping Log", filters={"shipping_order": self.name}, as_list=1
        ):
            frappe.delete_doc("Shipping Log", log_name, ignore_permissions=True)

    @frappe.whitelist()
    def stop(self, station, posting_datetime=None):
        if self.status != "In Transit":
            frappe.throw(
                frappe._(
                    "Cannot stop Shipping Order with status {}".format(
                        frappe.bold(self.status)
                    )
                )
            )

        _posting_datetime = posting_datetime or frappe.utils.now()
        if station == self.final_station:
            self.end_datetime = _posting_datetime
        self.status = "Stopped"
        self.current_station = station
        self.next_station = None
        self.save()
        _update_booking_orders(self)

        frappe.get_doc(
            {
                "doctype": "Shipping Log",
                "posting_datetime": _posting_datetime,
                "shipping_order": self.name,
                "station": station,
                "activity": "Stopped",
            }
        ).insert(ignore_permissions=True)

    @frappe.whitelist()
    def start(self, station, posting_datetime=None):
        if self.status != "Stopped":
            frappe.throw(
                frappe._(
                    "Cannot start Shipping Order with status {}".format(
                        frappe.bold(self.status)
                    )
                )
            )
        _posting_datetime = posting_datetime or frappe.utils.now()
        if self.current_station == self.initial_station:
            self.start_datetime = _posting_datetime
        self.status = "In Transit"
        self.next_station = station
        self.current_station = None
        self.save()
        _update_booking_orders(self)

        frappe.get_doc(
            {
                "doctype": "Shipping Log",
                "posting_datetime": _posting_datetime,
                "shipping_order": self.name,
                "station": station,
                "activity": "Moving",
            }
        ).insert(ignore_permissions=True)

    @frappe.whitelist()
    def set_as_completed(self, validate_onboard=False):
        if self.status != "Stopped":
            frappe.throw(
                frappe._("Shipping Order can only be completed when it has stopped.")
            )
        if validate_onboard and _current_onboard_bookings(self):
            frappe.throw(
                frappe._(
                    "Shipping Order cannot be completed because some Booking Orders "
                    "are still onboard. Please create a Loading Operation to unload."
                )
            )
        self.status = "Completed"
        self.save()

        frappe.get_doc(
            {
                "doctype": "Shipping Log",
                "posting_datetime": frappe.utils.now(),
                "shipping_order": self.name,
                "station": self.final_station,
                "activity": "Completed",
            }
        ).insert(ignore_permissions=True)


def _update_booking_orders(shipping_order):
    for bo in pluck(
        "name",
        frappe.get_all(
            "Booking Order",
            filters={
                "docstatus": 1,
                "status": ("in", ["Loaded", "In Transit"]),
                "last_shipping_order": shipping_order.name,
            },
        ),
    ):
        doc = frappe.get_cached_doc("Booking Order", bo)
        doc.status = "In Transit"
        doc.current_station = shipping_order.current_station
        doc.save()


def _get_dashboard_info(doc):
    contents = get_order_contents(doc)
    PurchaseInvoice = frappe.qb.DocType("Purchase Invoice")
    q = (
        frappe.qb.from_(PurchaseInvoice)
        .where(
            (PurchaseInvoice.docstatus == 1)
            & (PurchaseInvoice.gg_shipping_order == doc.name)
        )
        .select(
            Sum(PurchaseInvoice.rounded_total, "rounded_total"),
            Sum(PurchaseInvoice.outstanding_amount, "outstanding_amount"),
        )
    )
    invoice = q.run(as_dict=1)[0]

    return {
        **contents,
        "invoice": invoice,
        "history": get_history(doc.name),
    }


def _current_onboard_bookings(doc):
    LoadingOperationBookingOrder = frappe.qb.DocType("Loading Operation Booking Order")
    LoadingOperation = frappe.qb.DocType("Loading Operation")
    q = (
        frappe.qb.from_(LoadingOperationBookingOrder)
        .left_join(LoadingOperation)
        .on(LoadingOperation.name == LoadingOperationBookingOrder.parent)
        .where(
            (LoadingOperation.docstatus == 1)
            & (LoadingOperation.shipping_order == doc.name)
        )
        .select(LoadingOperationBookingOrder.booking_order)
    )
    get_booking_orders = compose(
        list,
        map(lambda x: x[0]),
        lambda x: q.where(LoadingOperationBookingOrder.parentfield == x).run(),
    )
    return [
        x
        for x in get_booking_orders("on_loads")
        if x not in get_booking_orders("off_loads")
    ]
