import frappe


def validate(doc, method):
    doc.flags.is_new_doc = doc.is_new()
    if doc.is_new():
        if (doc.get("_gstin") or doc.get("_phone")) and not (
            doc.get("address_line1") and doc.get("city")
        ):
            frappe.throw(
                "<em>Address Line 1</em>, <em>City</em>, <em>Country</em> are required."
            )
        if not (bool(doc.get("address_line1")) == bool(doc.get("city"))):
            frappe.throw(
                "All or none of <em>Address Line 1</em>, <em>City</em>, "
                "<em>Country</em> are required."
            )


def after_insert(doc, method):
    if doc.flags.is_new_doc and doc.get("address_line1"):
        address = frappe.get_doc(
            {
                "doctype": "Address",
                "address_title": doc.name,
                "address_type": "Current",
                "address_line1": doc.get("address_line1"),
                "address_line2": doc.get("address_line2"),
                "city": doc.get("city"),
                "state": doc.get("state"),
                "country": doc.get("country"),
                "phone": doc.get("_phone"),
                "is_primary_address": 1,
                "links": [{"link_doctype": "Driver", "link_name": doc.name}],
            }
        )
        address.insert()
        doc.reload()
        doc.address = address.name
        if phone := doc.get("_phone"):
            doc.cell_number = phone
        doc.save()
