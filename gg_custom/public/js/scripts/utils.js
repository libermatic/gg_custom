export function set_charge_type_query(frm) {
  frm.set_query('charge_type', 'charges', () => ({
    filters: { is_stock_item: 0 },
  }));
}

export function sumBy(prop, arr) {
  return (arr || []).reduce((a, x) => a + (x?.[prop] ?? 0), 0);
}
