import ShippingOrderLoad from '../vue/ShippingOrderLoad.vue';
import Timeline from '../vue/Timeline.vue';

export function shipping_order() {
  return {
    setup: function (frm) {
      frm.set_query('transit_stations', (doc) => ({
        filters: {
          name: [
            'not in',
            [
              doc.initial_station,
              doc.final_station,
              ...(doc.transit_stations || []).map((x) => x.station),
            ],
          ],
        },
      }));
      frm.set_query('vehicle', (doc) => ({ filters: { disabled: 0 } }));
      frm.set_query('driver', (doc) => ({ filters: { status: 'Active' } }));
    },
    refresh: function (frm) {
      if (frm.doc.docstatus === 1) {
        const { status } = frm.doc;
        if (!['Completed', 'Cancelled'].includes(status)) {
          frm
            .add_custom_button('Perform Loading Operation', () => {
              frappe.new_doc('Loading Operation', {
                shipping_order: frm.doc.name,
                station: frm.doc.current_station,
              });
            })
            .toggleClass('btn-primary', status === 'Stopped');
        }
        if (status === 'Stopped') {
          frm.add_custom_button('Move', handle_movement_action(frm));
          frm.add_custom_button('Complete', () =>
            frappe.confirm(
              'Are you sure you want to Complete this Shipping Order?',
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
        } else if (status === 'In Transit') {
          frm.add_custom_button('Stop', handle_movement_action(frm));
        }
      }
      if (frm.doc.docstatus > 0) {
        const { dashboard_info } = frm.doc.__onload || {};
        if (dashboard_info) {
          render_dashboard(frm, dashboard_info);
        }
      }
    },
  };
}

export function shipping_order_listview_settings() {
  const status_color = {
    Draft: 'red',
    'In Transit': 'blue',
    Stopped: 'orange',
    Completed: 'green',
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

function handle_movement_action(frm) {
  return async function () {
    const {
      message: { status: current_status, current_station, next_station } = {},
    } = await frappe.db.get_value(frm.doc.doctype, frm.doc.name, [
      'status',
      'current_station',
      'next_station',
    ]);
    if (!['Stopped', 'In Transit'].includes(current_status)) {
      frappe.throw(
        __(
          'Movement status can only be toggled between ' +
            '<strong>Stopped</strong> and <strong>In Transit</strong>.'
        )
      );
      return;
    }

    const route = [
      frm.doc.initial_station,
      ...frm.doc.transit_stations.map((x) => x.station),
      frm.doc.final_station,
    ];
    function get_fields() {
      if (current_status === 'In Transit') {
        const idx = route.findIndex((x) => x === next_station);
        return [
          {
            fieldtype: 'Select',
            fieldname: 'next_station',
            label: 'Stop at Station',
            options: ['', ...route],
            default: route[idx],
            reqd: 1,
          },
        ];
      }
      if (current_status === 'Stopped') {
        const idx = route.findIndex((x) => x === current_station) + 1;
        return [
          {
            fieldtype: 'Data',
            fieldname: 'current_station',
            read_only: 1,
            label: 'Current Station',
            default: current_station,
          },
          {
            fieldtype: 'Select',
            fieldname: 'next_station',
            label: 'Go to Station',
            options: ['', ...route.slice(idx)],
            default: route[idx],
            reqd: 1,
          },
        ];
      }
      return [];
    }

    const dialog = new frappe.ui.Dialog({
      title: current_status === 'Stopped' ? 'Start' : 'Stop',
      fields: get_fields(),
    });
    dialog.set_primary_action('OK', async function () {
      const station = dialog.get_value('next_station');
      if (current_status === 'In Transit') {
        await frm.call('stop', { station });
      } else if (current_status === 'Stopped') {
        await frm.call('start', { station });
      }
      frm.reload_doc();
      dialog.hide();
    });
    dialog.onhide = () => dialog.$wrapper.remove();
    dialog.show();
  };
}

function render_dashboard(frm, dashboard_info) {
  const props = { ...dashboard_info };
  new Vue({
    el: frm.dashboard.add_section('<div />').children()[0],
    render: (h) => h(ShippingOrderLoad, { props }),
  });

  new Vue({
    el: frm.dashboard.add_section('<div />').children()[0],
    render: (h) => h(Timeline, { props }),
  });

  frm.dashboard.transactions_area
    .find('.document-link[data-doctype="Booking Order"] > .btn-new')
    .hide();
}
