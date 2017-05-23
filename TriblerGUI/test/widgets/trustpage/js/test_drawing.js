/**
 * This file tests the drawing.js file with unit tests
 */

assert = require("assert");
config = require("../../../../widgets/trustpage/js/style_config.js");
drawing = require("../../../../widgets/trustpage/js/drawing.js");

describe("drawing.js", function () {
    describe("getStrokeWidth", function () {
        var data = {
            "min_transmission": 40,
            "max_transmission": 100
        };
        it("total link data halfway between min and max transmission", function () {
            var link = {
                "amount_up": 30,
                "amount_down": 40
            };
            assert.equal((config.link.strokeWidthMax + config.link.strokeWidthMin) / 2,
                drawing.getStrokeWidth(link, data));
        });
        it("total link data equal to max transmission", function () {
            var link = {
                "amount_up": 60,
                "amount_down": 40
            };
            assert.equal(config.link.strokeWidthMax, drawing.getStrokeWidth(link, data));
        });
        it("total link data equal to min transmission", function () {
            var link = {
                "amount_up": 15,
                "amount_down": 25
            };
            assert.equal(config.link.strokeWidthMin, drawing.getStrokeWidth(link, data));
        });
    });

    describe("getStrokeWidth", function () {
        it("the middle of the interval is returned as the stroke width if the difference is 0", function () {
            var data = {
                "min_transmission": 100,
                "max_transmission": 100
            };
            assert.equal((config.link.strokeWidthMax + config.link.strokeWidthMin) / 2,
                drawing.getStrokeWidth(null, data));
        });
    });
});
