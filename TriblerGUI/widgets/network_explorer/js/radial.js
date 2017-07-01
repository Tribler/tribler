/**
 * This file contains methods for controlling the radial layout of the graph.
 *
 * Each node has a distance from the focus node (depending on their depth) and
 * an alpha (the angle between the horizontal and the vector to that node). The
 * distance is established by a 'link' force, the alpha is established as follows:
 *
 * 1. graphToTree() transforms the graph into a tree.
 * 2. applyRecursiveAlphaByDescendants() assigns an alpha (angle) to each node,
 *      which represents the angle between the horizontal and the node vector.
 * 3. radialForceVector() calculates the actual alpha value from the node and
 *      determines a force vector tangential to the node vector.
 * 4. radialForce() takes the radialForceVector and changes the velocity of the
 *      node so it moves in the direction of that vector.
 */

/**
 * Recursively apply an alpha value to a tree. All nodes must have a
 * 'descendants' value, representing the number of descendants (including)
 * themselves.
 *
 * The tree size is the total number of descendants in the tree. The share of
 * each child of the root depends on its share in the number of descendants.
 *
 * Each child gets a proportional share in the given range [alpha_0, alpha_1]
 * and is positioned on the center of that share. It's children are recursively
 * positioned on that share.
 *
 * @param {TreeNode} treeRoot - The root node
 * @param {number} alpha_0 - Lower boundary of the range
 * @param {number} alpha_1 - Upper boundary of the range
 * @param {{x: number, y: number}} reference - The reference position
 */
function applyRecursiveAlphaByDescendants(treeRoot, alpha_0, alpha_1, reference) {
    if (!treeRoot.children) return;

    // The angle of the piece of pie
    var range = alpha_1 - alpha_0;

    // The total descendants in the subtree
    var treeSize = sum(treeRoot.children, 'descendants');

    // Start at the first boundary
    var alpha_current = alpha_0;

    treeRoot.children.forEach(function (child) {

        // The angle of the child piece and its center
        var portion = (child.descendants / treeSize) * range,
            center = alpha_current + portion / 2;

        // Keep track of the alpha boundary
        alpha_current += portion;

        // Apply the alpha and reference
        child.alpha = center;
        child.alpha_reference = reference;

        // Recurse
        applyRecursiveAlphaByDescendants(child, center - portion / 2, center + portion / 2, reference);
    });

}

/**
 * Calculate difference between angles alpha and beta mapped to the domain [-pi, +pi].
 * @param {number} alpha - the starting angle, (-inf, +inf)
 * @param {number} beta - the ending angle, (-inf, +inf)
 * @returns {number}
 */
function angularDifference(alpha, beta) {
    const pi = Math.PI;
    var gamma = ((beta - alpha) % (2 * pi) + 2 * pi) % (2 * pi);
    return gamma > pi ? gamma - 2 * pi : gamma;
}

/**
 * Gives the radial force from a vector towards a target angle.
 * The magnitude of the force is linear with the angular difference.
 * @param {number} x - The x coordinate of the vector
 * @param {number} y - The y coordinate of the vector
 * @param {number} alpha_target - the target angle to go to
 * @returns {{x: number, y: number}} x,y in (-inf, +inf)
 */
function radialForceVector(x, y, alpha_target) {
    const pi = Math.PI;

    var length = Math.sqrt(Math.pow(x, 2) + Math.pow(y, 2));

    // If the length is zero, no radial force
    if (length === 0) return {x: 0, y: 0};

    // Current angle of the vector
    var alpha = Math.atan2(y, x);

    // Difference with target
    var diff = angularDifference(alpha, alpha_target);

    // Calculate the moment
    var moment = (diff / pi);

    return {
        x: -y * moment,
        y: x * moment
    };
}

/**
 * Sum the values of a key in a collection of items
 * @param {Object[]} list - list of objects containing the key
 * @param {String} key - the key to sum
 * @returns {number} - the sum
 */
function sum(list, key) {
    return list.reduce(function (sum, item) {
        return sum + item[key];
    }, 0);
}

/**
 * A radial forcing function that takes a list of node objects containing at least the following
 * parameters:
 * - {number} x : x coordinate of node
 * - {number} y : y coordinate of node
 * - {number} alpha : target angle to go to
 * - {{x : number, y : number}} alpha_reference : reference position
 * @param {TreeNode[]} nodesList
 * @returns {force}
 */
function radialForce(nodesList) {
    var strength = 1,
        min_distance = 0,
        nodes = nodesList || [];

    /**
     * The forcing function
     * @param alpha
     */
    function force(alpha) {
        nodes.forEach(function (treeNode) {
            var origin = treeNode.alpha_reference,
                graphNode = treeNode.graphNode,
                forceVector;

            // Only apply force if target angle and current position are specified
            if ("alpha" in treeNode && "x" in graphNode && !isNaN(graphNode.x) && "y" in graphNode && !isNaN(graphNode.y) && origin) {

                forceVector = radialForceVector(graphNode.x - origin.x, graphNode.y - origin.y, treeNode.alpha);
                var dvx = (forceVector.x) * alpha * strength,
                    dvy = (forceVector.y) * alpha * strength;
                graphNode.vx += dvx;
                graphNode.vy += dvy;
            }
        });
    }

    /**
     * Initialize this force with a given set of nodes
     * @param {TreeNode[]} newNodes
     */
    force.initialize = function (newNodes) {
        nodes = newNodes;
    };

    /**
     * Set or get the strength of this force
     * @param newStrength
     * @returns {*}
     */
    force.strength = function (newStrength) {
        if (typeof newStrength !== "undefined") {
            strength = newStrength;
            return force;
        }
        else {
            return strength;
        }
    };

    /**
     * Set or get the minimum distance of this force
     * @param newDistance
     * @returns {*}
     */
    force.min_distance = function (newDistance) {
        if (typeof newDistance !== "undefined") {
            min_distance = newDistance;
            return force;
        }
        else {
            return min_distance;
        }
    };

    return force;
}


if (typeof module !== 'undefined') {
    module.exports = {
        applyRecursiveAlphaByDescendants: applyRecursiveAlphaByDescendants,
        angularDifference: angularDifference,
        radialForceVector: radialForceVector
    };
}
