# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

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

    def before_rename(self, old_name, new_name, merge=False):
        from frappe.model.rename_doc import rename_doc

        if merge and self.customer:
            new_customer = frappe.db.get_value("Booking Party", new_name, "customer")
            if not new_customer:
                frappe.throw(
                    "Cannot merge Booking Parties because this party has accounting "
                    "entries while the new one will have none."
                )

            rename_doc("Customer", self.customer, new_customer, merge=True)

    def on_update(self):
        update_customer(self.name)
        if self.flags.is_new_doc and self.get("address_line1"):
            address = make_address(self)
            if self.get("_gstin"):
                frappe.db.set_value(address.doctype, address.name, "gstin", self._gstin)
                frappe.db.set_value(self.doctype, self.name, "gstin", self._gstin)

    @frappe.whitelist()
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
                "customer_group": frappe.db.get_single_value(
                    "GG Custom Settings", "customer_group"
                ),
                "territory": frappe.db.get_single_value(
                    "GG Custom Settings", "territory"
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
