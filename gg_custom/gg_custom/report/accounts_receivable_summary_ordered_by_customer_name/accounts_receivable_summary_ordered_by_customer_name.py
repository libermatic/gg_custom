# Copyright (c) 2013, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import (
    execute as accounts_receivable_summary,
)


def execute(filters=None):
    result = list(accounts_receivable_summary(filters))
    result[1] = sorted(result[1] or [], key=lambda x: x.get("party_name"))
    return result
