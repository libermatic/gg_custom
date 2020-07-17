export function set_charge_type_query(frm) {
  frm.set_query('charge_type', 'charges', () => ({
    filters: { is_stock_item: 0 },
  }));
}
