# Copyright (c) 2022, Libermatic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class ShippingOrderChargeTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from gg_custom.gg_custom.doctype.shipping_order_charge.shipping_order_charge import ShippingOrderCharge

		charges: DF.Table[ShippingOrderCharge]
		is_default: DF.Check
		template_name: DF.Data
	# end: auto-generated types
	pass
