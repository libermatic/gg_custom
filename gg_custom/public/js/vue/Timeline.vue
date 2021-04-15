<template>
  <div class="new-timeline">
    <div class="timeline-items">
      <div v-for="state in states" class="timeline-item" :key="state.datetime">
        <div class="timeline-dot" />
        <div class="timeline-content">
          <div class="message bold">
            {{ getFormattedDatetime(state.datetime) }}
          </div>
          <div class="message muted">
            {{ state.message }}
            <a v-if="state.link" :href="state.link">
              <i class="octicon octicon-chevron-right" />
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: ['history'],
  data: function () {
    return {
      states: [...this.history].reverse(),
    };
  },
  methods: {
    getFormattedDatetime: function (dstr) {
      const d = new Date(dstr);
      return `${frappe.datetime.obj_to_user(d)} ${frappe.datetime.get_time(d)}`;
    },
  },
};
</script>

<style scoped>
.message {
  color: var(--text-color);
}
.message > a {
  padding: 0 0.5em;
}
.muted {
  color: var(--text-muted);
}
</style>
