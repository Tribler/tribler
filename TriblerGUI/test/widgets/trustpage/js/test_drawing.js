/**
 * This file tests the drawing.js file with unit tests
 */
assert = require("assert");
drawing = require("../../../../widgets/trustpage/js/drawing.js");

describe("drawing.js", function () {
    describe("getStrokeWidth", function () {
        it("the middle of the interval is returned as the stroke width if the difference is 0", function () {
            var data = {
                "min_transmission": 100,
                "max_transmission": 100
            };
            assert.equal(6, drawing.getStrokeWidth(null, data));
        });
    });
    describe("getStrokeWidth", function () {
        it("the function returns the correct width on sample data", function () {
            var data = {
                "min_transmission": 20,
                "max_transmission": 100
            };
            var link = {
                "amount_up": 15,
                "amount_down": 35
            };
            assert.equal(5, drawing.getStrokeWidth(link, data));
        });
    });
});
