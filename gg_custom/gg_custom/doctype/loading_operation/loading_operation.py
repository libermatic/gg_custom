# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe.model.document import Document


class LoadingOperation(Document):
    def validate(self):
        self._validate_shipping_order()

    def get_loads(self):
        self._validate_shipping_order()
        self.on_loads = []
        # todo: consider destination_station from Shipping Order stations
        for booking_order in frappe.get_all(
            "Booking Order",
            filters={
                "docstatus": 1,
                "status": "Booked",
                "source_station": self.station,
            },
            fields=[
                "name as booking_order",
                "no_of_packages",
                "weight_actual",
                "goods_value",
                "source_station",
                "destination_station",
            ],
        ):
            self.append("on_loads", booking_order)

        self.off_loads = []
        for booking_order in frappe.get_all(
            "Booking Order",
            filters={
                "docstatus": 1,
                "status": "In Transit",
                "destination_station": self.station,
                "last_shipping_order": self.shipping_order,
            },
            fields=[
                "name as booking_order",
                "no_of_packages",
                "weight_actual",
                "goods_value",
                "source_station",
                "destination_station",
            ],
        ):
            self.append("off_loads", booking_order)

    def on_submit(self):
        for load in self.on_loads:
            doc = frappe.get_cached_doc("Booking Order", load.booking_order)
            state_transition = {
                "from": {
                    "status": doc.status,
                    "last_shipping_order": doc.last_shipping_order,
                },
                "to": {"status": "Loaded", "last_shipping_order": self.shipping_order},
            }
            doc.status = "Loaded"
            doc.last_shipping_order = self.shipping_order
            doc.save()
            frappe.db.set_value(
                "Loading Operation Booking Order",
                load.name,
                "state_transition",
                json.dumps(state_transition),
            )

        for load in self.off_loads:
            doc = frappe.get_cached_doc("Booking Order", load.booking_order)
            state_transition = {
                "from": {"status": doc.status, "current_station": doc.current_station,},
                "to": {"status": "Unloaded", "current_station": self.station},
            }
            doc.status = "Unloaded"
            doc.current_station = self.station
            doc.save()
            frappe.db.set_value(
                "Loading Operation Booking Order",
                load.name,
                "state_transition",
                json.dumps(state_transition),
            )

    def before_cancel(self):
        self._validate_shipping_order()

    def on_cancel(self):
        for load in self.on_loads + self.off_loads:
            doc = frappe.get_cached_doc("Booking Order", load.booking_order)
            state_transition = json.loads(load.state_transition)
            if doc.docstatus == 1 and all(
                [
                    doc.get(key) == value
                    for key, value in state_transition.get("to").items()
                ]
            ):
                for key, value in state_transition.get("from"):
                    doc.set(key, value)
                doc.save()

    def _validate_shipping_order(self):
        status, current_station = frappe.db.get_value(
            "Shipping Order", self.shipping_order, ["status", "current_station"]
        )
        if status != "Stopped" or current_station != self.station:
            frappe.throw(
                frappe._(
                    "Operation can only be performed for a Shipping Order {} at {}".format(
                        frappe.bold("stopped"),
                        frappe.get_desk_link("Station", current_station)
                        if current_station
                        else frappe.bold("Station"),
                    )
                )
            )
