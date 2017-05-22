/**
 * This file creates an SVG element and draws the network using it.
 *
 * NOTE: Use a browser DOM inspection tool to see how the SVG is
 * built up and modified by this code.
 */

// TODO: start using JSDoc and setup some CI tool to check
// TODO: choose a testing framework and start writing tests

// Update the visualization
function onNewData(data) {
    state.request_pending = false;
    update(processData(data));
}

// Distance to peers
var radius = 200;

// Select the svg DOM element
var svg = d3.select("#graph"),
    width = +svg.attr("width"),
    height = +svg.attr("height");

// Append groups for links, nodes, labels.
// Order is important: drawed last is on top.
svg.append("g").attr("class", "links");
svg.append("g").attr("class", "nodes");
svg.append("g").attr("class", "labels");

var state = {
    request_pending: false,
    x: width / 2,
    y: height / 2,
    focus_pk: "self",
    focus_node: null,
    nodes: []
};

// Fetch the data
get_node_info(state.focus_pk, onNewData);

// Set up the force simulation
var simulation = d3.forceSimulation()

// Centering force (used for focus node)
    .force("center", d3.forceCenter(state.x, state.y))

    // Centering the neighbor nodes (radial layout)
    .force("neighbor_x", d3.forceX(getRadialPosition(0)).strength(.5))
    .force("neighbor_y", d3.forceY(getRadialPosition(1)).strength(.5))

    // The update function for every tick of the clock
    .on("tick", tick)

    // Make sure the simulation never dies out
    .alphaDecay(0);

// Only apply the centering force on the focus node
filterForceNodes(simulation.force("center"), function (n, i) {
    return n.public_key == state.focus_node.public_key;
});

// Only apply the neighbor force on the neighbors
filterForceNodes(simulation.force("neighbor_x"), function (n, i) {
    return n.public_key != state.focus_node.public_key;
});

filterForceNodes(simulation.force("neighbor_y"), function (n, i) {
    return n.public_key != state.focus_node.public_key;
});

/**
 * Update the visualization for the provided data set
 * @param {GraphData} graph
 */
function update(graph) {

    console.log(graph);
    // return;

    // console.log("Updating the visualization", graph);
    console.log("Focus on", graph.focus_node);

    // Restart simulation
    simulation.restart();

    // Update the state

    // Set the focus node
    state.focus_pk = graph.focus_pk;
    state.focus_node = graph.focus_node;

    // All nodes start in the center (slightly off)
    graph.nodes.forEach(function (node, i) {
        node.x = width / 2 + Math.random();
        node.y = height / 2 + Math.random();
    });

    // Position all direct neighbors on a circle
    const pi = Math.PI;
    applyAlphaLinear(state.focus_node.neighbors, 0, 2*pi);

    // Draw all nodes
    var nodes = drawNodes(svg, graph, function (d) {
            handle_node_click(d.public_key)
        });

    // Draw all links
    var links = drawLinks(svg, graph);

    // Apply the nodes to the simulation
    simulation.nodes(graph.nodes);

    // Reset the alpha to 1 (full energy)
    simulation.alpha(1);
}

/**
 * Returns the point x on line x0 to x1 at a given fraction
 * @param x0
 * @param x1
 * @param ratio
 * @returns x
 */
function xAtFraction(x0, x1, ratio){
    return x0 + (x1 - x0) * ratio;
}

/**
 * Update the positions of the links and nodes on every tick of the clock
 */
function tick() {
    var linkSource = svg.select(".links").selectAll(".link-source");
    var linkTarget = svg.select(".links").selectAll(".link-target");

    // Part of line at the source
    linkSource
        .attr("x1", function(d) { return d.source.x; })
        .attr("y1", function(d) { return d.source.y; })
        .attr("x2", function(d) { return xAtFraction(d.source.x, d.target.x, 1-d.ratio); })
        .attr("y2", function(d) { return xAtFraction(d.source.y, d.target.y, 1-d.ratio); });

    // Part of line at the target
    linkTarget
        .attr("x1", function(d) { return xAtFraction(d.target.x, d.source.x, d.ratio); })
        .attr("y1", function(d) { return xAtFraction(d.target.y, d.source.y, d.ratio); })
        .attr("x2", function(d) { return d.target.x; })
        .attr("y2", function(d) { return d.target.y; });

    selectNodes(svg)
        .attr("x", function (d) { return d.x; })
        .attr("y", function (d) { return d.y; });
}

/**
 * Make a new request when a node is clicked
 * @param public_key
 */
function handle_node_click(public_key) {
    if(state.request_pending){
        console.log("Request pending, ignore new request");
    } else {
        state.request_pending = true;
        get_node_info(public_key, onNewData)
    }
}

/**
 * Return the cartesian coordinates of a node base on its alpha
 * @param dimension (0: x, 1: y)
 */
function getRadialPosition(dimension) {
    return function (node) {
        var pos = polarToCartesian(state.x, state.y, node.alpha, radius);
        return dimension === 0 ? pos.x : pos.y;
    }
}
