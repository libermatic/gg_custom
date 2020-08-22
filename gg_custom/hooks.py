# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__

app_name = "gg_custom"
app_version = __version__
app_title = "GG Custom"
app_publisher = "Libermatic"
app_description = "Customizations for GG"
app_icon = "fa fa-truck"
app_color = "grey"
app_email = "info@libermatic.com"
app_license = "MIT"

fixtures = [
    {
        "doctype": "Custom Field",
        "filters": {
            "fieldname": ("like", "gg_%"),
            "dt": ("in", ["Sales Invoice", "Item"]),
        },
    },
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/gg_custom/css/gg_custom.css"
app_include_js = ["/assets/js/gg_custom.min.js"]

# include js, css files in header of web template
# web_include_css = "/assets/gg_custom/css/gg_custom.css"
# web_include_js = "/assets/gg_custom/js/gg_custom.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "gg_custom.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "gg_custom.install.before_install"
# after_install = "gg_custom.install.after_install"

boot_session = "gg_custom.boot.boot_session"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "gg_custom.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Address": {
        "before_save": "gg_custom.doc_events.address.before_save",
        "on_update": "gg_custom.doc_events.address.on_update",
    },
    "Sales Invoice": {
        "validate": "gg_custom.doc_events.sales_invoice.validate",
        "on_submit": "gg_custom.doc_events.sales_invoice.on_submit",
        "on_cancel": "gg_custom.doc_events.sales_invoice.on_cancel",
    },
    "Payment Entry": {
        "on_submit": "gg_custom.doc_events.payment_entry.on_submit",
        "on_cancel": "gg_custom.doc_events.payment_entry.on_cancel",
    },
    "Item": {"validate": "gg_custom.doc_events.item.validate"},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"gg_custom.tasks.all"
# 	],
# 	"daily": [
# 		"gg_custom.tasks.daily"
# 	],
# 	"hourly": [
# 		"gg_custom.tasks.hourly"
# 	],
# 	"weekly": [
# 		"gg_custom.tasks.weekly"
# 	]
# 	"monthly": [
# 		"gg_custom.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "gg_custom.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "gg_custom.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "gg_custom.task.get_dashboard_data"
# }

# Jinja Environment Customizations
# --------------------------------

jenv = {
    "methods": [
        "get_manifest_rows:gg_custom.api.shipping_order.get_manifest_rows",
        "get_party_open_orders:gg_custom.api.booking_party.get_party_open_orders",
    ]
}

