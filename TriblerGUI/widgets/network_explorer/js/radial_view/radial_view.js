/**
 * The Radial View of the Network Explorer.
 * @param svg
 * @param {Object} settings - override of the defaults
 * @constructor
 */
function RadialView(svg, settings) {

    var self = this;

    var defaults = {
        center_x: svg.attr("width") / 2,
        center_y: svg.attr("height") / 2
    };

    self.links = null;
    self.nodes = null;
    self.config = Object.assign({}, defaults, settings || {});
    self.hoverTimeout = null;

    /**
     * Set-up the <svg> with rings and bind all events of nodes and links.
     */
    self.initialize = function () {

        // Position the origin in the center of the SVG
        self.container = svg.append("g").attr("id", "graph-center")
            .attr("transform", "translate(" + self.config.center_x + "," + self.config.center_y + ")");

        for (var i = 1; i <= self.config.neighbor_level; i++)
            self._drawNeighborRing(self.config.radius_step * i);

        self.container.append("g").attr("class", "links");
        self.container.append("g").attr("class", "nodes");
        self.container.append("g").attr("class", "labels");

        self.links = new RadialLinks(self.container, config.link);
        self.nodes = new RadialNodes(self.container, config.node);
        self.inspector = new RadialInspector(d3.select("#inspector"), config);

        self.nodes.bind("click", function (node) {
            self.nodes.unapplyHighlight();
            self.links.unapplyHighlight();
        });

        self.nodes.bind("mouseover", function (targetNode) {
            self.delayedHover(function () {
                self.inspector.displayNodeInfo(targetNode, self.nodes);

                // Highlight links attached to target node
                self.links.applyHighlight(function (d) {
                    return d.source_pk === targetNode.public_key
                        || d.target_pk === targetNode.public_key;
                });

                // Highlight target node
                self.nodes.applyHighlight(function (node) {
                    return node.public_key === targetNode.public_key;
                });
            }, self.config.hover_in_delay);
        });

        self.nodes.bind("mouseout", function () {
            self.delayedHover(function () {
                self.inspector.displayNetworkInfo();
                self.links.unapplyHighlight();
                self.nodes.unapplyHighlight();
            }, self.config.hover_out_delay);
        });

        self.links.bind("mouseover", function (targetLink) {
            self.delayedHover(function () {
                self.inspector.displayLinkInfo(targetLink);

                // Highlight target link
                self.links.applyHighlight(function (link) { return link === targetLink; });

                // Highlight nodes of target link
                self.nodes.applyHighlight(function (node) {
                    return targetLink.source.public_key === node.public_key || targetLink.target.public_key === node.public_key;
                });
            }, self.config.hover_in_delay);
        });

        self.links.bind("mouseout", function () {
            self.delayedHover(function () {
                self.links.unapplyHighlight();
                self.nodes.unapplyHighlight();
                self.inspector.displayNetworkInfo();
            }, self.config.hover_out_delay);
        });

        return self;
    };

    /**
     * Pass the data to the nodes and edges.
     * @param {GraphData} newGraphData
     */
    self.onNewData = function (newGraphData) {
        self.nodes.onNewData(newGraphData);
        self.links.onNewData(newGraphData);
        self.inspector.onNewData(newGraphData);

        d3.select('#back-to-you-button')
            .attr('class', newGraphData.focus_node.is_user ? 'disabled' : '');
    };

    /**
     * Pass the tick to the nodes and edges.
     */
    self.tick = function () {
        self.links.tick();
        self.nodes.tick();
    };

    /**
     * Call a given callback after a period of time, overwriting a previously set callback.
     *
     * Many hover events will fire, causing a callback to be assigned before the previous callback is fired. This may
     * cause conflicts in the view (flickering). Therefore, any unfired hover callback must be cancelled before a new
     * one is set.
     * @param callback
     * @param delay
     */
    self.delayedHover = function (callback, delay) {
        if (self.hoverTimeout) clearTimeout(self.hoverTimeout);

        self.hoverTimeout = setTimeout(callback, delay);
    };

    /**
     * Draw a ring around the center on which nodes can be put.
     * @param radius
     * @returns D3 Selection of a <circle.neighbor-ring> element
     */
    self._drawNeighborRing = function (radius) {
        return self.container.append("circle")
            .attr("class", "neighbor-ring")
            .attr("r", 0)
            .attr("stroke-width", 1)
            .attr("fill", "transparent")
            .style("stroke", config.neighbor_ring.strokeColor)
            .transition()
            .duration(1000)
            .attr("r", radius);
    }

}
