from __future__ import unicode_literals
import frappe

from gg_custom.api.booking_party import update_customer


@frappe.whitelist()
def update_document_title(
    doctype,
    docname,
    title_field=None,
    old_title=None,
    new_title=None,
    new_name=None,
    merge=False,
):
    from frappe.model.rename_doc import update_document_title

    docname = update_document_title(
        doctype, docname, title_field, old_title, new_title, new_name, merge,
    )

    if doctype == "Booking Party":
        update_customer(docname)

    return docname
