# -*- coding: utf-8 -*-
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class BookingOrderFreightDetail(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		based_on: DF.Literal["", "Packages", "Weight"]
		item_description: DF.SmallText
		no_of_packages: DF.Int
		packing: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		rate: DF.Currency
		weight_actual: DF.Float
		weight_charged: DF.Float
	# end: auto-generated types
	pass
