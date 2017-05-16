/**
 * Filters the nodes on which the given force is applied using a provided filter callback.
 *
 * @param force
 * @param filter function (nodes) {}
 */
function filterForceNodes(force, filter) {
    var init = force.initialize;
    force.initialize = function (nodes) {
        init(nodes.filter(filter));
    }
}

/**
 * List the neighbors of a node with a provided public key
 * @param edges
 * @param neighborPK
 * @returns {Array}
 */
function listNeighborsOf(edges, neighborPK) {
    var neighbors = [];
    for (var i = 0; i < edges.length; i++) {
        var n = null;
        if (edges[i].source_pk == neighborPK)
            n = edges[i].target_pk;
        else if (edges[i].target_pk == neighborPK)
            n = edges[i].source_pk;

        if (n && neighbors.indexOf(n) == -1) {
            neighbors.push(n);
        }
    }
    return neighbors;
}

/**
 * Group the list by given key attribute.
 *
 * @param list: the list from which elements have to be grouped
 * @param key: the attribute on which the list elements have to be grouped
 * @returns a dictionary with elements grouped by attribute value
 */
function groupBy(list, key) {
  return list.reduce(function(rv, x) {
    (rv[x[key]] = rv[x[key]] || []).push(x);
    return rv;
  }, {});
}
