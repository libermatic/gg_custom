# -*- coding: utf-8 -*-
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class LoadingOperationBookingOrder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		available: DF.Int
		bo_detail: DF.Literal[None]
		booking_order: DF.Link
		consignee: DF.Link | None
		consignee_name: DF.Data | None
		description: DF.Data | None
		loading_unit: DF.Literal["", "Packages", "Weight"]
		no_of_packages: DF.Int
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		qty: DF.Int
		weight_actual: DF.Float
	# end: auto-generated types
	pass
