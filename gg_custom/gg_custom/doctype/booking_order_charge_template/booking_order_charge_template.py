# -*- coding: utf-8 -*-
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class BookingOrderChargeTemplate(Document):
    def validate(self):
        existing = frappe.db.exists(
            "Booking Order Charge Template",
            {"is_default": 1, "name": ("!=", self.name)},
        )
        if existing:
            frappe.throw(
                frappe._(
                    "{} is already the default template".format(
                        frappe.get_desk_link("Booking Order Charge Template", existing)
                    )
                )
            )
