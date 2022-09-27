# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BookingLog(Document):
    def validate(self):
        existing_loading_unit = frappe.db.get_value(
            "Booking Log",
            filters={
                "name": ("!=", self.name),
                "booking_order": self.booking_order,
                "bo_detail": self.bo_detail,
                "activity": ("!=", "Booked"),
            },
            fieldname="loading_unit",
        )
        if existing_loading_unit and self.loading_unit != existing_loading_unit:
            frappe.throw(
                frappe._(
                    "Previous Loading Operation on {} has already being performed based on {}. ".format(
                        frappe.get_desk_link("Booking Order", self.booking_order),
                        existing_loading_unit,
                    )
                    + "Please execute the current one based on the same unit."
                )
            )
