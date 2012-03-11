/*
Copyright (c) 2011 BitTorrent, Inc. All rights reserved.

Use of this source code is governed by a BSD-style that can be
found in the LICENSE file.
*/

var ELE_A = new Element("a");
var ELE_LI = new Element("li");
var ELE_SPAN = new Element("span");

var Tabs = new Class({

	"active": "",
	"tabs": {},
	"lazyshow": false,
	"tabchange": Function.from(),

	"initialize": function(ele, options) {
		this.element = $(ele);
		this.tabs = options.tabs;
		this.lazyshow = !!options.lazyshow;
		if (typeof(options.onChange) == 'function') {
			this.tabchange = options.onChange;
		}
		var $me = this;
		this.element.addStopEvent("click", function(ev) {
			var targ = ev.target;

			if (targ && (targ.get("tag") == "span"))
				targ = targ.getParent("a");

			if (targ && (targ.get("tag") == "a"))
				$me.show(targ.retrieve("showId"));
		});
	},

	"draw": function() {
		this.element.set("html", "");

		Object.each(this.tabs, function(text, id) {
			var ele = ELE_LI.clone(false);
			if (this.lazyshow) {
				ele.hide();

				var showCB = function() {
					ele.show();
					$(id).removeEvent("show", showCB);
				};

				$(id).addEvent("show", showCB);
			}

			this.element.adopt(ele
				.set("id", "tab_" + id)
				.adopt(ELE_A.clone(false)
					.setProperty("href", "#")
					.store("showId", id)
					.adopt(ELE_SPAN.clone(false)
						.adopt(ELE_SPAN.clone(false))
						.appendText(text)
					)
				)
			);
		}, this);

		return this;
	},

	"onChange": function() {
		if (arguments.length > 0)
			this.tabchange.apply(this, arguments);
		else
			this.tabchange.call(this, this.active);
	},

	"setNames": function(names) {
		Object.each(names, function(name, id) {
			var tab = $("tab_" + id);
			var icon = tab.getElement("span span");
			if (icon) icon.dispose();
			tab.getElement("span").set("html", name);
			if (icon) tab.getElement("span").grab(icon, "top");
		});

		return this;
	},

	"show": function(id) {
		if (!has(this.tabs, id)) return;

		Object.each(this.tabs, function(_, tab) {
			if (tab == id) {
				$(tab).show();
				$("tab_" + tab).addClass("selected");
			}
			else {
				$(tab).hide();
				$("tab_" + tab).removeClass("selected");
			}
		});

		this.active = id;
		this.onChange(id);
		return this;
	}

});
