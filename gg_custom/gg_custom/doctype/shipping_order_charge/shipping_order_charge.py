# Copyright (c) 2022, Libermatic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class ShippingOrderCharge(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		charge_account: DF.Link
		charge_amount: DF.Currency
		item_description: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types
	pass
