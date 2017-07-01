/**
 * The help page explaining the visualization.
 * @param {Object} options - override of the defaults
 * @constructor
 */
function HelpPage(options) {

    var self = this,
        defaults = {};

    self.config = Object.assign({}, defaults, options || {});
    self.visible = false;

    /**
     * Fill the different <svg>'s of the help page content
     */
    self.initialize = function () {
        self._drawCircleTextSvg();
        self._drawCircleColorSvg();
        self._drawCircleSizeSvg();
        self._drawLineSizeSvg();
        self._drawLineDividerSvg();

        return self;
    };

    /**
     * Show the help page
     */
    self.show = function () {
        document.getElementsByTagName("body")[0].classList.add("show-help-page");
        self.visible = true;
    };

    /**
     * Hide the help page
     */
    self.hide = function () {
        document.getElementsByTagName("body")[0].classList.remove("show-help-page");
        self.visible = false;
    };

    /**
     * Hide the help page when visible, show the help page when hidden
     */
    self.toggle = function () {
        self.visible ? self.hide() : self.show();
    };

    /**
     * Hide the help page and help page button if the window becomes too small
     */
    window.onresize = function () {
        if (window.innerWidth < self.config.help.page.minWindowWidth) self.hide();
    };

    /**
     * Get node color based on node balance score [0, 1]
     * @private
     */
    self._nodeColor = d3.scaleLinear()
        .domain(self.config.node.color.domain)
        .range(self.config.node.color.range);

    /**
     * Fill the svg which explains the meaning of the text inside the circle.
     * @private
     */
    self._drawCircleTextSvg = function () {

        var svg = d3.select("#help-circle-text"),
            containerSvg = self._drawSvgCenterContainer(svg)
                .attr("x", parseInt(svg.style("width")) / 2);

        containerSvg.append("circle")
            .attr("r", self.config.node.circle.maxRadius)
            .attr("fill", self._nodeColor(0.5));

        containerSvg
            .append("text")
            .attr("dominant-baseline", "central")
            .attr("text-anchor", "middle")
            .attr("fill", self.config.node.publicKeyLabel.color)
            .style("font-family", self.config.node.publicKeyLabel.fontFamily)
            .style("font-size", self.config.node.publicKeyLabel.fontSize)
            .style("font-weight", self.config.node.publicKeyLabel.fontWeight)
            .text(self.config.help.nodes.examplePublicKey);
    };

    /**
     * Fill the svg which explains the meaning of the circle colors.
     * @private
     */
    self._drawCircleColorSvg = function () {
        var svg = d3.select("#help-circle-color"),
            containerSvg = self._drawSvgCenterContainer(svg),
            nodeRadius = self.config.help.nodes.circleColor.nodeRadius,
            names = self.config.help.nodes.circleColor.labels,
            numberOfNodes = self.config.help.nodes.numberOfNodes,
            labelOffset = self.config.help.label.offsetY,
            width = parseInt(svg.style("width")),
            spacing = width / (numberOfNodes + 1),
            labelY = (1 / 2) * nodeRadius + labelOffset + self.config.help.label.fontSize,
            nodesData = [];

        // Draw the nodes and corresponding labels
        for (var i = 0; i < numberOfNodes; i++) {
            var x = (i + 1) * spacing;
            self._drawNode(containerSvg, x, 0, config.help.nodes.circleColor.nodeRadius, self._nodeColor(i / (numberOfNodes - 1)));
            self._drawLabel(containerSvg, self.config.help.nodes.circleColor.labels[i], x, labelY);
        }
    };

    /**
     * Fill the svg which explains the meaning of the circle sizes.
     * @private
     */
    self._drawCircleSizeSvg = function () {
        var svg = d3.select("#help-circle-size"),
            containerSvg = self._drawSvgCenterContainer(svg),
            numberOfNodes = self.config.help.nodes.numberOfNodes,
            minRadius = self.config.node.circle.minRadius,
            maxRadius = self.config.node.circle.maxRadius,
            radiusScale = d3.scaleLinear()
                .domain([0, numberOfNodes - 1])
                .range([minRadius, maxRadius]),
            width = parseInt(svg.style("width")),
            spacing = width / (numberOfNodes + 1),
            labelY = (1 / 2) * self.config.help.label.fontSize + maxRadius + self.config.help.label.offsetY;

        // Draw the nodes and corresponding labels
        for (var i = 0; i < numberOfNodes; i++) {
            var x = (i + 1) * spacing;
            self._drawNode(containerSvg, x, 0, radiusScale(i), self._nodeColor(0.5));
            self._drawLabel(containerSvg, self.config.help.nodes.circleSize.labels[i], x, labelY);
        }
    };

    /**
     * Fill the svg which explains the meaning of the line sizes.
     * @private
     */
    self._drawLineSizeSvg = function () {
        var svg = d3.select("#help-connection-transmission"),
            containerSvg = self._drawSvgCenterContainer(svg),
            numberOfEdges = self.config.help.edges.numberOfEdges,
            minEdgeWidth = self.config.link.strokeWidthMin,
            maxEdgeWidth = self.config.link.strokeWidthMax,

            edgeWidthScale = d3.scaleLinear()
                .domain([0, numberOfEdges - 1])
                .range([minEdgeWidth, maxEdgeWidth]),

            width = parseInt(svg.style("width")),
            spacing = width / (numberOfEdges + 1),
            labelY = (1 / 2) * (self.config.help.label.fontSize + maxEdgeWidth) + self.config.help.label.offsetY;

        var conf = self.config.help.edges;

        // Fill array with the data belonging to each edge
        for (var i = 0; i < numberOfEdges; i++) {
            var x = (i + 1) * spacing;
            self._drawLink(containerSvg, x, 0, conf.edgeLength, edgeWidthScale(i), 0.5);
            self._drawLabel(containerSvg, conf.width.labels[i], x, labelY);
        }
    };

    /**
     * Fill the svg which explains the meaning of the line divider.
     * @private
     */
    self._drawLineDividerSvg = function () {
        var svg = d3.select("#help-connection-balance"),
            containerSvg = self._drawSvgCenterContainer(svg),
            numberOfEdges = self.config.help.edges.numberOfEdges,
            edgeWidth = (self.config.link.strokeWidthMin + self.config.link.strokeWidthMax) / 2,
            width = parseInt(svg.style("width")),
            spacing = width / (numberOfEdges + 1),
            labelY = (1 / 2) * self.config.help.label.fontSize + edgeWidth + self.config.help.label.offsetY;

        var conf = self.config.help.edges;

        // Fill array with the data belonging to each edge
        for (var i = 0; i < numberOfEdges; i++) {
            var x = (i + 1) * spacing;
            self._drawLink(containerSvg, x, 0, conf.edgeLength, edgeWidth, (i + 1) / (numberOfEdges + 1));
            self._drawLabel(containerSvg, conf.separator.labels[i], x, labelY);
        }
    };

    /**
     * Appends a container svg to the input svg
     * @param svg the svg to put the container around
     */
    self._drawSvgCenterContainer = function (svg) {
        return svg.append("svg")
            .attr("x", 0)
            .attr("y", parseInt(svg.style("height")) / 2)
            .attr("overflow", "visible");
    };

    /**
     * Appends a line to the input svg using the following properties:
     * @param parent the svg to append the line to
     * @param x the start x coordinate
     * @param y the start y coordinate
     * @param length
     * @param width
     * @param ratio the ratio at which to put the balance divider separator
     * @param separatorThickness
     * @private
     */
    self._drawLink = function (parent, x, y, length, width, ratio) {
        parent
            .append("line")
            .attr("x1", x - length / 2)
            .attr("x2", x - length / 2 + length * ratio - self.config.help.edges.dividingWidth / 2)
            .attr("stroke", self.config.link.color)
            .attr("stroke-width", width);

        parent
            .append("line")
            .attr("x1", x - length / 2 + length * ratio + self.config.help.edges.dividingWidth / 2)
            .attr("x2", x + length / 2)
            .attr("stroke", self.config.link.color)
            .attr("stroke-width", width);
    };

    /**
     * Appends a circle to the input svg using the following properties:
     * @param parent the svg to append the line to
     * @param x the start x coordinate
     * @param y the start y coordinate
     * @param radius the radius of the circle
     * @param color the color of the circle
     * @private
     */
    self._drawNode = function (parent, x, y, radius, color) {
        parent
            .append("circle")
            .attr("r", radius)
            .attr("fill", color)
            .attr("cx", x)
            .attr("cy", y);
    };

    /**
     * Appends a label to the input svg based on the following properties:
     * @param parent the svg to append the label to
     * @param text the text to put in the label
     * @param x the start x coordinate
     * @param y the start y coordinate
     * @private
     */
    self._drawLabel = function (parent, text, x, y) {
        parent
            .append("text")
            .attr("dominant-baseline", "central")
            .attr("text-anchor", "middle")
            .style("font-family", config.help.label.fontFamily)
            .style("font-size", config.help.label.fontSize)
            .style("font-weight", config.help.label.fontWeight)
            .attr("fill", config.help.label.color)
            .attr("x", x)
            .attr("y", y)
            .text(text);
    }
}
