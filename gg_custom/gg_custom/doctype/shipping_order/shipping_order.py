# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from toolz.curried import (
    unique,
    pluck,
    merge,
    keyfilter,
    concat,
    keymap,
    valmap,
    map,
    compose,
)

from gg_custom.api.shipping_order import get_history


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
                "activity": "Not Started",
            }
        ).insert()

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

        frappe.get_doc(
            {
                "doctype": "Shipping Log",
                "posting_datetime": frappe.utils.now(),
                "shipping_order": self.name,
                "station": station,
                "activity": "Stopped",
            }
        ).insert()

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

        frappe.get_doc(
            {
                "doctype": "Shipping Log",
                "posting_datetime": frappe.utils.now(),
                "shipping_order": self.name,
                "station": station,
                "activity": "Moving",
            }
        ).insert()

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
        ).insert()


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
    params = ["no_of_packages", "weight_actual", "goods_value"]
    fields = list(
        concat(
            [
                ["SUM({t}_{p}) AS {t}_{p}".format(t=t, p=p) for p in params]
                for t in ["on_load", "off_load"]
            ]
        )
    )
    data = frappe.db.sql(
        """
            SELECT {fields} FROM `tabLoading Operation`
            WHERE docstatus = 1 AND shipping_order = %(shipping_order)s
        """.format(
            fields=", ".join(fields)
        ),
        values={"shipping_order": doc.name},
        as_dict=1,
    )[0]

    def get_values(_type):
        fields = list(map(lambda x: "{}_{}".format(_type, x), params))
        _get = compose(
            valmap(lambda x: x or 0),
            keymap(lambda x: x.replace("{}_".format(_type), "")),
            keyfilter(lambda x: x in fields),
        )
        return _get(data)

    on_load = get_values("on_load")
    off_load = get_values("off_load")

    current = merge({}, *[{x: on_load[x] - off_load[x]} for x in params])
    return {
        "on_load": on_load,
        "off_load": off_load,
        "current": current,
        "history": get_history(doc.name),
    }


def _current_onboard_bookings(doc):
    get_booking_orders = compose(
        list,
        map(lambda x: x[0]),
        lambda x: frappe.db.sql(
            """
                SELECT lobo.booking_order
                FROM `tabLoading Operation Booking Order` AS lobo
                LEFT JOIN `tabLoading Operation` AS lo ON
                    lo.name = lobo.parent
                WHERE
                    lo.docstatus = 1 AND
                    lo.shipping_order = %(shipping_order)s AND
                    lobo.parentfield = %(parentfield)s
            """,
            values={"shipping_order": doc.name, "parentfield": x},
        ),
    )
    return [
        x
        for x in get_booking_orders("on_loads")
        if x not in get_booking_orders("off_loads")
    ]

