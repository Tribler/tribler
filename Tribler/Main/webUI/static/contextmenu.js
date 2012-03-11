/*
Copyright (c) 2011 BitTorrent, Inc. All rights reserved.

Use of this source code is governed by a BSD-style that can be
found in the LICENSE file.
*/

var CMENU_SEP = 0;
var CMENU_CHILD = 1;
var CMENU_SEL = 2;
var CMENU_CHECK = 3;

var ELE_A = new Element("a");
var ELE_DIV = new Element("div");
var ELE_LI = new Element("li");
var ELE_UL = new Element("ul");

var ContextMenu = {

	"hideAfterClick": true,
	"hidden": true,

	"init": function(id) {
		this.element = ELE_DIV.clone(false)
			.addClass("CMenu")
			.setProperties({
				"class": "CMenu",
				"id": id
			})
			.inject(document.body)
			.addStopEvent("mousedown")
			.grab(ELE_UL.clone(false));
	},

	"add": function() {
		function clickEvent(fn) {
			return (function(ev) {
				if (ContextMenu.hideAfterClick)
					ContextMenu.hide();

				if (typeof(fn) == 'function')
					fn(ev);
			});
		}

		var items = Array.from(arguments);
		var menu = items[0];

		if (typeOf(menu) == 'element') {
			if (!menu.getParent().hasClass("CMenu")) return;
			items.splice(0, 1);
		}
		else {
			menu = this.element.getElement("ul");
		}

		items.each(function(item) {
			if (!item) return;

			var li = ELE_LI.clone(false);
			menu.adopt(li);

			switch (item[0]) {
				case CMENU_SEP:
					li.addClass("sep");
				break;

				case CMENU_SEL:
					li.adopt(ELE_A.clone(false)
						.addClass("sel")
						.set("text", item[1])
					);
				break;

				case CMENU_CHECK:
					li.adopt(ELE_A.clone(false)
						.addClass("check")
						.set("text", item[1])
						.addStopEvents({
							"mouseup": clickEvent(item[2]),
							"click": null
						})
					);
				break;

				case CMENU_CHILD:
					li.adopt(ELE_A.clone(false)
						.addClass("exp")
						.set("text", item[1])
					);

					var ul = ELE_UL.clone(false);
					var div = ELE_DIV.clone(false)
						.addClass("CMenu")
						.grab(ul);

					li.adopt(div).addStopEvents({
						"mouseenter": function(){ ContextMenu.show(this.getCoordinates(), div); },
						"mouseleave": function(){ ContextMenu.hide(div); }
					});
					for (var k = 0, len = item[2].length; k < len; k++)
						this.add(ul, item[2][k]);
				break;

				default:
					if (item[1] === undefined) {
						li.adopt(ELE_A.clone(false)
							.addClass("dis")
							.set("text", item[0])
						);
					}
					else {
						li.adopt(ELE_A.clone(false)
							.set("text", item[0])
							.addStopEvents({
								"mouseup": clickEvent(item[1]),
								"click": null
							})
						);
					}
			}
		}, this);
	},

	"clear": function() {
		this.element.getElement("ul").set("html", "");
		this.hideAfterClick = true;
	},

	"scroll": function(ev) {
		if (this.__scrolling__) return;
		this.__scrolling__ = true;

		var ul = this.getElement("ul");
		var ulc = ul.getChildren()[0];
		if (ulc) {
			var ulch = ulc.getHeight() / 2;

			var dpos = this.getCoordinates();
			var scrollMax = (dpos.height - ul.getHeight() - ul.getDimensions({computeSize: true})['padding-top']);

			var top;
			if (ev.page.y < dpos.top + ulch) {
				top = 0;
			}
			else if (dpos.bottom - ulch < ev.page.y) {
				top = scrollMax;
			}
			else {
				top = (scrollMax * (ev.page.y - dpos.top - ulch) / (dpos.height - ulch - ulch)).toFixed(0).toInt();
			}

			ul.setStyle("top", top);
		}

		this.__scrolling__ = false;
	},

	"show": function(rect, ele) {
		ele = ele || this.element;
		ele.setStyles({
			"height": undefined,
			"width": undefined,
			"left": 0,
			"top": 0
		});

		rect = Object.merge({x:0, y:0}, rect);
		if (typeof(rect.left) === 'undefined') rect.left = rect.x;
		if (typeof(rect.right) === 'undefined') rect.right = rect.x;
		if (typeof(rect.top) === 'undefined') rect.top = rect.y;
		if (typeof(rect.bottom) === 'undefined') rect.bottom = rect.y;

		// Show menu
		ele.show();
		this.hidden = false;

		// Get sizes
		var winSize = window.getSize();
		var cSize = ele.getDimensions({computeSize: true});
		var size = {x: cSize.totalWidth, y: cSize.totalHeight};
		if (size.x > winSize.x) {
			size.x = winSize.x;
			ele.setStyle("width", size.x);
		}

		// Correct background position for expandable menu items
		ele.getElements("> ul > li > a.exp").each(function(exp) {
			exp.setStyle("background-position", (size.x - 16) + "px center");
		});

		// Try to keep menu within window boundaries
		var x = rect.right;
		if (x + size.x > winSize.x) {
			if (size.x <= rect.left) {
				x = rect.left - size.x;
			}
			else {
				x = winSize.x - size.x;
			}
		}

		var y = rect.top;
		if (y + size.y > winSize.y) {
			if (size.y <= rect.bottom) {
				y = rect.bottom - size.y;
			}
			else {
				if (rect.bottom < winSize.y - rect.top) {
					ele.setStyle("height", winSize.y - rect.top - 5);
				}
				else {
					ele.setStyle("height", rect.bottom);
					y = 0;
				}
				ele.addStopEvent("mousemove", this.scroll);
			}
		}
		ele.addStopEvent("mousemove");

		// Position menu
		ele.setStyles({
			"left": x.max(0),
			"top": y.max(0)
		});
	},

	"hide": function(ele) {
		ele = ele || this.element;
		ele.hide();

		// Undo changes possibly made to element in show()
		ele.getElement("ul").setStyle("top");
		ele.removeEvents("mousemove");

		if (ele === this.element) {
			this.hidden = true;
			this.clear();
		}
	}

};
