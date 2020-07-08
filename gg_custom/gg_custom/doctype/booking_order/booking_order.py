# -*- coding: utf-8 -*-
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class BookingOrder(Document):
    def before_submit(self):
        self.status = "Booked"

    def before_cancel(self):
        if self.status != "Booked":
            frappe.throw(frappe._("Cannot cancel an order when it is in progress"))
        self.status = "Cancelled"

