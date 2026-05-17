# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BookingOrderChargeTemplate(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF
        from gg_custom.gg_custom.doctype.booking_order_charge.booking_order_charge import BookingOrderCharge

        charges: DF.Table[BookingOrderCharge]
        is_default: DF.Check
        template_name: DF.Data
    # end: auto-generated types
    def validate(self):
        if self.is_default:
            self._validate_default()

    def _validate_default(self):
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
