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

    def before_save(self):
        for load in self.on_loads + self.off_loads:
            no_of_packages, weight_actual, goods_value = frappe.get_cached_value(
                "Booking Order",
                load.booking_order,
                ["no_of_packages", "weight_actual", "goods_value"],
            )
            load.weight_actual = (
                weight_actual / no_of_packages * load.no_of_packages
                if no_of_packages
                else 0
            )
            load.goods_value = (
                goods_value / no_of_packages * load.no_of_packages
                if no_of_packages
                else 0
            )

        for param in ["no_of_packages", "weight_actual", "goods_value"]:
            for direction in ["on_load", "off_load"]:
                field = "{}_{}".format(direction, param)
                table = self.get("{}s".format(direction))
                self.set(field, sum([x.get(param) for x in table]))

        self.on_load_no_of_bookings = len(self.on_loads)
        self.off_load_no_of_bookings = len(self.off_loads)

    def on_submit(self):
        for load in self.on_loads + self.off_loads:
            _create_booking_log(load, self)

        frappe.get_doc(
            {
                "doctype": "Shipping Log",
                "posting_datetime": self.posting_datetime,
                "shipping_order": self.shipping_order,
                "station": self.station,
                "activity": "Loading",
                "loading_operation": self.name,
            }
        ).insert()
        so = frappe.get_doc("Shipping Order", self.shipping_order)
        if so.final_station == self.station:
            so.set_as_completed()

    def before_cancel(self):
        self._validate_shipping_order()

    def on_cancel(self):
        for log_type in ["Booking Log", "Shipping Log"]:
            for (log_name,) in frappe.get_all(
                log_type, filters={"loading_operation": self.name}, as_list=1
            ):
                frappe.delete_doc(log_type, log_name)

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


def _create_booking_log(child, parent):
    if child.parentfield not in ["on_loads", "off_loads"]:
        frappe.throw(frappe._("Invalid Loading Operation child"))

    activity = "Loaded" if child.parentfield == "on_loads" else "Unloaded"
    direction = -1 if child.parentfield == "on_loads" else 1
    frappe.get_doc(
        {
            "doctype": "Booking Log",
            "posting_datetime": parent.posting_datetime,
            "booking_order": child.booking_order,
            "shipping_order": parent.shipping_order,
            "station": parent.station,
            "activity": activity,
            "loading_operation": parent.name,
            "no_of_packages": direction * child.no_of_packages,
            "weight_actual": direction * child.weight_actual,
            "goods_value": direction * child.goods_value,
        }
    ).insert()

