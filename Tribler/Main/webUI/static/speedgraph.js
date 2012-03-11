/*
Copyright (c) 2011 BitTorrent, Inc. All rights reserved.

Use of this source code is governed by a BSD-style that can be
found in the LICENSE file.
*/

var SpeedGraph = new Class({

	"element": null,
	"plot": null,

	"maxDataInterval": 600 * 1000, // milliseconds
	"maxShowInterval": -1,

	"create": function(id) {
		this.element = $(id);

		this.plot = new Flotr.Plot(this.element, [{ data: [] }, { data: [] }], {
			"colors" : ["#EE0000", "#00AA00"],
			"legend" : {
				"position": 'nw'
			},
			"lines" : {
				"show": true,
				"lineWidth": 1
			},
			"xaxis" : {
				"tickSize" : 60,
				"tickFormatter" : function(n) {
					return (new Date(Number(n))).format('%H:%M:%S');
				}
			},
			"yaxis" : {
				"min": 0,
				"minMaxTickSize": 512,
				"tickFormatter": function(n) {
					return (parseInt(n).toFileSize() + g_perSec);
				}
			},
			"grid": {
				"color": "#868686"
			},
			"shadowSize": 0
		});
	},

	"draw": function() {
		if (!(utWebUI.config || {}).showDetails || utWebUI.mainTabs.active != "mainInfoPane-speedTab") return;
		this.plot.repaint();
	},

	"resizeTo": function(w, h) {
		var style = {};
		if (typeof(w) === 'number' && w > 0)
			style.width = w;
		if (typeof(h) === 'number' && h > 0)
			style.height = h;

		this.element.setStyles(style);
		this.draw();
	},

	"showLegend": function(show) {
		this.plot.options.legend.show = !!show;
		this.draw();
	},

	"setLabels": function(upLabel, downLabel) {
		if (typeof(upLabel) !== 'undefined')
			this.plot.series[0].label = upLabel;
		if (typeof(downLabel) !== 'undefined')
			this.plot.series[1].label = downLabel;
	},

	"addData": function(upSpeed, downSpeed) {
		var now = Date.now();

		var dataUp = this.plot.series[0].data;
		var dataDown = this.plot.series[1].data;

		dataUp.push([now, upSpeed]);
		dataDown.push([now, downSpeed]);

		while ((now - dataUp[0][0]) > this.maxDataInterval) {
			dataUp.shift();
			dataDown.shift();
		}

		this.plot.options.xaxis.min = now - (
			0 < this.maxShowInterval && this.maxShowInterval < this.maxDataInterval
				? this.maxShowInterval
				: this.maxDataInterval
		);

		this.draw();
	}
});
