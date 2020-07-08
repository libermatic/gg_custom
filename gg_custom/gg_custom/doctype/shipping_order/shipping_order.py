# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from toolz.curried import unique


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
            frappe.throw(frappe._("Same Transit Station selected multiple times"))

    def before_insert(self):
        self.status = "Draft"
