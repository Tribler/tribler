/*
Copyright (c) 2011 BitTorrent, Inc. All rights reserved.

Use of this source code is governed by a BSD-style that can be
found in the LICENSE file.
*/

//================================================================================
// LOGGER
//================================================================================

var Logger = {

	"element": null,
	"log_date": false,

	"init": function(element) {
		this.element = $(element);
	},

	"log": function() {
		if (!this.element) return;
		var text = Array.prototype.slice.call(arguments).join(" ");
		var dt = new Date();

		var YYYY = dt.getFullYear();
		var MM = dt.getMonth() + 1; MM = (MM < 10 ? "0" + MM : MM);
		var DD = dt.getDate(); DD = (DD < 10 ? "0" + DD : DD);

		var hh = dt.getHours(); hh = (hh < 10 ? "0" + hh : hh);
		var mm = dt.getMinutes(); mm = (mm < 10 ? "0" + mm : mm);
		var ss = dt.getSeconds(); ss = (ss < 10 ? "0" + ss : ss);

		var time = (
			(this.log_date ? YYYY + "-" + MM + "-" + DD + " " : "") +
			hh + ":" + mm + ":" + ss
		);

		this.element.grab(new Element("p")
			.grab(new Element("span.timestamp", {"text": "[" + time + "] "}))
			.appendText(text)
		);

		this.scrollBottom();
	},

	"scrollBottom": function() {
		if (!this.element) return;
		this.element.scrollTo(0, this.element.getScrollSize().y)
	},

	"setLogDate": function(log_date) {
		this.log_date = !!log_date;
	}
};

function log() {
	Logger.log.apply(Logger, arguments);
}

//================================================================================
// BROWSER CONSOLE
//================================================================================
/*
window.onerror = function(msg, url, linenumber) {
	log("JS error: [" + url.split("/").slice(-1)[0] + ":" + linenumber + "] " + msg);
	//return true;
};
*/

if (! window.console) { window.console = {};
console.log = function(str) {
	if (window.opera) {
		opera.postError(str);
	} else {
		log(str);
	}
};
}


if (! console.assert) {
console.assert = function() {
	var args = Array.from(arguments), expr = args.shift();
	if (!expr) {
		throw new Error(false);
	}
};
}

if (! console.time) {
var __console_timers__ = {};
console.time = function(name) {
	if (name == "") return;
	__console_timers__[name] = Date.now();
};
}

if (! console.timeEnd) {
console.timeEnd = function(name) {
	if (name == "" || !__console_timers__.hasOwnProperty(name)) return;
	console.log(name + ": " + (Date.now() - __console_timers__[name]) + "ms");
	delete __console_timers__[name];
};
}
