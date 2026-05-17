# -*- coding: utf-8 -*-
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ShippingLog(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        activity: DF.Literal["", "Not Started", "Moving", "Stopped", "Operation", "Completed"]
        loading_operation: DF.Link | None
        posting_datetime: DF.Datetime | None
        shipping_order: DF.Link | None
        station: DF.Link | None
    # end: auto-generated types
    pass
