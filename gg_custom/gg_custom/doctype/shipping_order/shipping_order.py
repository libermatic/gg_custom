# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from toolz.curried import unique, pluck


class ShippingOrder(Document):
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

    def before_insert(self):
        self.status = "Draft"

    def before_submit(self):
        self.status = "Stopped"
        self.current_station = self.initial_station

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

    def stop(self, station):
        if self.status != "In Transit":
            frappe.throw(
                frappe._(
                    "Cannot stop Shipping Order with status {}".format(
                        frappe.bold(self.status)
                    )
                )
            )

        if station == self.final_station:
            self.end_datetime = frappe.utils.now()
        self.status = "Stopped"
        self.current_station = station
        self.next_station = None
        self.save()
        _update_booking_orders(self)

    def start(self, station):
        if self.status != "Stopped":
            frappe.throw(
                frappe._(
                    "Cannot start Shipping Order with status {}".format(
                        frappe.bold(self.status)
                    )
                )
            )
        if self.current_station == self.initial_station:
            self.start_datetime = frappe.utils.now()
        self.status = "In Transit"
        self.next_station = station
        self.current_station = None
        self.save()
        _update_booking_orders(self)


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

