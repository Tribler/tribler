/**
 * Process the GraphResponseData object into a GraphData object by collecting the result
 * of a series of pure functions (with some exceptions).
 *
 * The resulting data structure is a GraphData object which is defined at the bottom
 * of this file.
 */

/**
 * Convert the GraphResponseData into GraphData by combining the result of pure
 * functions.
 *
 * @param {GraphResponseData} response - The response data
 * @returns {GraphData} - The resulting graph data object
 */
function processData(response) {

    /**
     * The converter functions in their order of execution.
     * @type {Converter[]}
     */
    var converters = [
        mapNodes,
        markUserNode,
        mapEdges,
        combineLinks,
        addMinMaxTransmission,
        addTrafficFunction,
        focusNodePublicKey,
        sortNodes,
        makeLocalKeyMap, // after sorting
        addNeighborsToNodes
    ];

    return convertResponse(response, converters);
}

/**
 * Convert the response object into a different object by combining the
 * result of an array of converters.
 *
 * @param {GraphResponseData} response - The response
 * @param {Converter[]} converters
 * @returns {Object} - The resulting object
 */
function convertResponse(response, converters) {

    return converters.reduce(function (interim, converter) {
        var additions = converter(response, interim);

        return Object.assign(interim, additions);
    }, {});
}

/**
 * Map the GraphResponseNode to GraphNode objects
 *
 * @param {GraphResponseData} response - The response
 * @returns {{nodes: GraphNode[]}}
 */
function mapNodes(response) {
    var nodes = response.nodes.map(function (node) {
        return {
            public_key: node.public_key,
            total_up: node.total_up,
            total_down: node.total_down,
            score: node.score,
            total_neighbors: node.total_neighbors
        }
    });

    return {
        nodes: nodes
    }
}

/**
 * Add a property to each node telling whether it represents the user
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.nodes)
 * @returns {{}}
 */
function markUserNode(response, interim) {
    interim.nodes.forEach(function (node) {
        node.is_user = node.public_key === response.user_node;
    });

    return {};
}

/**
 * Map the directed GraphResponseEdge to GraphEdge objects
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.nodes)
 * @returns {{edges: GraphEdge[]}}
 */
function mapEdges(response, interim) {

    var edges = response.edges.map(function (edge) {
        return {
            source: find(interim.nodes, "public_key", edge.from),
            source_pk: edge.from,
            target: find(interim.nodes, "public_key", edge.to),
            target_pk: edge.to,
            amount: edge.amount
        }
    });

    return {
        edges: edges
    }
}

/**
 * Combine the directed edges between nodes to one link per pair.
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.nodes, interim.edges)
 * @returns {{links: GraphLink[]}}
 */
function combineLinks(response, interim) {

    var groupedEdges = groupBy(interim.edges, "source_pk");

    // Make the combined links for all nodes
    var combinedLinks = flatMap(interim.nodes, function (sourceNode) {
        return (groupedEdges[sourceNode.public_key] || []).map(function (edge) {
            var edgesFromTarget = groupedEdges[edge.target_pk];
            var inverseEdge = edgesFromTarget !== undefined ? find(edgesFromTarget, "target_pk", sourceNode.public_key) : null;
            var up = edge.amount,
                down = inverseEdge ? inverseEdge.amount : 0,
                empty = up + down === 0;

            // Remove the inverse edge
            if (inverseEdge) {
                groupedEdges[edge.target_pk].splice(groupedEdges[edge.target_pk].indexOf(inverseEdge), 1);
            }

            return {
                source_pk: edge.source_pk,
                target_pk: edge.target_pk,
                source: edge.source,
                target: edge.target,
                amount_up: up,
                amount_down: down,
                ratio: !empty ? up / (up + down) : 1,
                log_ratio: !empty ? Math.log(up + 1) / (Math.log(up + 1) + Math.log(down + 1)) : 1
            };
        });
    });

    // Sort combined links ascending on up + down
    combinedLinks.sort(function (linkOne, linkTwo) {
        return linkOne.amount_up + linkOne.amount_down - linkTwo.amount_up - linkTwo.amount_down;
    });

    // Add reference to source and target object
    return {
        links: combinedLinks
    };
}

/**
 * Calculate the smallest and largest transmission from the focus node to its neighbors.
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.links)
 * @returns {{min_transmission: number, max_transmission: number}}
 */
function addMinMaxTransmission(response, interim) {

    var min = -1,
        max = -1;

    interim.links.forEach(function (link) {
            var total = link.amount_up + link.amount_down;
            if (min === -1 || total < min) min = total;
            if (max === -1 || total > max) max = total;
    });

    return {
        min_transmission: min >= 0 ? min : 0,
        max_transmission: max >= 0 ? max : 0
    };
}

/**
 * Calculate the parameters for the linear line describing the node size based on the amount of total traffic.
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result
 * @returns {{min_total_traffic: number, max_total_traffic: number}}
 */
function addTrafficFunction(response, interim) {
    var min = Number.MAX_VALUE,
        max = Number.MIN_VALUE;

    interim.nodes.forEach(function (node) {
       var total_traffic = node.total_up + node.total_down;
       min = Math.min(total_traffic, min);
       max = Math.max(total_traffic, max);
    });

    if (min === Number.MAX_VALUE && max === Number.MIN_VALUE)
        max = min = 0;

    return {
        min_total_traffic: min,
        max_total_traffic: max
    };
}

/**
 * Make a map from local_keys (integers 0 to n-1) to public keys (where n is the number of nodes).
 * (Manipulates the interim)
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.nodes)
 * @returns {{local_keys: String[]}}
 */
function makeLocalKeyMap(response, interim) {

    var localKeys = interim.nodes.map(function (node, i) {
        node.local_key = i;
        return node.public_key;
    });

    return {
        local_keys: localKeys
    };
}

