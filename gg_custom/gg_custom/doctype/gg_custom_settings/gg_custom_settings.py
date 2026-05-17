# Copyright (c) 2021, Libermatic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class GGCustomSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		company: DF.Link
		customer_group: DF.Link
		supplier_group: DF.Link | None
		supplier_type: DF.Literal["Company", "Individual"]
		territory: DF.Link
	# end: auto-generated types
	pass
