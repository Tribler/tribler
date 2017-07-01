/**
 * Turns the graph into a tree and positions (using an angle) all GraphNodes.
 * @constructor
 */
function RadialPositioning(options) {

    var self = this,
        defaults = {};

    self.config = Object.assign({}, defaults, options || {});
    self.nodes = [];
    self.focus_pk = null;
    self.orientation = 0;

    /**
     * Add the tree nodes and angles to all nodes in this view.
     * @param {GraphData} newGraphData
     */
    self.setNodePositions = function (newGraphData) {

        // Copy positions from node to node
        self.nodes.forEach(function (node) {
            var new_node = find(newGraphData.nodes, "public_key", node.public_key);

            if (new_node) {
                new_node.x = node.x;
                new_node.y = node.y;
            }

            // Copy the previous alpha value from the new focus node
            if (node.public_key === newGraphData.focus_pk) {
                self.orientation = node.treeNode.alpha || 0;
            }
        });

        // Position all new nodes at the focus node
        newGraphData.nodes.forEach(function (node) {
            if (!('x' in node)) {
                node.x = newGraphData.focus_node.x || 0;
                node.y = newGraphData.focus_node.y || 0;
            }
        });

        // Make a tree from the graph
        var tree = self._makeTreeFromGraphNode(newGraphData.focus_node);

        // Bind each tree node to its graph node
        tree.nodes.forEach(function (treeNode) {
            treeNode.graphNode.treeNode = treeNode;
        });

        // Position all nodes on a circle
        applyRecursiveAlphaByDescendants(tree.root, 0, 2 * Math.PI, {x: 0, y: 0});

        // Find the new angle of the old focus node
        var target_angle = (self.orientation + Math.PI),
            old_focus_node = self.focus_pk ? find(newGraphData.nodes, "public_key", self.focus_pk) : null,
            current_angle = old_focus_node ? old_focus_node.treeNode.alpha || 0 : 0,
            correction = target_angle - current_angle;

        // Maintain orientation between previous and current focus node
        tree.nodes.forEach(function (node) {
            node.alpha += correction;
        });

        // Remember the current focus, tree and nodes
        self.focus_pk = newGraphData.focus_pk;
        self.tree = tree;
        self.nodes = newGraphData.nodes;

    };

    /**
     * Turns a graph structure into a tree structure
     * @param {GraphNode} graphRootNode - the focus node of the graph
     * @returns {{root: TreeNode, nodes: TreeNode[]}} - the root and all nodes of the tree
     */
    self._makeTreeFromGraphNode = function (graphRootNode) {

        var treeRoot = {
                graphNode: graphRootNode,
                children: [],
                parent: null,
                depth: 0,
                descendants: 1
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
                        descendants: 1
                    };

                    treeNodes.push(treeChild);
                    treeNode.children.push(treeChild);
                    nextQueue.push(treeChild);
                })
            }
        }

        self._calculateDescendants(treeRoot);

        return {root: treeRoot, nodes: treeNodes};
    };

    /**
     * Calculates the number of descendants of each node and sets this number as a property
     * @param treeNode
     * @returns {number} - the number of descendants (>= 1)
     * @private
     */
    self._calculateDescendants = function (treeNode) {
        return treeNode.descendants = treeNode.children.reduce(function (runningSum, childNode) {
            return runningSum + self._calculateDescendants(childNode);
        }, 1);
    }

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
    module.exports = RadialPositioning;
}
