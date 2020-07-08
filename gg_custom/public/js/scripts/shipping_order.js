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
              ...doc.transit_stations.map((x) => x.station),
            ],
          ],
        },
      }));
    },
  };
}
