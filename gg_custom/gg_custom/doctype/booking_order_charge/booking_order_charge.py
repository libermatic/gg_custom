# -*- coding: utf-8 -*-
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class BookingOrderCharge(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		charge_amount: DF.Currency
		charge_type: DF.Link
		item_description: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types
	pass
