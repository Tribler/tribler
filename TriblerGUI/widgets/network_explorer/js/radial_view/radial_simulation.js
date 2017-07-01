/**
 * The force simulation for the Radial Layout View. This class sets up the d3 simulation
 * and updates it when new data is presented.
 *
 * @param options
 * @constructor
 */
function RadialSimulation(options) {

    var self = this;

    self.simulation = null;

    var defaults = {
        alpha_decay: 0.01,
        radial_force_strength: 0.1,
        radial_force_min_distance: 30,
        link_strength: 0.1,
        radius_step: 80
    };

    self.config = Object.assign({}, defaults, options || {});

    /**
     * The centerfix object
     */
    var centerFix = {
        x: 0,
        y: 0,
        local_key: 0,
        inCenter: true
    };

    /**
     * Initialize the simulation
     * @returns {RadialSimulation}
     */
    self.initialize = function () {

        self.simulation = d3.forceSimulation()

        // Link force to keep distance between nodes
            .force("link", d3.forceLink()
                .id(function (d) { return d.local_key; })
                .distance(function (d) { return d.dist; })
                .strength(self.config.link_strength))

            // Centering force (used for focus node)
            .force("center", d3.forceCenter(0, 0))

            // Torque force to keep nodes at correct angle
            .force("torque", radialForce()
                .strength(self.config.radial_force_strength)
                .min_distance(self.config.radial_force_min_distance))

            // Make sure the simulation never dies out
            .alphaDecay(self.config.alpha_decay);

        // Only apply the centering force on the center fix
        filterForceNodes(self.simulation.force("center"), function (n) {
            return n.inCenter;
        });

        return self;
    };

    /**
     * Set the tick callback, which is called on every time-step of the simulation
     * @param tick
     * @returns {RadialSimulation}
     */
    self.onTick = function (tick) {
        self.simulation.on("tick", tick);

        return self;
    };

    /**
     * Get the center fix object, the anchor for the focus node.
     * @returns {Object}
     */
    self.getCenterFix = function () {
        return centerFix;
    };

    /**
     * Update the Radial Simulation with graph and tree nodes
     * @param {TreeNode[]} treeNodes
     * @returns {RadialSimulation}
     */
    self.update = function (treeNodes) {

        // Reset alpha
        self.simulation.alpha(1);

        // Restart simulation
        self.simulation.restart();

        // Add the center-fix node to the nodes
        centerFix.local_key = treeNodes.length;

        // Apply the nodes to the simulation
        self.simulation.nodes(treeNodes.map(function (n) {return n.graphNode}).concat([centerFix]));

        // Apply the torque force only to the tree nodes
        self.simulation.force('torque').initialize(treeNodes);

        // Apply a distance force that puts a node on the correct circle
        var forcingLinks = treeNodes.map(function (treeNode) {
            return {
                source: centerFix.local_key,
                target: treeNode.graphNode.local_key,
                dist: treeNode.depth * self.config.radius_step
            };
        });

        self.simulation.force("link")
            .links(forcingLinks);

        return self;
    };

}
