/**
 * These methods are concerned with drawing and styling SVG elements
 */

if (typeof require !== "undefined") {
    var config = require("./style_config.js");
}

/**
 * Select all <svg.node> elements in .nodes
 * @returns D3 Selection of <svg.node> elements
 */
function selectNodes(svg) {
    return svg
        .select(".nodes")
        .selectAll(".node");
}

/**
 * Draw the nodes and their labels
 * @param svg the svg from the body
 * @param data the JSON data of the graph
 * @param on_click the function that responds to the click
 * @returns D3 Selection of <svg.node> elements
 */
function drawNodes(svg, data, on_click) {

    // Always remove existing nodes before adding new ones
    var all = selectNodes(svg).data(data.nodes, function (d) {
            return d.public_key;
        }),
        exit = all.exit(),
        enter = all.enter();

    // Remove exit nodes
    exit.remove();

    // Create an <svg.node> element.
    var groups = enter
        .append("svg")
        .attr("overflow", "visible")
        .attr("class", "node");

    // Append a <circle> element to it.
    var circles = groups
        .append("circle")
        .attr("fill", function (d) {
            return getNodeColor(d, data)
        })
        .attr("r", "0")
        .attr("cx", config.node.circle.cx)
        .attr("cy", config.node.circle.cy)
        .style("cursor", config.node.circle.cursor)
        .on("click", on_click)
        .on("mouseenter", function () {
            d3.select(this).transition().ease(d3.easeElasticOut).delay(0).duration(300).attr("r", 25);
        }).on("mouseout", function () {
            d3.select(this).transition().ease(d3.easeElasticOut).delay(0).duration(300).attr("r", 20);
        });

    // Transition the radius of the circles
    circles.transition()
        .duration(1000)
        .attr("r", config.node.circle.radius)

    // Append a <text> element to it
    groups
        .append("text")
        .attr("x", config.node.publicKeyLabel.x)
        .attr("y", config.node.publicKeyLabel.y)
        .style("font-family", config.node.publicKeyLabel.fontFamily)
        .style("font-size", config.node.publicKeyLabel.fontSize)
        .style("fill", config.node.publicKeyLabel.color)
        .text(function (d) {
            return d.public_key.substr(-5);
        });

    // Return the group of <svg.node>
    return groups;
}

/**
 * Get the color of a node based on the page rank score of the node
 * @param node the node to get the color for
 * @param data the JSON data of the graph
 * @returns the color of the node
 */
function getNodeColor(node, data) {
    // Use D3 color scale to map floats to colors
    var nodeColor = d3.scaleLinear()
        .domain(config.node.color.domain)
        .range(config.node.color.range);

    // Map relative to the minimum and maximum page rank of the graph
    var rank_difference = data.max_page_rank - data.min_page_rank;
    if (rank_difference === 0) {
        return nodeColor(1);
    }

    return nodeColor((node.page_rank - data.min_page_rank) / rank_difference);
}

/**
 * Select all <svg.link> elements in .links
 * @returns D3 Selection of <svg.link> elements
 */
function selectLinks(svg) {
    return svg
        .select(".links")
        .selectAll(".link")
}

/**
 * Draw the links upon given data
 * @param svg the svg from the body
 * @param data the JSON data of the graph
 * @returns D3 Selection of <svg.link> elements
 */
function drawLinks(svg, data) {

    selectLinks(svg).remove();

    // All lines, identified by source and target public_key
    var all = selectLinks(svg).data(data.links, function (l) {
        return l.source.public_key + "" + l.target.public_key
    });

    // Remove exit lines
    all.exit().remove();

    var links = all.enter()
        .append("svg")
        .attr("class", "link")
        .style("opacity", "0");

    links.append("line")
        .attr("class", "link-source")
        .attr("stroke-width", function (d) {
            return getStrokeWidth(d, data)
        })
        .style("stroke", config.link.colorLinkSource);

    links.append("line")
        .attr("class", "link-target")
        .attr("stroke-width", function (d) {
            return getStrokeWidth(d, data)
        })
        .style("stroke", config.link.colorLinkTarget);

    links.append("line")
        .attr("class", "link-velocity")
        .attr("stroke-width", 2)
        .style("stroke", "white");

    links.transition()
        .duration(1000)
        .style('opacity', '1');

    return links;
}

/**
 * Get the stroke width based on the total amount of transmitted data over the link,
 * relative to the other links in the graph
 * @param link the link to get the width for
 * @param data the JSON data of the graph
 * @returns the width of the link
 */
function getStrokeWidth(link, data) {

    // The difference between the minimum and maximum data links
    var transmissionDifference = data.max_transmission - data.min_transmission;
    
    // The difference between the minimum and maximum stroke width
    var widthDifference = config.link.strokeWidthMax - config.link.strokeWidthMin;

    // If exactly the same amount is transmitted between all peers, return the middle of the width interval
    if (transmissionDifference === 0)
        return (config.link.strokeWidthMax + config.link.strokeWidthMin) / 2;

    // The total transmission of the current link
    var linkTotal = link.amount_up + link.amount_down;

    // The fraction of the current link in the network
    var fraction = (linkTotal - data.min_transmission) / transmissionDifference;

    // The width based on the fraction and the interval
    return fraction * widthDifference + config.link.strokeWidthMin;
}

/**
 * Draw a ring around the center on which nodes can be put.
 * @param svg
 * @param center_x
 * @param center_y
 * @param radius
 * @returns D3 Selection of a <circle.neighbor-ring> element
 */
function drawNeighborRing(svg, center_x, center_y, radius) {

    return svg.append("circle")
        .attr("class", "neighbor-ring")
        .attr("r", 0)
        .attr("cx", center_x)
        .attr("cy", center_y)
        .attr("stroke-width", 1)
        .attr("fill", "transparent")
        .style("stroke", "#333333")
        .transition()
        .duration(1000)
        .attr("r", radius)

}

if (typeof module !== "undefined") {
    module.exports = {getStrokeWidth: getStrokeWidth};
}
