import { get_fields } from "./commom_fields";

export function booking_party(QuickEntryForm) {
  return class BookingPartyQuickEntryForm extends QuickEntryForm {
    render_dialog() {
      this.mandatory = [...this.mandatory, ...this.get_variant_fields()];
      super.render_dialog();
    }
    get_variant_fields() {
      return get_fields();
    }
  };
}
