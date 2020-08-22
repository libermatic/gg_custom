from __future__ import unicode_literals
from gg_custom.api.booking_order import get_freight_rates


def boot_session(bootinfo):
    bootinfo.freight_items = get_freight_rates()
