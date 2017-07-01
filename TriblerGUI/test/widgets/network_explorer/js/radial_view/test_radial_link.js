/**
 * This file tests the radial_link.js file with unit tests
 */

assert = require("assert");
radial_link = require("TriblerGUI/widgets/network_explorer/js/radial_view/radial_link.js");

describe("radial_link.js", function () {

    describe("getStrokeWidth", function () {
        var links = new radial_link.RadialLinks(null, {
            strokeWidthMax : 10,
            strokeWidthMin: 2
        });
        links.graphData = {
            "min_transmission": 40,
            "max_transmission": 100
        };
        it("total link data halfway between min and max transmission", function () {
            var link = {
                "amount_up": 30,
                "amount_down": 40
            };
            assert.equal(6, links._calculateStrokeWidth(link));
        });
        it("total link data equal to max transmission", function () {
            var link = {
                "amount_up": 60,
                "amount_down": 40
            };
            assert.equal(10, links._calculateStrokeWidth(link));
        });
        it("total link data equal to min transmission", function () {
            var link = {
                "amount_up": 15,
                "amount_down": 25
            };
            assert.equal(2, links._calculateStrokeWidth(link));
        });
        it("the middle of the interval is returned as the stroke width if the difference is 0", function () {
            links.graphData = {
                "min_transmission": 100,
                "max_transmission": 100
            };
            assert.equal(6, links._calculateStrokeWidth(null));
        });
    });

});
