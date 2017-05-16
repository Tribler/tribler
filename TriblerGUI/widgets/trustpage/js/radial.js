/**
 * These methods are concerned with calculations for radial layout.
 */

/**
 * Calculate Cartesian coordinates from a set of polar coordinates.
 * @param center_x
 * @param center_y
 * @param alpha
 * @param radius
 * @returns {{x: *, y: number}} y if flipped because screen-Y points down
 */
function polarToCartesian(center_x, center_y, alpha, radius) {
    return {
        x: center_x + radius * Math.cos(alpha),
        y: center_y - radius * Math.sin(alpha)
    }
}

/**
 * Apply a linear distribution of alpha within a given range to a given list of nodes.
 * @param nodes
 * @param alpha_start
 * @param alpha_end
 */
function applyAlphaLinear(nodes, alpha_start, alpha_end){
    var d_alpha = (alpha_end - alpha_start)/nodes.length;
    nodes.forEach(function(node, i){
        node.alpha = alpha_start + d_alpha * i;
    });
}
