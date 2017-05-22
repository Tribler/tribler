/**
 * Process the JSON dictionary in the HTTP Response for the data used in the visualization.
 *
 * The JSON will be converted to the following format:
 * {
 *      "focus_node": "xyz",
 *      "min_page_rank": 5,
 *      "max_page_rank": 5,
 *      "nodes": [{
 *          "public_key": "xyz",
 *          "total_up": 100,
 *          "total_down": 500,
 *          "page_rank": 5
 *      }, ...],
 *          "links": [{
 *          "source_pk": "xyz",
 *          "source": {source node object},
 *          "target_pk": "xyz_n1",
 *          "target": {target node object},
 *          "amount_up": 100,
 *          "amount_down": 10,
 *          "ratio": 0.90909,
 *          "log_ratio": 0.66666
 *      }, ...]
 * }
 *
 * Note that the "nodes" list in the dictionary is in ascending order on total_up + total_down and "links" is in
 * ascending order on amount_up + amount_down.
 *
 * @param jsonData: the JSON dictionary passed on by the HTTP request
 * @returns a dictionary in the form specified above
 */
function processData(jsonData) {
    var data = JSON.parse(jsonData);

    // Map edges to links
    data.links = data.edges;

    var groupedLinks = groupBy(data.links, "from");
    var combinedLinks = [];
    var public_keys = [];
    
    // Calculate all combined links
    data.nodes.forEach(function(node) {
        combinedLinks = combinedLinks.concat(getCombinedLinks(groupedLinks, node.public_key));
    });

    // Sort combined links ascending on up + down
    combinedLinks = combinedLinks.sort(function(linkOne, linkTwo) {
        return linkOne.amount_up + linkOne.amount_down - linkTwo.amount_up - linkTwo.amount_down;
    });

    // Sort nodes ascending on up + down
    var nodes = data.nodes.sort(function(nodeOne, nodeTwo) {
        return nodeOne.total_up + nodeOne.total_down - nodeTwo.total_up - nodeTwo.total_down;
    });

    // Map public keys to i
    nodes.forEach(function(node, i){
        public_keys.push(node.public_key);
        node.public_key_string = node.public_key;
        node.public_key = i;
    });
    
    /**
     * Finds the first object in a list of objects that matches a given key-value pair
     * @param list
     * @param key
     * @param val
     * @returns {*}
     */
    function find(list, key, val){
        return list.find(function(item){
            return item[key] === val;
        });
    }

    // Add reference to source and target object
    combinedLinks = combinedLinks.map(function (link) {
        return Object.assign({}, link, {
            source_pk : link.source,
            target_pk : link.target,
            source: find(nodes, "public_key", link.source),
            target: find(nodes, "public_key", link.target)
        });
    });

    var sortedPageRank = data.nodes.map(function(node) {return node.page_rank}).sort(function (nodeOne, nodeTwo) {
        return nodeOne - nodeTwo;
    });

    return {'focus_node': public_keys.indexOf(data.focus_node),
            'public_keys' : public_keys,
            'min_page_rank': sortedPageRank[0],
            'max_page_rank': sortedPageRank[sortedPageRank.length - 1],
            'nodes': nodes,
            'links': combinedLinks}
}

/**
 * Combine the directed links between the given node and other nodes to one link per pair.
 *
 * The attributes of the combined links are calculated as follows:
 *  - from: node_name
 *  - to: to attribute from outgoing link from node_name
 *  - amount_up: amount from the outgoing link from node_name
 *  - amount_down: amount from the ingoing link to node_name if any
 *  - ratio: amount_up / (amount_up + amount_down)
 *  - log_ratio: log(amount_up + 1) / (log(amount_up + 1) + log(amount_down + 1))
 *
 * @param groupedLinks: the dictionary of links, grouped by "from" attribute
 * @param nodeName: the node name from which viewpoint each combine link is created
 * @returns an array of combined links with the described attributes
 */
function getCombinedLinks(groupedLinks, nodeName) {
    var combinedLinks = [];

    if(!groupedLinks[nodeName]) {
        return [];
    }

    groupedLinks[nodeName].forEach(function (link) {
        var inverseLink = groupedLinks[link.to].find(function(inv) {
            return inv.to === nodeName;
        });
        var up = link.amount,
            down = 0,
            ratio = 0,
            logRatio = 0;
        if (inverseLink !== undefined) {
            down = inverseLink["amount"]
        }
        if (up !== 0 || down !== 0) {
            ratio = up / (up + down);
            logRatio = Math.log(up + 1) / (Math.log(up + 1) + Math.log(down + 1))
        }
        combinedLinks.push({'source': nodeName, 'target': link['to'], 'amount_up': up, 'amount_down': down,
            'ratio': ratio, 'log_ratio': logRatio});
        groupedLinks[link.to].splice(groupedLinks[link['to']].indexOf(inverseLink), 1)
    });
    return combinedLinks
}
