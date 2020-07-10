# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe import _


def get_data():
    return [
        {
            "module_name": "GG Custom",
            "color": "grey",
            "icon": "fa fa-truck",
            "type": "module",
            "label": _("GG Custom"),
        }
    ]
