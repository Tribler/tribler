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

    var selection = selectNodes(svg).data(data).enter();

    // Create an <svg.node> element.
    var groups = selection
        .append("svg")
        .attr("overflow", "visible")
        .attr("class", "node");

    // Append a <circle> element to it.
    var circles = groups
        .append("circle")
        .attr("fill", "#ff9b00")
        .attr("r", "20")
        .attr("cx", 0)
        .attr("cy", 0)
        .style("cursor","pointer")
        .on("click", on_click)
        .on("mouseenter", function(){
            d3.select(this).transition().ease(d3.easeElasticOut).delay(0).duration(300).attr("r", 25);
        }).on("mouseout", function(){
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

    var selection = selectLinks(svg).data(data).enter();

    var links = selection
        .append("svg")
        .attr("class", "link");

    links.append("line")
        .attr("class", "link-source")
        .attr("stroke-width", 2)
        .style("stroke", "#ffff00");

    links.append("line")
        .attr("class", "link-target")
        .attr("stroke-width", 2)
        .style("stroke", "#ff0000");

    return links;
}
