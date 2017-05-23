/**
 * These methods are concerned with drawing and styling SVG elements
 */

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
    selectNodes(svg).remove();

    var selection = selectNodes(svg).data(data.nodes).enter();

    // Create an <svg.node> element.
    var groups = selection
        .append("svg")
        .attr("overflow", "visible")
        .attr("class", "node");

    // Append a <circle> element to it.
    var circles = groups
        .append("circle")
        .attr("fill", function (d) {
            return getNodeColor(d, data)
        })
        .attr("r", "20")
        .attr("cx", 0)
        .attr("cy", 0)
        .style("cursor", "pointer")
        .on("click", on_click)
        .on("mouseenter", function () {
            d3.select(this).transition().ease(d3.easeElasticOut).delay(0).duration(300).attr("r", 25);
        }).on("mouseout", function () {
            d3.select(this).transition().ease(d3.easeElasticOut).delay(0).duration(300).attr("r", 20);
        });

    // Append a <text> element to it
    groups
        .append("text")
        .attr("x", 24)
        .attr("y", 24)
        .style("font-family", "sans-serif")
        .style("font-size", "12")
        .style("fill", "#ffff00")
        .text(function (d) {
            return d.public_key_string.substr(-5);
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
        .domain([0, 0.5, 1])
        .range(["red", "yellow", "green"]);

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

    var selection = selectLinks(svg).data(data.links).enter();

    var links = selection
        .append("svg")
        .attr("class", "link");

    links.append("line")
        .attr("class", "link-source")
        .attr("stroke-width", function (d) {
            return getStrokeWidth(d, data)
        })
        .style("stroke", "#ffff00");

    links.append("line")
        .attr("class", "link-target")
        .attr("stroke-width", function (d) {
            return getStrokeWidth(d, data)
        })
        .style("stroke", "#ff0000");

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
    // Map relative to the minimum and maximum total transition links of the graph
    var difference = data.max_transmission - data.min_transmission;
    if(difference === 0) {
        return 6;
    }
    var linkTotal = link.amount_up + link.amount_down;
    var normalizedTotal = (linkTotal - data.min_transmission) / difference;

    // Width in [2, 10] px
    return (normalizedTotal * 8) + 2;
}

module.exports = {getStrokeWidth: getStrokeWidth};
