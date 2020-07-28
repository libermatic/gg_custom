<template>
  <div class="timeline">
    <div class="timeline-items">
      <div
        v-for="state in states"
        :class="`media timeline-item notification-content ${getColor(state.status)}`"
        :key="state.datetime"
      >
        <div class="pull-left media-body">
          <div class="media-content-wrapper">
            <div class="small">
              <div class="message bold">{{ getFormattedDatetime(state.datetime) }}</div>
              <div class="message">
                {{ state.message }}
                <a v-if="state.link" :href="state.link">
                  <i class="octicon octicon-chevron-right" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
const status_color = {
  Booked: 'darkgrey',
  Cancelled: 'red',
  Collected: 'green',
  Completed: 'green',
  Draft: 'red',
  Moving: 'blue',
  Loaded: 'lightblue',
  Operation: 'lightblue',
  Stopped: 'orange',
  Unknown: 'darkgrey',
  Unloaded: 'orange',
};
export default {
  props: ['history'],
  data: function() {
    return {
      states: [...this.history].reverse(),
    };
  },
  methods: {
    getFormattedDatetime: function(dstr) {
      const d = new Date(dstr);
      return `${frappe.datetime.obj_to_user(d)} ${frappe.datetime.get_time(d)}`;
    },
    getColor: function(status) {
      return status_color[status] || '';
    },
  },
};
</script>

<style scoped>
.timeline::before {
  top: -1em;
  bottom: 0;
}
.timeline-item {
  margin: 1em 0;
}
.timeline-item.notification-content.red::before {
  background-color: #ff5858;
}
.timeline-item.notification-content.orange::before {
  background-color: #ffa00a;
}
.timeline-item.notification-content.blue::before {
  background-color: #5e64ff;
}
.timeline-item.notification-content.lightblue::before {
  background-color: #7cd6fd;
}
.timeline-item.notification-content.green::before {
  background-color: #98d85b;
}
.timeline-item.notification-content.darkgrey::before {
  background-color: #b8c2cc;
}

.message {
  color: #36414c;
}
.message > a {
  padding: 0 0.5em;
}
</style>