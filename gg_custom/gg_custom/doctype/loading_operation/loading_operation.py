# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from toolz.curried import pluck


class LoadingOperation(Document):
    def get_loads(self):
        self.on_loads = []
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

    def on_submit(self):
        for bo in pluck("booking_order", self.on_loads):
            doc = frappe.get_cached_doc("Booking Order", bo)
            doc.status = "Loaded"
            doc.last_shipping_order = self.shipping_order
            doc.save()

        for bo in pluck("booking_order", self.off_loads):
            doc = frappe.get_cached_doc("Booking Order", bo)
            doc.status = "Unloaded"
            doc.current_station = self.station
            doc.save()
