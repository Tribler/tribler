/**
 * This file is responsible for making the HTTP requests to the Tribler API,
 * to retrieve information about the neighbors of the focus node.
 */

/**
 * Make a Cross-Origin-Resource-Sharing request object.
 * @param method The http method
 * @param url The url to which the request is made
 * @returns {XMLHttpRequest} The request object
 */
function make_cors_request(method, url) {
    var request = new XMLHttpRequest();
    request.open(method, url, true);

    if(!request) {
        // No CORS support by this browser
        request = null;
    }

    return request;
}

/**
 * Make a request to the Tribler API requesting a given
 * focus node and its first level neighbors.
 *
 * The expected JSON format:
 *
 * {
 *       "focus_node": "xyz",
 *       "neighbor_level": 1,
 *       "nodes": [{
 *           "public_key": "xyz",
 *           "total_up": 12736457,
 *           "total_down": 1827364,
 *           "score": 0.0011,
 *           "total_neighbors": 1
 *       }, ...],
 *       "edges": [{
 *           "from": "xyz",
 *           "to": "xyz_n1",
 *           "amount": 12384
 *       }, ...]
 * }
 *
 * This will be converted into the following object:
 *
 * @param public_key The public key of the focus node
 * @param neighbor_level The neighbor level which has to be displayed
 * @param max_neighbors The maximum amount of higher level neighbors one node can have
 * @param path_to_old_focus All nodes in the tree connecting the new focus to the old focus
 * @param callback The callback which is called with the GraphResponseData
 */
function get_node_info(public_key, neighbor_level, max_neighbors, path_to_old_focus, callback) {
    var url = "http://localhost:8085/trustchain/network?focus_node=" + public_key + "&neighbor_level=" + neighbor_level
                    + "&max_neighbors=" + max_neighbors + "&mandatory_nodes=" + path_to_old_focus;
    var response = make_cors_request('GET', url);
    if (!response) {
        console.log("No CORS support by this browser");
    }

    response.onload = function() {
        /**
         * @type {GraphResponseData}
         */
        var graphResponseData = JSON.parse(response.responseText);
        callback(graphResponseData);
    };

    response.onerror = function() {
        console.log("Request error");
    };

    response.send();
}

/**
 * @typedef {Object} GraphResponseData
 * @property {String} user_node          - The public key of the user
 * @property {String} focus_node         - The public key of the focus node
 * @property {number} neighbor_level     - The neighbor level
 * @property {GraphResponseNode[]} nodes - The nodes
 * @property {GraphResponseEdge[]} edges - The edges
 */

/**
 * @typedef {Object} GraphResponseEdge
 * @property {String} from   - The public key of the source node
 * @property {String} to     - The public key of the target node
 * @property {number} amount - The amount of MB sent from source to target
 */

/**
 * @typedef {Object} GraphResponseNode
 * @property {String} public_key - The public key of the node
 * @property {number} total_up   - The total amount of MB uploaded by the node
 * @property {number} total_down - The total amount of MB downloaded by the node
 * @property {number} score      - The score between 0 and 1 for the rating in the network of the node
 * @property {number} total_neighbors  - The number of neighbors the node has
 */
