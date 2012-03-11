/*
Copyright (c) 2011 BitTorrent, Inc. All rights reserved.

Use of this source code is governed by a BSD-style that can be
found in the LICENSE file.
*/
(function($){

var DialogManager = {

	"winZ": 500,
	"items": {},
	"showing": [],

	"init": function() {
		// Create popup dialog
		var dlgPopupId = this.create("Popup");
		this.add("Popup");

		$(dlgPopupId).getElement(".dlg-body").adopt(
			new Element("span", {id: dlgPopupId + "-message"}),
			new Element("div.textarea_wrap").grab(
				new Element("textarea.wide", {
					id: dlgPopupId + "-input",
					styles: { marginTop: "5px" }
				}).setProperty("wrap", "off")
			)
		);
	},

	"create": function(id) {
		var dlgId = "dlg" + id;

		var dlgWindow = new Element("div.dlg-window", {id: dlgId}).adopt(
			  new Element("a.dlg-close", {href: "#"})
			, new Element("div.dlg-head", {id: dlgId + "-head"})
			, new Element("form", {action: ""}).adopt(
				  new Element("div.dlg-body")
				, new Element("div.dlg-foot")
			).addEvent("submit", Function.from(false))
		).inject(document.body);

		return dlgId;
	},

	"popup": function(options) {
		options = options || {};
		var opt;

		var id = "Popup"
		var dlgId = "dlg" + id;

		var dlgWin = $(dlgId);
		var dlgHead = dlgWin.getElement(".dlg-head");
		var dlgFoot = dlgWin.getElement(".dlg-foot");

		var dlgMsg = $(dlgId + "-message");
		var dlgInput = $(dlgId + "-input");

		// Clear previous configuration
		if ((opt = dlgHead.retrieve("icon"))) {
			dlgHead.removeClass(opt);
		}

		dlgFoot.set("html", "");

		// Set text
		dlgHead.set("text", options.title || "");
		dlgMsg.set("text", options.message || "");
		dlgInput.set("value", options.input || "");

		// Set icon
		if ((opt = options.icon || "")) {
			dlgHead.store("icon", opt);
			dlgHead.addClass(opt);
		}

		// Set buttons
		var btnFocus;
		if ((opt = options.buttons || []).length) {
			var $me = this;
			opt.each(function(btn) {
				var ele = new Element("input.btn", {
					type: btn.submit ? "submit" : "button",
					value: btn.text
				}).addStopEvent("click", function(ev) {
					if (typeof(btn.click) === 'function') {
						if (btn.click(dlgInput.get("value")) === false) {
							return;
						}
					}

					$me.hide(id);
				});
				
				dlgFoot.grab(ele).appendText(" ");
				if (btn.focus) btnFocus = ele;
			})
		}

		// Set dimensions
		var width = [options.width, "25em"].pick();
		dlgWin.setStyle("width", width);
		if (undefined !== options.input) {
			dlgInput.measure(function() {
				var lines = (options.input.split("\n").length || 1).min(5);
				dlgInput.setStyle("height", (lines * 1.3) + "em");

				// Make room for horizontal scrollbar
				var dims = dlgInput.getDimensions({computeSize: true});
				var bordY = dims["border-bottom-width"] + dims["border-top-width"];
				var sbHeight = dlgInput.offsetHeight - (dlgInput.clientHeight + bordY);

				if (sbHeight > 0) {
					dlgInput.setStyle("height", dlgInput.offsetHeight - bordY + sbHeight);
				}
			});
		}

		// Finish
		this.items[id].modal = !![options.modal, true].pick();
		this.show(id);

		if (undefined !== options.input) {
			dlgInput.show();
			dlgInput.select();
			dlgInput.focus();
		}
		else {
			dlgInput.hide();
			if (btnFocus) {
				btnFocus.focus();
			}
		}
	},

	"add": function(id, isModal, showCB) {
		if (has(this.items, id)) return;

		this.items[id] = {"modal": !!isModal, "onShow": showCB};

		var dlgId = "dlg" + id;
		if (! $(dlgId)) { return; }
		$(dlgId)
			.addEvent("mousedown", this.bringToFront.bind(this, id))
			.getElement(".dlg-close").addStopEvent("click", this.hide.bind(this, id));

		new Drag(dlgId, {
			"handle": dlgId + "-head",
			"snap": 1
		});
	},

	"show": function(id) {
		if (!ContextMenu.hidden)
			ContextMenu.hide();

		this.bringToFront(id);

		if (this.items[id].modal)
			$("modalbg").show().setStyle("zIndex", this.winZ);
		else if (!this.modalIsVisible())
			$("modalbg").hide();

		if (this.isOffScreen(id))
			$("dlg" + id).centre();

		if (this.items[id].onShow)
			this.items[id].onShow();
	},

	"hide": function(id) {
		var dlgWin = $("dlg" + id);

		dlgWin.hide();
		if (dlgWin.contains(document.activeElement)) {
			document.activeElement.blur();
		}

		this.showing = this.showing.erase(id);

		if (this.items[id].modal) {
			var topModal = this.getTopModal();
			if (topModal)
				$("modalbg").setStyle("zIndex", $("dlg" + topModal).getStyle("zIndex"));
			else
				$("modalbg").hide();
		}

		if (this.showing.length)
			this.bringToFront(this.showing.getLast());
	},

	"hideTopMost": function(fireClose) {
		if (!this.showing.length) return;

		var id = this.showing.pop();
		this.hide(id);

		if (fireClose)
			$("dlg" + id).getElement(".dlg-close").fireEvent("click", { stop: Function.from() });
	},

	"isOffScreen": function(id) {
		var threshX = 150, threshY = 50;
		var winSize = window.getSize();
		var head = $("dlg" + id + "-head").getCoordinates();

		return (
			(head.left > winSize.x - threshX) ||
			(head.right < threshX) ||
			(head.top > winSize.y - threshY) ||
			(head.bottom < threshY)
		);
	},

	"bringToFront": function(id) {
		this.showing = this.showing.erase(id);

		if (this.showing.length)
			$("dlg" + this.showing.getLast()).removeClass("dlg-top");

		this.showing.push(id);
		$("dlg" + id).addClass("dlg-top").setStyle("zIndex", ++this.winZ);
	},

	"getTopModal": function() {
		for (var i = this.showing.length - 1; i >= 0; --i) {
			if (this.items[this.showing[i]].modal) {
				return this.showing[i];
			}
		}
		return null;
	},

	"modalIsVisible": function() {
		return !!this.getTopModal();
	}
};

window.DialogManager = DialogManager;

})(document.id); // mootools $ is document.id
