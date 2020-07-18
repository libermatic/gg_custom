from __future__ import unicode_literals
import frappe


def before_save(doc, method):
    booking_party_links = [x for x in doc.links if x.link_doctype == "Booking Party"]
    customer_links = [x.link_name for x in doc.links if x.link_doctype == "Customer"]
    for link in booking_party_links:
        bp = frappe.get_cached_doc(link.link_doctype, link.link_name)
        if bp.customer and bp.customer not in customer_links:
            doc.append("links", {"link_doctype": "Customer", "link_name": bp.customer})


def on_update(doc, method):
    for link in [x for x in doc.links if x.link_doctype == "Booking Party"]:
        bp = frappe.get_cached_doc(link.link_doctype, link.link_name)
        if not bp.primary_address:
            bp.primary_address = doc.name
        if bp.primary_address == link.link_name:
            bp.phone = doc.phone
        bp.save()
