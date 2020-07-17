import sumBy from 'lodash/sumBy';

import { set_charge_type_query } from './utils';
import Timeline from '../vue/Timeline.vue';

function set_address(party_type) {
  const address_field = `${party_type}_address`;
  return async function (frm) {
    if (frm.doc[party_type]) {
      const { message: { primary_address } = {} } = await frappe.db.get_value(
        'Booking Party',
        frm.doc[party_type],
        'primary_address'
      );
      frm.set_value(address_field, primary_address);
    } else {
      frm.set_value(address_field, null);
    }
  };
}

function set_address_dispay(party_type) {
  const address_field = `${party_type}_address`;
  const display_field = `${party_type}_address_display`;
  return async function (frm) {
    erpnext.utils.get_address_display(frm, address_field, display_field);
  };
}

function set_total_amount(frm) {
  const total_amount = sumBy(frm.doc.charges, 'charge_amount');
  frm.set_value({ total_amount });
}

export function booking_order_charge() {
  return {
    charge_amount: set_total_amount,
    charges_remove: set_total_amount,
  };
}

export function booking_order() {
  return {
    setup: function (frm) {
      ['consignor', 'consignee'].forEach((type) =>
        frm.set_query(`${type}_address`, (doc) => ({
          filters: { link_doctype: 'Booking Party', link_name: doc[type] },
        }))
      );
      set_charge_type_query(frm);
    },
    refresh: function (frm) {
      if (frm.doc.docstatus === 1) {
        const { status, current_station, destination_station } = frm.doc;
        if (status === 'Unloaded' && current_station === destination_station) {
          frm.add_custom_button('Deliver', () =>
            frappe.confirm(
              'Are you sure you want to Deliver this Booking Order?',
              async function () {
                try {
                  await frm.call('set_as_completed', {
                    validate_onboard: true,
                  });
                  frm.reload_doc();
                } finally {
                  frm.refresh();
                }
              }
            )
          );
        }

        const { payment_status } = frm.doc;
        if (payment_status === 'Unbilled') {
          frm
            .add_custom_button('Create Invoice', () => create_invoice(frm))
            .addClass('btn-primary');
        } else if (payment_status === 'Unpaid') {
          frm
            .add_custom_button('Create Payment', () => {})
            .addClass('btn-primary');
        }
      }
      if (frm.doc.docstatus > 0) {
        const { dashboard_info } = frm.doc.__onload || {};
        if (dashboard_info) {
          render_dashboard(frm, dashboard_info);
        }
      }
    },
    consignor: set_address('consignor'),
    consignee: set_address('consignee'),
    consignor_address: set_address_dispay('consignor'),
    consignee_address: set_address_dispay('consignee'),
    booking_order_charge_template: async function (frm) {
      cur_frm.clear_table('charges');
      const { booking_order_charge_template } = frm.doc;
      if (booking_order_charge_template) {
        const charges = await frappe.db.get_list('Booking Order Charge', {
          fields: ['charge_type', 'charge_amount'],
          parent: 'Booking Order Charge Template',
          filters: {
            parenttype: 'Booking Order Charge Template',
            parent: booking_order_charge_template,
          },
          order_by: 'idx',
        });
        charges.forEach((row) => {
          frm.add_child('charges', row);
        });
      }
      cur_frm.refresh_field('charges');
      set_total_amount(frm);
    },
  };
}

export function booking_order_listview_settings() {
  const status_color = {
    Draft: 'red',
    Booked: 'darkgrey',
    Loaded: 'lightblue',
    'In Transit': 'blue',
    Unloaded: 'orange',
    Collected: 'green',
    Cancelled: 'red',
    Unknown: 'darkgrey',
  };
  return {
    get_indicator: function (doc) {
      const status = doc.status || 'Unknown';
      return [__(status), status_color[status] || 'grey', `status,=,${status}`];
    },
  };
}

function render_dashboard(frm, dashboard_info) {
  const props = { ...dashboard_info };
  if (dashboard_info && dashboard_info.invoice) {
    const { grand_total, outstanding_amount } = dashboard_info.invoice;
    cur_frm.dashboard.add_indicator(
      `Total Billed: ${format_currency(grand_total)}`,
      'green'
    );
    cur_frm.dashboard.add_indicator(
      `Outstanding Amount: ${format_currency(outstanding_amount)}`,
      'orange'
    );
  }
  new Vue({
    el: frm.dashboard.add_section('<div />').children()[0],
    render: (h) => h(Timeline, { props }),
  });
}

function create_invoice(frm) {
  const dialog = new frappe.ui.Dialog({
    title: 'Create Invoice',
    fields: [
      {
        fieldtype: 'Select',
        fieldname: 'bill_to',
        label: __('Bill To'),
        options: [
          {
            label: `Consignor: ${frm.doc.consignor}`,
            value: 'consignor',
          },
          {
            label: `Consignee: ${frm.doc.consignee}`,
            value: 'consignee',
          },
        ],
        default: 'consignor',
      },
      {
        fieldtype: 'Link',
        fieldname: 'taxes_and_charges',
        label: __('Sales Taxes and Charges Template'),
        options: 'Sales Taxes and Charges Template',
        only_select: 1,
      },
    ],
  });
  dialog.set_primary_action('OK', async function () {
    const args = dialog.get_values();
    frappe.model.open_mapped_doc({
      method: 'gg_custom.api.booking_order.make_sales_invoice',
      frm,
      args,
    });
    dialog.hide();
  });
  dialog.onhide = () => dialog.$wrapper.remove();
  dialog.show();
}
