# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe.model.document import Document
from toolz.curried import compose, valmap, first, groupby

from gg_custom.api.booking_order import get_orders_for


class LoadingOperation(Document):
    def validate(self):
        self._validate_shipping_order()
        self._validate_booking_orders()

    def get_loads(self):
        self._validate_shipping_order()

        self.on_loads = []
        for booking_order in get_orders_for(station=self.station):
            self.append("on_loads", booking_order)

        self.off_loads = []
        for booking_order in get_orders_for(shipping_order=self.shipping_order):
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
            self._create_booking_log(load)

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

    def _validate_booking_orders(self):
        rows_with_zero_packages = [
            x.booking_order
            for x in self.on_loads + self.off_loads
            if x.no_of_packages <= 0
        ]
        if rows_with_zero_packages:
            frappe.throw(
                frappe._(
                    "Booking Orders: {} cannot contain less than 1 package".format(
                        ", ".join(rows_with_zero_packages)
                    )
                )
            )

        get_map = compose(valmap(first), groupby("booking_order"))

        on_loads_orders = get_map(get_orders_for(station=self.station))
        on_load_rows_with_invalid_packages = [
            x.booking_order
            for x in self.on_loads
            if x.no_of_packages
            > on_loads_orders.get(x.booking_order, {}).get("no_of_packages", 0)
        ]
        if on_load_rows_with_invalid_packages:
            frappe.throw(
                frappe._(
                    "Booking Orders: {} contain invalid no of packages ".format(
                        ", ".join(on_load_rows_with_invalid_packages)
                    )
                )
            )

        off_loads_orders = get_map(get_orders_for(shipping_order=self.shipping_order))
        off_load_rows_with_invalid_packages = [
            x.booking_order
            for x in self.off_loads
            if x.no_of_packages
            > off_loads_orders.get(x.booking_order, {}).get("no_of_packages", 0)
        ]
        if off_load_rows_with_invalid_packages:
            frappe.throw(
                frappe._(
                    "Booking Orders: {} contain invalid no of packages ".format(
                        ", ".join(off_load_rows_with_invalid_packages)
                    )
                )
            )

    def _create_booking_log(self, load):
        if load.parentfield not in ["on_loads", "off_loads"]:
            frappe.throw(frappe._("Invalid Loading Operation load"))

        activity = "Loaded" if load.parentfield == "on_loads" else "Unloaded"
        direction = -1 if load.parentfield == "on_loads" else 1
        frappe.get_doc(
            {
                "doctype": "Booking Log",
                "posting_datetime": self.posting_datetime,
                "booking_order": load.booking_order,
                "shipping_order": self.shipping_order,
                "station": self.station,
                "activity": activity,
                "loading_operation": self.name,
                "no_of_packages": direction * load.no_of_packages,
                "weight_actual": direction * load.weight_actual,
                "goods_value": direction * load.goods_value,
            }
        ).insert()
