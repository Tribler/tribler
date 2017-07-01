if (typeof require !== "undefined") {
    var d3 = require("TriblerGUI/widgets/network_explorer/js/d3/d3.v4.min");
    var config = require("TriblerGUI/widgets/network_explorer/js/style_config");
}

/**
 * Filters the nodes on which the given force is applied using a provided filter callback.
 *
 * @param force
 * @param filter function (nodes) {}
 */
function filterForceNodes(force, filter) {
    var init = force.initialize;
    force.initialize = function (nodes) {
        init(nodes.filter(filter));
    }
}

/**
 * Group the list by given key attribute.
 *
 * @param list: the list from which elements have to be grouped
 * @param key: the attribute on which the list elements have to be grouped
 * @returns a dictionary with elements grouped by attribute value
 */
function groupBy(list, key) {
    return list.reduce(function (rv, x) {
        (rv[x[key]] = rv[x[key]] || []).push(x);
        return rv;
    }, {});
}

/**
 * Format a byte value depending on its size.
 *
 * @param bytes
 */
function formatBytes(bytes) {

    var sizes = config.byteUnits;

    var i = 0;

    while (Math.abs(bytes) >= Math.pow(10, (i + 1) * 3) && (i + 1) < sizes.length) i++;

    return parseFloat(Math.round((1.0 * bytes) / Math.pow(10, (i - 1) * 3)) / 1000).toPrecision(4) + " " + sizes[i];
}

/**
 * Returns the point x on line x0 to x1 at a given fraction
 * @param x0
 * @param x1
 * @param ratio
 * @returns x
 */
function xAtFraction(x0, x1, ratio) {
    return x0 + (x1 - x0) * ratio;
}

/**
 * Calculate the distance between 2 positions in 2D
 * @param {{x: number, y : number}} positionA
 * @param {{x: number, y : number}} positionB
 * @returns {number} - the distance
 */
function distance2D(positionA, positionB) {
    return Math.sqrt(Math.pow(positionB.x - positionA.x, 2) + Math.pow(positionB.y - positionA.y, 2));
}

/**
 * Replace variable bindings in brackets inside given string with given substitutions
 * @example substituteString("Hello {name}", {name: "Joe"}) returns "Hello Joe"
 * @param {String} str - the subject of replacement
 * @param {Object} substitutions - the key-value pairs
 * @returns {String} the resulting string
 */
function substituteString(str, substitutions) {
    if(!substitutions instanceof Object) return str;
    for (var key in substitutions) {
        str = str.replace(new RegExp("{" + key + "}","g"), substitutions[key]);
    }
    return str;
}

/**
 * Set the first character of the provided string to uppercase.
 * @param {string} str
 * @returns {string}
 */
function ucfirst(str) {
    return (str.length > 0) ? (str.substr(0, 1).toUpperCase() + str.substr(1)) : "";
}

/**
 * Export functions so Mocha can test it
 */
if (typeof module !== 'undefined') {
    module.exports = {
        filterForceNodes: filterForceNodes,
        groupBy: groupBy,
        formatBytes: formatBytes,
        xAtFraction: xAtFraction,
        distance2D: distance2D,
        substituteString: substituteString
    };
}
