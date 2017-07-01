/**
 * The Radial Controller initializes and connects all other modules necessary for the Network Display.
 *
 * 1. Navigation is used to manage clicking through the network and remembering the path taken.
 * 2. Positioning takes care of calculating the position of nodes.
 * 3. Simulation applies D3 forces to move nodes to their desired position.
 * 4. View draws all visuals (nodes, links and inspector) and updates the view when the simulation is updated
 *      or when new data is requested.
 * 5. Animation steps back through the network when the user clicks the 'BackToYou' button
 *
 * @constructor
 */
function RadialController() {

    var self = this;

    /**
     * Initialize all modules
     * @returns {RadialController}
     */
    self.initialize = function () {

        self.navigation = new RadialNavigation(get_node_info);
        self.positioning = new RadialPositioning();
        self.simulation = new RadialSimulation({radius_step : config.radius_step}).initialize();
        self.view = new RadialView(d3.select("#graph"), config).initialize();
        self.animation = new RadialSteppingAnimation(self.view.nodes, self.navigation, config.steppingAnimation);
        self.help = new HelpPage(config).initialize();

        // When the navigation comes back with a response, process the data
        self.navigation.setNeighborLevel(config.neighbor_level);
        self.navigation.bind('response', function (data) {
            self.update(processData(data));
        });

        // When a node is clicked, load the new data corresponding to that node
        self.view.nodes.bind("click", function (node) {
            self.animation.stop();
            self.navigation.step(node.public_key, node);
        });

        // When the simulation clock ticks, update the view
        self.simulation.onTick(self.view.tick);

        // Disable right mouse click functionality
        document.oncontextmenu = document.body.oncontextmenu = function () { return false; };

        return self;
    };

    /**
     * Start the display by loading the user's node and its neighbors.
     * @returns {RadialController}
     */
    self.start = function () {
        self.navigation.step("self");

        return self;
    };

    /**
     * Update the display when new data has arrived.
     * @returns {RadialController}
     */
    self.update = function (newGraphData) {

        // Set the positions on all graph nodes
        self.positioning.setNodePositions(newGraphData);

        // Update the view
        self.view.onNewData(newGraphData);

        // Update the simulation
        self.simulation.update(self.positioning.tree.nodes);

        return self;
    };

    /**
     * Animate back to the user node (along the taken path).
     */
    self.backToYou = function () {
        self.animation.rewindHistory();
    };

    /**
     * Show or hide the help page.
     */
    self.toggleHelpPage = function () {
        self.help.toggle();
    }

}
