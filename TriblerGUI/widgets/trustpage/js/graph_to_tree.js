/**
 * This file is concerned with turning a recursive GraphNode structure into a TreeNode
 * structure. This establishes a child-parent relationship and a concept of 'depth'.
 */

/**
 * Turns a graph structure into a tree structure
 * @param {GraphNode} graphRootNode - the focus node of the graph
 * @returns {{root: TreeNode, nodes: TreeNodes[]}} - the root and all nodes of the tree
 */
function makeTreeFromGraphNode(graphRootNode) {

    var treeRoot = {
            graphNode: graphRootNode,
            children: [],
            parent: null,
            depth: 0,
            descendants: 1,
        },
        treeNodes = [treeRoot],
        nextQueue = [treeRoot],
        treeNode,
        queue,
        keys = [graphRootNode.public_key];

    while ((queue = nextQueue.splice(0)).length > 0) {

        while (treeNode = queue.shift()) {

            treeNode.graphNode.neighbors.forEach(function (neighbor) {

                // Check if the neighbor is not already in the tree
                if (keys.indexOf(neighbor.public_key) >= 0) return;

                keys.push(neighbor.public_key);

                // Make a tree node and add to queue
                var treeChild = {
                    graphNode: neighbor,
                    children: [],
                    parent: treeNode,
                    depth: treeNode.depth + 1,
                    descendants: 1,
                };

                treeNodes.push(treeChild);
                treeNode.children.push(treeChild);
                nextQueue.push(treeChild);
            })
        }
    }

    _calculateDescendants(treeRoot);

    return {root: treeRoot, nodes: treeNodes};
}

/**
 * Calculates the number of descendants of each node and sets this number as a property
 * @param treeNode
 * @returns {number} - the number of descendants (>= 1)
 * @private
 */
function _calculateDescendants(treeNode) {
    return treeNode.descendants = treeNode.children.reduce(function (runningSum, childNode) {
        return runningSum + _calculateDescendants(childNode);
    }, 1);
}

/**
 * Lists the nodes per depth
 * @param {TreeNode[]} treeNodes - all nodes of the tree
 * @returns {number[]} - the number of nodes on each depth
 */
function _calculateNodesOnDepths(treeNodes) {
    var depths = [];
    treeNodes.forEach(function (node) {
        depths[node.depth] = (depths[node.depth] || 0) + 1;
    });
    return depths;
}

/**
 * Turns a graph into a tree.
 *
 * @param {GraphNode} graphRootNode - the focus node of the graph
 * @returns {Tree} - The tree structure
 */
function graphToTree(graphRootNode) {

    var tree = makeTreeFromGraphNode(graphRootNode);

    tree.nodes_per_depth = _calculateNodesOnDepths(tree.nodes);

    return tree;

}

/**
 * @typedef {Object} Tree
 * @property {TreeNode} root
 * @property {TreeNode[]} nodes
 * @property {number[]} nodes_per_depth
 */

/**
 * @typedef {Object} TreeNode
 * @property {GraphNode} graphNode
 * @property {TreeNode[]} children
 * @property {TreeNode|null} parent
 * @property {number} depth
 * @property {number} descendants
 */

/**
 * Export functions so Mocha can test it
 */
if (typeof module !== 'undefined') {
    module.exports = {
        makeTreeFromGraphNode: makeTreeFromGraphNode,
        _calculateDescendants: _calculateDescendants,
        _calculateNodesOnDepths: _calculateNodesOnDepths,
        graphToTree: graphToTree
    };
}
