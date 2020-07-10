<template>
  <div class="row">
    <div class="col-sm-4 col-xs-12" v-for="section in sections" :key="section.title">
      <h6 :class="`indicator ${section.color}`">{{ section.title }}</h6>
      <div class="row small" v-for="param in section.body" :key="param.label">
        <div class="col-xs-8">{{ param.label }}</div>
        <div class="col-xs-4 bold">{{ param.value }}</div>
      </div>
    </div>
  </div>
</template>

<script>
function get_body(body) {
  if (!body) {
    return [];
  }
  return [
    {
      label: 'No of Packages',
      value: body.no_of_packages,
    },
    {
      label: 'Weight Actual',
      value: body.weight_actual,
    },
    {
      label: 'Goods Value',
      value: body.goods_value,
    },
  ];
}
export default {
  props: ['on_load', 'off_load', 'current'],
  data: function() {
    return {
      sections: [
        {
          title: 'On Loaded',
          color: 'lightblue',
          body: get_body(this.on_load),
        },
        {
          title: 'Off Loaded',
          color: 'orange',
          body: get_body(this.off_load),
        },
        {
          title: 'Currently Onboard',
          color: 'blue',
          body: get_body(this.current),
        },
      ],
    };
  },
};
</script>