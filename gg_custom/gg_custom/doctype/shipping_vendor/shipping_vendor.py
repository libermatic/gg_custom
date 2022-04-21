# Copyright (c) 2022, Libermatic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact
from erpnext.selling.doctype.customer.customer import make_address
from erpnext.accounts.party import get_dashboard_info

from gg_custom.api.shipping_vendor import update_supplier

class ShippingVendor(Document):
    def onload(self):
        load_address_and_contact(self)
        if self.supplier:
            self.set_onload(
                "dashboard_info", get_dashboard_info("Supplier", self.supplier)
            )

    def validate(self):
        self.flags.is_new_doc = self.is_new()

    def on_update(self):
        update_supplier(self.name)
        if self.flags.is_new_doc:
            if self.get("address_line1"):
                address = make_address(self)
                if self.get("_gstin"):
                    frappe.db.set_value(address.doctype, address.name, "gstin", self._gstin)
                    frappe.db.set_value(self.doctype, self.name, "gstin", self._gstin)
            self.create_supplier()
            

    @frappe.whitelist()
    def create_supplier(self):
        if self.supplier:
            frappe.throw(
                frappe._(
                    "Supplier already created for {}".format(
                        frappe.get_desk_link("Shipping Vendor", self.name)
                    )
                )
            )

        doc = frappe.get_doc(
            {
                "doctype": "Supplier",
                "supplier_name": self.shipping_vendor_name,
                "supplier_group": frappe.db.get_single_value(
                    "GG Custom Settings", "supplier_group"
                ),
                "supplier_type": frappe.db.get_single_value(
                    "GG Custom Settings", "supplier_type"
                ),
                "supplier_primary_address": self.primary_address,
            }
        ).insert(ignore_permissions=True, ignore_mandatory=True)
        for (parent,) in frappe.get_all(
            "Dynamic Link",
            filters={
                "parenttype": "Address",
                "link_doctype": "Shipping Vendor",
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

        self.db_set("supplier", doc.name)
        return doc
