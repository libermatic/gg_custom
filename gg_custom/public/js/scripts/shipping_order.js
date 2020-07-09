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
    },
    refresh: function (frm) {
      if (frm.doc.docstatus === 1) {
        frm.add_custom_button('Stop / Start', handle_movement_action(frm));
        frm.add_custom_button('Perform Loading Operation', () => {
          frappe.new_doc('Loading Operation', {
            shipping_order: frm.doc.name,
            station: frm.doc.current_station,
          });
        });
      }
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