/**
 * Get the focus node object and its public key.
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.nodes)
 * @returns {{focus_node: GraphNode, focus_pk: String}}
 */
function focusNodePublicKey(response, interim) {

    return {
        focus_node: interim.nodes ? find(interim.nodes, "public_key", response.focus_node) : null,
        focus_pk: response.focus_node
    };
}

/**
 * Add the neighbors to each node. (Manipulates the interim)
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.links, interim.nodes)
 * @returns {{}} - An empty object, since this manipulates the interim.
 */
function addNeighborsToNodes(response, interim) {

    interim.nodes.forEach(function (node) {
        node.neighbors = [];
    });

    interim.links.forEach(function (link) {
        link.source.neighbors.push(link.target);
        link.target.neighbors.push(link.source);
    });

    return {};
}

/**
 * Sort the nodes array in-place in the result object ascending on up+down.
 * (Manipulates the interim)
 *
 * @param {GraphResponseData} response - The response
 * @param {Object} interim - The interim result (expects interim.nodes)
 * @returns {{}} - An empty object, since this manipulates the interim.
 */
function sortNodes(response, interim) {

    interim.nodes.sort(function (nodeOne, nodeTwo) {
        return nodeOne.total_up + nodeOne.total_down - nodeTwo.total_up - nodeTwo.total_down;
    });

    return {};
}

/**
 * Returns the first object in a list of objects that matches a given key-value pair.
 *
 * @param {Object[]} list - The list of objects
 * @param {String} key    - The key to look at
 * @param {*} val         - The value to match for
 * @returns {Object|null} - The matching object or null if no match
 */
function find(list, key, val) {
    return list.find(function (item) {
        return item[key] === val;
    });
}

/**
 * Returns a concatenation of arrays returned from mapping an array over a callback.
 *
 * @param {Array} arr         - The array to reduce
 * @param {Function} callback - The callback to apply, must return an array
 * @returns {Array} arr       - The concatenated result of all calls to callback
 */
function flatMap(arr, callback) {
    return arr.reduce(function (acc, item) {
        return acc.concat(callback(item));
    }, []);
}

/**
 * Group the list by given key attribute.
 *
 * @param {Array} list - The list from which elements have to be grouped
 * @param {String} key - The attribute on which the list elements have to be grouped
 * @returns {Object}   - A dictionary with elements grouped by attribute value
 */
function groupBy(list, key) {
    return list.reduce(function (rv, x) {
        (rv[x[key]] = rv[x[key]] || []).push(x);
        return rv;
    }, {});
}

/**
 * @typedef {Object} GraphData
 * @property {String} focus_pk          - the public key of the focus node
 * @property {GraphNode} focus_node     - the focus node object
 * @property {number} min_transmission  - the smallest transmission (up+down) from the focus node
 * @property {number} max_transmission  - the largest transmission (up+down) from the focus node
 * @property {number} min_total_traffic - the minimal amount of traffic a single node in the set has
 * @property {number} max_total_traffic - the slope of the traffic function
 * @property {String[]} local_keys      - a map from GraphNode.local key (array index) to public_key
 * @property {GraphNode[]} nodes        - the array of nodes (sorted ascending on .total_up + .total_down)
 * @property {GraphEdge[]} edges        - the directed edges
 * @property {GraphLink[]} links        - the combined links (sorted ascending on .amount_up + .amount_down)
 */

/**
 * @typedef {Object} GraphNode
 * @property {String} public_key      - the public key of this node
 * @property {number} local_key       - the local key of this node (corresponds with GraphData.local_keys)
 * @property {number} total_up        - the total upload by this node
 * @property {number} total_down      - the total download by this node
 * @property {number} score           - the score between 0 and 1 for the rating in the network of the node
 * @property {number} total_neighbors - The number of neighbors the node has
 * @property {boolean} is_user        - true if this node represents the user
 * @property {GraphNode[]} neighbors  - the list of neighbors of this node
 */

/**
 * @typedef {Object} GraphEdge
 * @property {GraphNode} source - The source node
 * @property {String} source_pk - The public key of the source node
 * @property {GraphNode} target - The target node
 * @property {String} target_pk - The public key of the target node
 * @property {number} amount    - The amount of MB sent from source to target
 */

/**
 * @typedef {Object} GraphLink
 * @property {GraphNode} source - The source node
 * @property {String} source_pk - The public key of the source node
 * @property {GraphNode} target - The target node
 * @property {String} target_pk - The public key of the target node
 * @property {number} amount_up   - The amount of bytes sent from source to target
 * @property {number} amount_down - The amount of bytes sent from target to source
 * @property {number} ratio       - amount_up / (amount_up + amount_down)
 * @property {number} log_ratio   - log(amount_up+1) / (log(amount_up+1) + log(amount_down+1))
 */

/**
 * @typedef {Function} Converter
 * @param {GraphResponseData} response - The response data, must be considered immutable
 * @param {Object} interim - The interim graph data object (as far as constructed)
 * @returns {Object} - The additions which should be added to the interim
 */

/**
 * Export functions so Mocha can test it
 */
if (typeof module !== 'undefined') {
    module.exports = {
        processData: processData,
        convertResponse: convertResponse,
        mapNodes: mapNodes,
        mapEdges: mapEdges,
        combineLinks: combineLinks,
        addMinMaxTransmission: addMinMaxTransmission,
        addTrafficFunction: addTrafficFunction,
        makeLocalKeyMap: makeLocalKeyMap,
        focusNodePublicKey: focusNodePublicKey,
        sortNodes: sortNodes,
        addNeighborsToNodes: addNeighborsToNodes
    };
}
