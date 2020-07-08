# -*- coding: utf-8 -*-
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

# import frappe
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact
from erpnext.selling.doctype.customer.customer import make_address


class BookingParty(Document):
    def onload(self):
        load_address_and_contact(self)

    def validate(self):
        self.flags.is_new_doc = self.is_new()

    def on_update(self):
        if self.flags.is_new_doc and self.get("address_line1"):
            make_address(self)
