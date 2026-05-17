# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BookingLog(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        activity: DF.Literal["", "Booked", "Loaded", "Unloaded", "Collected"]
        bo_detail: DF.Data | None
        booking_order: DF.Link | None
        goods_value: DF.Currency
        loading_operation: DF.Link | None
        loading_unit: DF.Literal["", "Packages", "Weight"]
        no_of_packages: DF.Int
        posting_datetime: DF.Datetime | None
        shipping_order: DF.Link | None
        station: DF.Link | None
        weight_actual: DF.Float
    # end: auto-generated types
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
