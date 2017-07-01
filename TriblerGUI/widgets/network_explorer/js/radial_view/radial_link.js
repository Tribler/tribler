if (typeof require !== "undefined") {
    var applyEventfulMixin = require("../support/eventful_mixin.js").applyEventfulMixin;
}

/**
 * The links between nodes in the Radial View.
 * @param svg - the parent svg element
 * @param {Object} options - configuration overrides for the links
 * @constructor
 */
function RadialLinks(svg, options) {

    applyEventfulMixin(this);

    var self = this,
        defaults = {};

    self.graphData = null;
    self.config = Object.assign({}, defaults, options || {});

    /**
     * Select all <svg.link> objects in the SVG
     */
    self.selectAll = function () {
        return svg.select(".links").selectAll(".link");
    };

    /**
     * Create, update and destroy the <svg.link> objects based on new data
     * @param {GraphData} newGraphData
     */
    self.onNewData = function (newGraphData) {
        self.graphData = newGraphData;

        var update = self.selectAll()
            .data(self.graphData.links, function (link) {
                return link.id;
            });

        self.destroy(update.exit());
        self.update(update);
        self.create(update.enter());
    };

    /**
     * Create the new <svg.link> objects based on entering data
     * @param enterSelection
     */
    self.create = function (enterSelection) {
        // Create <svg.link>
        var links = enterSelection
            .append("g")
            .attr("class", "link")
            .style("opacity", "0")
            .style("stroke", "transparent")

            // Apply stroke width
            .attr("stroke-width", function (link) {
                return self._calculateStrokeWidth(link);
            })

            // Bind mouse events
            .on("mouseover", self.getEventHandlers("mouseover"))
            .on("mousemove", self.getEventHandlers("mousemove"))
            .on("mouseout", self.getEventHandlers("mouseout"));

        // Append <line.link-source> to <svg.link>
        links.append("line")
            .attr("class", "link-source")
            .style("stroke", self.config.color);

        // Append <line.link-target> to <svg.link>
        links.append("line")
            .attr("class", "link-target")
            .style("stroke", self.config.color);

        // Fade-in
        links
            .transition()
            .duration(1000)
            .style("opacity", function (link) {
                return self._calculateOpacity(link);
            });

    };

    /**
     * Update existing <svg.link> objects based on updated data
     * @param updateSelection
     */
    self.update = function (updateSelection) {
        // Pass updated data through to all child elements using it
        updateSelection.each(function (newData) {
            var nodeElement = d3.select(this);
            nodeElement.select('.link-source').datum(newData);
            nodeElement.select('.link-target').datum(newData);
        });
        updateSelection
            .attr("stroke-width", function (d) {
                return self._calculateStrokeWidth(d);
            });
    };

    /**
     * Destroy existing <svg.link> objects based on exiting data
     * @param exitSelection
     */
    self.destroy = function (exitSelection) {
        exitSelection.remove();
    };

    /**
     * Update the positions of the links on each tick.
     */
    self.tick = function () {
        self.selectAll().each(function (link) {
            var separator = self._calculateSeparatorPositionWithOffset(link);

            // Part of line at the source
            d3.select(this).select(".link-source")
                .attr("x1", function (d) { return d.source.x; })
                .attr("y1", function (d) { return d.source.y; })
                .attr("x2", function () { return separator.x_from_source})
                .attr("y2", function () { return separator.y_from_source});

            // // Part of line at the target
            d3.select(this).select(".link-target")
                .attr("x1", function () { return separator.x_from_target })
                .attr("y1", function () { return separator.y_from_target; })
                .attr("x2", function (d) { return d.target.x; })
                .attr("y2", function (d) { return d.target.y; });
        });
    };

    /**
     * Highlights all links for which the filter function returns true, dims the others.
     * @param filterFunction
     */
    self.applyHighlight = function (filterFunction) {
        self.selectAll()
            .transition()
            .duration(self.config.highlightInDuration)
            .style("opacity", function (d) {
                return filterFunction(d) ? 1 : self.config.highlightDimmedOpacity
            });
    };

    /**
     * Restores the original opacity of all links.
     */
    self.unapplyHighlight = function () {
        self.selectAll()
            .transition()
            .duration(self.config.highlightOutDuration)
            .style("opacity", function (d) {
                return self._calculateOpacity(d);
            });
    };

    /**
     * Calculate the position of the separator.
     * @param {GraphLink} link
     * @returns {{x_from_source: x, y_from_source: x, x_from_target: x, y_from_target: x}}
     * @private
     */
    self._calculateSeparatorPositionWithOffset = function (link) {
        var s = link.source,
            t = link.target,
            offset = 1 / Math.max(1, distance2D(s, t)),
            ratio = link.ratio;
        return {
            x_from_source: xAtFraction(s.x, t.x, ratio - offset),
            y_from_source: xAtFraction(s.y, t.y, ratio - offset),
            x_from_target: xAtFraction(t.x, s.x, 1 - ratio - offset),
            y_from_target: xAtFraction(t.y, s.y, 1 - ratio - offset)
        };
    };

    /**
     * Calculate the link opacity.
     *
     * For parent-child links the opacity decreases with the distance to
     * the focus node. For other links the opacity is always at a minimum.
     *
     * @param link
     * @returns {number} opacity
     */
    self._calculateOpacity = function (link) {
        var t1 = link.source.treeNode,
            t2 = link.target.treeNode,
            minDepth = Math.min(t1.depth, t2.depth),
            opacityByDepth = 1 - minDepth * self.config.opacityDecrementPerLevel;

        return (t1.parent === t2 || t2.parent === t1) ? Math.max(opacityByDepth, self.config.opacityMinimum) : self.config.opacityMinimum;
    };

    /**
     * Get the stroke width based on the total amount of transmitted data over the link,
     * relative to the other links in the graph
     * @param link the link to get the width for
     * @returns the width of the link
     */
    self._calculateStrokeWidth = function (link) {
        // The difference between the minimum and maximum data links
        var transmissionDifference = self.graphData.max_transmission - self.graphData.min_transmission;

        // The difference between the minimum and maximum stroke width
        var widthDifference = self.config.strokeWidthMax - self.config.strokeWidthMin;

        // If exactly the same amount is transmitted between all peers, return the middle of the width interval
        if (transmissionDifference === 0)
            return (self.config.strokeWidthMax + self.config.strokeWidthMin) / 2;

        // The total transmission of the current link
        var linkTotal = link.amount_up + link.amount_down;

        // The fraction of the current link in the network
        var fraction = (linkTotal - self.graphData.min_transmission) / transmissionDifference;

        // The width based on the fraction and the interval
        return fraction * widthDifference + self.config.strokeWidthMin;
    };

}

/**
 * Export functions so Mocha can test it
 */
if (typeof module !== 'undefined') {
    module.exports = {
        RadialLinks: RadialLinks
    };
}
