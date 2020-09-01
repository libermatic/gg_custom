import sumBy from 'lodash/sumBy';

export function loading_operation_booking_order() {
  return {
    booking_order: async function (frm, cdt, cdn) {
      const { booking_order } = frappe.get_doc(cdt, cdn);
      const { message: options } = await frappe.call({
        method: 'gg_custom.api.booking_order.get_description_options',
        args: { booking_order },
      });
      console.log(options);
    },
    loading_unit: set_booking_order_fields,
    no_of_packages: set_totals,
    weight_actual: set_totals,
    goods_value: set_totals,
    on_loads_remove: set_totals,
    off_loads_remove: set_totals,
  };
}

export function loading_operation() {
  return {
    setup: function (frm) {
      frm.set_query('shipping_order', ({ station }) => ({
        query: 'gg_custom.api.shipping_order.query',
        filters: { station, docstatus: 1 },
      }));
      frm.set_query(
        'booking_order',
        'on_loads',
        set_query_booking_order('on_load')
      );
      frm.set_query(
        'booking_order',
        'off_loads',
        set_query_booking_order('off_load')
      );
    },
    refresh: function (frm) {
      if (frm.doc.docstatus < 1) {
        frm.add_custom_button('Auto Load', async function () {
          if (!frm.doc.station) {
            frappe.msgprint('Please select Station first.');
            return;
          }
          await frm.call('get_on_loads');
          set_totals(frm);
        });
        frm.add_custom_button('Auto Unload', async function () {
          if (!frm.doc.shipping_order) {
            frappe.msgprint('Please select Shipping Order first.');
            return;
          }
          await frm.call('get_off_loads');
          set_totals(frm);
        });
      }
    },
  };
}

export function loading_operation_listview_settings() {
  return {
    filters: [['docstatus', '!=', 2]],
  };
}

function set_totals(frm) {
  ['no_of_packages', 'weight_actual', 'goods_value'].forEach((param) =>
    ['on_load', 'off_load'].forEach((type) => {
      const field = `${type}_${param}`;
      const table = frm.doc[`${type}s`] || [];
      frm.set_value(field, sumBy(table, param));
    })
  );
}

function set_query_booking_order(type) {
  return ({ station, shipping_order }) => {
    if (!station || !shipping_order) {
      frappe.throw(
        __('Cannot fetch Booking Orders without Station or Shipping Order')
      );
      return;
    }
    return {
      query: 'gg_custom.api.booking_order.query',
      filters: { type, station, shipping_order },
    };
  };
}

async function set_booking_order_fields(frm, cdt, cdn) {
  const { station, shipping_order } = frm.doc;
  const { booking_order, loading_unit, parentfield } = frappe.get_doc(cdt, cdn);
  const fields = ['no_of_packages', 'weight_actual', 'goods_value'];
  function get_args() {
    if (parentfield === 'on_loads') {
      return { name: booking_order, station };
    }
    if (parentfield === 'off_loads') {
      return { name: booking_order, shipping_order };
    }
  }
  if (booking_order && loading_unit) {
    const { message: details = {} } = await frappe.call({
      method: 'gg_custom.api.booking_order.get_order_details',
      args: get_args(),
    });
    const available =
      loading_unit === 'Packages'
        ? details.no_of_packages
        : loading_unit === 'Weight'
        ? details.weight_actual
        : 0;
    ['qty', 'available'].forEach((x) =>
      frappe.model.set_value(cdt, cdn, x, available)
    );
    fields.forEach((x) => frappe.model.set_value(cdt, cdn, x, details[x]));
    return;
  }
  [...fields, 'qty', 'available'].forEach((x) =>
    frappe.model.set_value(cdt, cdn, x, null)
  );
}

async function set_description_options(frm, cdt, cdn) {}
