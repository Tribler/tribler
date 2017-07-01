/**
 * The data inspector for the Radial Network
 * @param d3element - the container HTML element wrapped in d3
 * @param {Object} options - configuration overrides for the links
 * @constructor
 */
function RadialInspector(d3element, options) {

    var self = this,
        defaults = {};

    self.graphData = null;
    self.config = Object.assign({}, defaults, options || {});

    /**
     * Select all <svg.link> objects in the SVG
     */
    self.select = function () {
        return d3element;
    };

    /**
     * Push the new data to the inspector and redraw
     * @param {GraphData} newGraphData
     */
    self.onNewData = function (newGraphData) {
        self.graphData = newGraphData;
        self.displayNetworkInfo();
    };

    /**
     * Display the network information
     */
    self.displayNetworkInfo = function () {
        if (!self.graphData) return;

        var data = self.graphData,
            bindings = {
                focusNodeName: self._getNodeIdentifier(data.focus_node),
                nodeCount: data.nodes.length,
                linkCount: data.links.length,
                color: self.config.node.color.range[0]
            },
            exploreEncouragement = bindings.nodeCount === 1 ? "Exchange content to see more users."
                : "Click on users to explore the rest of the network.";
            bindings.user = "user" + (bindings.nodeCount === 1 ? "" : "s");

        self._setContents(
            "Tribler Network",
            "Partial view around {focusNodeName}",
            [
                "Showing <strong>{nodeCount} {user}</strong>",
                exploreEncouragement,
                "Users with" +
                    "<span class='badge inline' style='background:{color}'>Balance: <strong>-10GB</strong></span>" +
                    "or worse will be blocked from downloading until they start uploading again."
            ], bindings);
    };

    /**
     * Display the node information
     * @param {GraphNode} node
     * @param {RadialNodes} radial_nodes - the radial nodes module, used for calculating the color
     */
    self.displayNodeInfo = function (node, radial_nodes) {
        var balance = node.total_up - node.total_down,
            bindings = {
                formatted_upload: formatBytes(node.total_up),
                formatted_download: formatBytes(node.total_down),
                formatted_balance: (balance > 0 ? "+" : "") + formatBytes(balance),
                peer_count: node.total_neighbors,
                shown_peer_count: node.neighbors.length,
                x: self._getNodeIdentifier(node),
                color: radial_nodes._calculateFill(node)
            };
            bindings.user = "user" + (bindings.peer_count === 1 ? "" : "s");

        self._setContents(
            self._getNodeIdentifier(node),
            "Anonymous",
            [
                "Shared <strong>{formatted_upload}</strong>",
                "Consumed <strong>{formatted_download}</strong>",
                "Showing {shown_peer_count} of {peer_count} connected {user}.",
                "<span class='badge' style='background:{color}'>Balance: <strong>{formatted_balance}</strong></span>"
            ], bindings);
    };

    /**
     * Display the link information
     * @param {GraphLink} link
     */
    self.displayLinkInfo = function (link) {
        var bindings = {
            source: self._getNodeIdentifier(link.source),
            target: self._getNodeIdentifier(link.target),
            formatted_up: formatBytes(link.amount_up),
            formatted_down: formatBytes(link.amount_down)
        };

        self._setContents(
            "Content exchanged",
            "Between {source} and {target}",
            [
                "{source} shared <strong>{formatted_up}</strong> with {target}",
                "{target} shared <strong>{formatted_down}</strong> with {source}",
                "File contents are always hidden"
            ], bindings);
    };

    /**
     * Format the string that identifies a node
     * @param node
     * @private
     */
    self._getNodeIdentifier = function (node) {
        return node.is_user ? "you" : "user #" + node.public_key.substr(-3);
    };

    /**
     * Fills the inspector with HTML contents
     * @param {String} title - html that will be added inside the title element
     * @param {String} subtitle - html that will be added inside the subtitle element
     * @param {String[]} lines - html that will be added inside <p> elements
     * @param {Object} bindings - the variable-value bindings which will be replaced in the title and lines
     * @private
     */
    self._setContents = function (title, subtitle, lines, bindings) {
        self.select().select(".title .title").html(ucfirst(substituteString(title, bindings)));
        self.select().select(".title .subtitle").html(ucfirst(substituteString(subtitle, bindings)));

        self.select().selectAll("p.info").remove();

        // Redraw text for all lines
        self.select().selectAll("p.info")
            .data(lines)
            .enter()
            .append("p")
            .attr("class", "info")
            .html(function (line) {
                return ucfirst(substituteString(line, bindings));
            });
    };
}

/**
 * Export functions so Mocha can test it
 */
if (typeof module !== "undefined") {
    module.exports = {
        RadialInspector: RadialInspector
    };
}
