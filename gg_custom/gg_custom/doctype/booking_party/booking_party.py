# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact
from erpnext.selling.doctype.customer.customer import make_address
from erpnext.accounts.party import get_dashboard_info

from gg_custom.api.booking_party import update_customer


class BookingParty(Document):
    def onload(self):
        load_address_and_contact(self)
        if self.customer:
            self.set_onload(
                "dashboard_info", get_dashboard_info("Customer", self.customer)
            )

    def validate(self):
        self.flags.is_new_doc = self.is_new()

    def on_update(self):
        update_customer(self.name)
        if self.flags.is_new_doc and self.get("address_line1"):
            address = make_address(self)
            if self.get("_gstin"):
                frappe.db.set_value(address.doctype, address.name, "gstin", self._gstin)
                frappe.db.set_value(self.doctype, self.name, "gstin", self._gstin)

    def create_customer(self):
        if self.customer:
            frappe.throw(
                frappe._(
                    "Customer already created for {}".format(
                        frappe.get_desk_link("Booking Party", self.name)
                    )
                )
            )

        doc = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": self.booking_party_name,
                "customer_group": frappe.get_cached_value(
                    "Selling Settings", None, "customer_group"
                ),
                "territory": frappe.get_cached_value(
                    "Selling Settings", None, "territory"
                ),
                "customer_primary_address": self.primary_address,
            }
        ).insert(ignore_permissions=True, ignore_mandatory=True)
        for (parent,) in frappe.get_all(
            "Dynamic Link",
            filters={
                "parenttype": "Address",
                "link_doctype": "Booking Party",
                "link_name": self.name,
            },
            fields=["parent"],
            as_list=1,
        ):
            address = frappe.get_doc("Address", parent)
            address.append(
                "links", {"link_doctype": doc.doctype, "link_name": doc.name}
            )
            address.save(ignore_permissions=True)

        self.db_set("customer", doc.name)
        return doc
