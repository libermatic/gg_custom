import { set_charge_type_query, sumBy } from './utils';
import Timeline from '../vue/Timeline.vue';

export function booking_order_freight_detail() {
  return {
    freight_add: function (frm, cdt, cdn) {
      const row = frappe.get_doc(cdt, cdn);
      frm.script_manager.copy_from_first_row('freight', row, ['based_on']);
    },
    based_on: function (frm, cdt, cdn) {
      const { freight_items = {} } = frappe.boot;
      const { based_on } = frappe.get_doc(cdt, cdn);
      const { rate = 0 } = freight_items[based_on] || {};
      ['no_of_packages', 'weight_actual', 'weight_charged'].forEach((field) =>
        frappe.model.set_value(cdt, cdn, field, 0)
      );
      frappe.model.set_value(cdt, cdn, 'rate', rate);
    },
    no_of_packages: set_total('no_of_packages'),
    weight_actual: function (frm, cdt, cdn) {
      set_total('weight_actual')(frm, cdt, cdn);
      const { weight_actual } = frappe.get_doc(cdt, cdn);
      frappe.model.set_value(cdt, cdn, 'weight_charged', weight_actual);
    },
    weight_charged: set_total('weight_charged'),
    rate: set_freight_amount,
    amount: function (frm, cdt, cdn) {
      const freight_total = sumBy('amount', frm.doc.freight);
      frm.set_value({ freight_total });
    },
  };
}

export function booking_order_charge() {
  return {
    charge_amount: set_charge_total,
    charges_remove: set_charge_total,
  };
}

export function booking_order() {
  return {
    setup: function (frm) {
      ['consignor', 'consignee'].forEach((type) => {
        frm.set_query(type, (doc) => ({
          filters: { disabled: 0 },
        }));
        frm.set_query(`${type}_address`, (doc) => ({
          filters: { link_doctype: 'Booking Party', link_name: doc[type] },
        }));
      });
      set_charge_type_query(frm);
    },
    refresh: function (frm) {
      if (frm.doc.docstatus === 1) {
        frm.add_custom_button('Deliver', handle_deliver(frm));

        frm
          .add_custom_button('Create Invoice', () => create_invoice(frm))
          .addClass('btn-primary');

        const {
          dashboard_info: { invoice: { outstanding_amount = 0 } = {} } = {},
        } = frm.doc.__onload || {};
        if (outstanding_amount > 0) {
          frm.add_custom_button('Create Payment', () => create_payment(frm));
        }
        frm.page.add_menu_item('Update Party Details', () =>
          update_party_details(frm)
        );
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
        const { message: charges } = await frappe.call({
          method: 'gg_custom.api.booking_order.get_charges_from_template',
          args: { template: booking_order_charge_template },
        });
        (charges || []).forEach((row) => {
          frm.add_child('charges', row);
        });
      }
      cur_frm.refresh_field('charges');
      set_charge_total(frm);
    },
    freight_total: set_total_amount,
    charge_total: set_total_amount,
  };
}

export function booking_order_listview_settings() {
  const status_color = {
    Draft: 'red',
    Booked: 'darkgrey',
    'In Progress': 'blue',
    Collected: 'green',
    Cancelled: 'red',
    Unknown: 'darkgrey',
  };
  return {
    filters: [['docstatus', '!=', 2]],
    get_indicator: function (doc) {
      const status = doc.status || 'Unknown';
      return [__(status), status_color[status] || 'grey', `status,=,${status}`];
    },
  };
}

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

function set_charge_total(frm) {
  const charge_total = sumBy('charge_amount', frm.doc.charges);
  frm.set_value({ charge_total });
}

async function update_party_details(frm) {
  const { message } = await frappe.call({
    method: 'gg_custom.api.booking_order.update_party_details',
    args: { name: frm.doc.name },
  });
  frm.reload_doc();
}

function set_freight_amount(frm, cdt, cdn) {
  const {
    based_on,
    no_of_packages = 0,
    weight_charged = 0,
    rate = 0,
  } = frappe.get_doc(cdt, cdn);
  const qty =
    based_on === 'Packages'
      ? no_of_packages
      : based_on === 'Weight'
      ? weight_charged
      : 0;
  frappe.model.set_value(cdt, cdn, 'amount', qty * rate);
}

function set_total(field) {
  return function (frm, cdt, cdn) {
    frm.set_value(field, sumBy(field, frm.doc.freight));
    const { based_on } = frappe.get_doc(cdt, cdn);
    if (
      (field === 'no_of_packages' && based_on === 'Packages') ||
      (field === 'weight_charged' && based_on === 'Weight')
    ) {
      set_freight_amount(frm, cdt, cdn);
    }
  };
}

function set_total_amount(frm) {
  const { freight_total, charge_total } = frm.doc;
  frm.set_value('total_amount', freight_total + charge_total);
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
    el: frm.dashboard.add_section('<div />', 'History').children()[0],
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
        fieldtype: 'Check',
        fieldname: 'is_freight_invoice',
        label: __('Is Freight Invoice'),
      },
      {
        fieldtype: 'Link',
        fieldname: 'loading_operation',
        label: __('Loading Operation'),
        options: 'Loading Operation',
        depends_on: 'is_freight_invoice',
        get_query: function () {
          return {
            query: 'gg_custom.api.loading_operation.query',
            filters: { booking_order: frm.doc.name },
          };
        },
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

function create_payment(frm) {
  frappe.model.open_mapped_doc({
    method: 'gg_custom.api.booking_order.make_payment_entry',
    frm,
  });
}

function handle_deliver(frm) {
  return async function () {
    const dialog = new frappe.ui.Dialog({
      title: 'Deliver',
      fields: [
        {
          fieldtype: 'Select',
          fieldname: 'bo_detail',
          options: ['', ...frm.doc.freight.map((x) => x.name)],
          reqd: 1,
          label: 'Freight Row',
          change: async function () {
            const cdn = this.get_value();
            const { item_description } =
              frappe.get_doc('Booking Order Freight Detail', cdn) || {};
            dialog.set_value('item_description', item_description);
            const {
              message: { qty, unit },
            } = await frappe.call({
              method: 'gg_custom.api.booking_order.get_deliverable',
              args: { bo_detail: cdn, station: frm.doc.destination_station },
            });
            dialog.set_value('unit', unit);
            dialog.set_value('qty', qty);
          },
        },
        { fieldtype: 'Column Break' },
        {
          fieldtype: 'Small Text',
          fieldname: 'item_description',
          read_only: 1,
          label: 'Description',
        },
        { fieldtype: 'Section Break' },
        {
          fieldtype: 'Data',
          fieldname: 'unit',
          read_only: 1,
          label: 'Unit',
        },
        {
          fieldtype: 'Int',
          fieldname: 'qty',
          reqd: 1,
          label: 'Qty',
        },
      ],
    });
    dialog.set_primary_action('OK', async function () {
      try {
        const { bo_detail, qty, unit } = dialog.get_values();
        await frm.call('deliver', { bo_detail, qty, unit });
        frm.reload_doc();
        dialog.hide();
      } finally {
        frm.refresh();
      }
    });
    dialog.onhide = () => dialog.$wrapper.remove();
    dialog.show();
  };
}
