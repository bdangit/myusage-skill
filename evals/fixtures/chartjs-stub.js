/* Chart.js stub for offline testing — replaces full Chart.js library */
(function(global) {
  'use strict';

  function Chart(ctx, config) {
    this.ctx = ctx;
    this.config = config;
    this.data = config.data || {};
    this.options = config.options || {};
    // Stub: do nothing with the canvas
    if (ctx && ctx.getContext) {
      var c = ctx.getContext('2d');
      if (c) { c.clearRect(0, 0, ctx.width || 1, ctx.height || 1); }
    }
  }
  Chart.prototype.destroy = function() {};
  Chart.prototype.update = function() {};
  Chart.defaults = {
    color: '#94a3b8',
    borderColor: '#2d3148',
    font: { family: 'system-ui' }
  };
  Chart.register = function() {};

  global.Chart = Chart;
})(typeof window !== 'undefined' ? window : this);
