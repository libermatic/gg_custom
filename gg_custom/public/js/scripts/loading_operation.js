import sumBy from 'lodash/sumBy';

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

export function loading_operation_booking_order() {
  return {
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
        frm.add_custom_button('Auto Load / Unload', async function () {
          if (!frm.doc.station || !frm.doc.shipping_order) {
            frappe.msgprint('Please select Station and Shipping Order first.');
            return;
          }
          await frm.call('get_loads');
          set_totals(frm);
        });
      }
    },
  };
}
