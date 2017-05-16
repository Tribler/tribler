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
 * @param public_key The public key of the focus node
 * @param callback The callback which is called with the response
 */
function get_node_info(public_key, callback) {
    var url = "http://localhost:8085/display?focus_node=" + public_key + "&neighbor_level=1";

    var response = make_cors_request('GET', url);
    if (!response) {
        console.log("No CORS support by this browser");
    }

    response.onload = function() {
        callback(response.responseText);
    };

    response.onerror = function() {
        console.log("Request error");
    };

    response.send();
}
