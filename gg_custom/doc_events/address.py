from __future__ import unicode_literals
import frappe


def on_update(doc, self):
    for link in doc.links:
        if link.link_doctype == "Booking Party":
            bp = frappe.get_doc(link.link_doctype, link.link_name)
            if not bp.primary_address:
                bp.primary_address = doc.name
            if bp.primary_address == link.link_name:
                bp.phone = doc.phone
            bp.save()
