import * as R from 'ramda';

export function set_charge_type_query(frm) {
  frm.set_query('charge_type', 'charges', () => ({
    filters: { is_stock_item: 0 },
  }));
}

export const sumBy = R.compose(
  R.reduce((a, x) => a + (x ?? 0), 0),
  R.pluck
);
