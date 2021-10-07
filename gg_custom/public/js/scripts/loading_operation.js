import sumBy from 'lodash/sumBy';

export function loading_operation_booking_order() {
  return {
    loading_unit: set_qtys,
    no_of_packages: set_totals,
    weight_actual: set_totals,
    on_loads_remove: set_totals,
    off_loads_remove: set_totals,
    bo_detail: set_booking_order_fields,
  };
}

export function loading_operation() {
  return {
    onload: function (frm) {
      frm.ignore_doctypes_on_cancel_all = ['Sales Invoice'];
    },
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
      ['on_loads', 'off_loads'].forEach((parentfield) =>
        frm.set_query('bo_detail', parentfield, (doc, cdt, cdn) => {
          const { booking_order: parent } = frappe.get_doc(cdt, cdn);
          return { filters: { parent } };
        })
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
      if (
        frm.doc.docstatus === 1 &&
        frm.doc.on_loads &&
        frm.doc.on_loads.length > 0
      ) {
        frm.add_custom_button(
          'Remove On Loaded Booking Orders',
          async function () {
            let data = [];
            const dialog = new frappe.ui.Dialog({
              title: 'Remove Booking Orders',
              fields: [
                {
                  fieldname: 'on_loads',
                  fieldtype: 'Table',
                  label: 'On Load',
                  cannot_add_rows: true,
                  in_place_edit: true,
                  reqd: 1,
                  data,
                  get_data: () => {
                    return data;
                  },
                  fields: [
                    {
                      fieldtype: 'Data',
                      fieldname: 'docname',
                      read_only: 1,
                      hidden: 1,
                    },
                    {
                      fieldtype: 'Read Only',
                      fieldname: 'booking_order',
                      label: 'Booking Order',
                      in_list_view: 1,
                    },
                    {
                      fieldtype: 'Read Only',
                      fieldname: 'bo_detail',
                      label: 'BO Detail',
                      in_list_view: 1,
                    },
                    {
                      fieldtype: 'Read Only',
                      fieldname: 'description',
                      label: 'Description',
                      in_list_view: 1,
                    },
                  ],
                },
              ],
              primary_action: async function () {
                const remaining = this.get_values()['on_loads'].map(
                  ({ docname }) => docname
                );
                const booking_orders = frm.doc.on_loads.filter(
                  ({ name }) => !remaining.includes(name)
                );
                try {
                  frappe.dom.freeze();
                  this.get_primary_btn().toggleClass('hidden', true);
                  if (booking_orders.length > 0) {
                    await frm.call('remove_booking_orders', { booking_orders });
                    frm.reload_doc();
                    refresh_field('on_loads');
                    frappe.show_alert({
                      message: `Booking Orders ${booking_orders
                        .map((x) => x.booking_order)
                        .join(
                          ', '
                        )} removed. Invoices might also have been cancelled.`,
                      indicator: 'green',
                    });
                  }
                  this.hide();
                } finally {
                  frappe.dom.unfreeze();
                }
              },
              primary_action_label: 'Update',
            });
            frm.doc.on_loads.forEach(
              ({ name: docname, booking_order, bo_detail, description }) => {
                dialog.fields_dict.on_loads.df.data.push({
                  docname,
                  booking_order,
                  bo_detail,
                  description,
                });
                data = dialog.fields_dict.on_loads.df.data;
                dialog.fields_dict.on_loads.grid.refresh();
              }
            );
            dialog.show();
          }
        );
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
  ['no_of_packages', 'weight_actual'].forEach((param) =>
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
  const { bo_detail, loading_unit, parentfield } = frappe.get_doc(cdt, cdn);
  const fields = ['description', 'no_of_packages', 'weight_actual'];
  function get_args() {
    if (parentfield === 'on_loads') {
      return { bo_detail, loading_unit, station };
    }
    if (parentfield === 'off_loads') {
      return { bo_detail, loading_unit, shipping_order };
    }
  }
  if (bo_detail) {
    const { message: details = {} } = await frappe.call({
      method: 'gg_custom.api.booking_order.get_order_details',
      args: get_args(),
    });
    fields.forEach((x) => frappe.model.set_value(cdt, cdn, x, details[x]));
    set_qtys(frm, cdt, cdn);
    return;
  }
  [...fields].forEach((x) => frappe.model.set_value(cdt, cdn, x, null));
  set_qtys(frm, cdt, cdn);
}

function set_qtys(frm, cdt, cdn) {
  const { loading_unit, no_of_packages, weight_actual } = frappe.get_doc(
    cdt,
    cdn
  );
  const available =
    loading_unit === 'Packages'
      ? no_of_packages
      : loading_unit === 'Weight'
      ? weight_actual
      : 0;
  ['qty', 'available'].forEach((x) =>
    frappe.model.set_value(cdt, cdn, x, available)
  );
}
