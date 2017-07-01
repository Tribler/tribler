/**
 * Animate stepping through the network along a given path by highlighting the steps and then navigating there.
 *
 * The animation time-line:
 * 1. Highlight the first node in the queue (if in view)
 * 2. Navigate to the first node in the queue (and pop it)
 * 3. The response comes back
 * 4. Unhighlight the (new) focus node
 * 5. If queue not empty, repeat from 1.
 *
 * @param {RadialNodes} radialNodes
 * @param {RadialNavigation} navigation
 * @param {Object} options
 * @constructor
 */
function RadialSteppingAnimation(radialNodes, navigation, options) {

    var self = this,
        defaults = {};

    self.config = Object.assign({}, defaults, options || {});
    self.navigation = navigation;
    self.radialNodes = radialNodes;
    self.path = [];
    self.playing = false;
    self.highlightedNodes = [];

    /**
     * Play the navigation history in reverse order.
     */
    self.rewindHistory = function () {
        if (navigation.history.length > 1)
            self.play(navigation.history.slice(0, -1).reverse());
    };

    /**
     * Start playing the animation along a given path of public keys (if not already playing)
     * @param {String[]} path - public keys to step navigate to
     * @returns {boolean} - false if play ignored (when already playing), true otherwise
     */
    self.play = function (path) {
        if (self.playing) return false;

        self.playing = true;
        self.path = path;
        self.highlightAndStep();

        return true;
    };

    /**
     * Highlight the next node, and after a delay, navigate to it.
     */
    self.highlightAndStep = function () {
        if (!self.playing) return;

        self.radialNodes.applyMarker([self.path[0]]);
        self.highlightedNodes.push(self.path[0]);

        setTimeout(function () {
            if (!self.playing) return;

            self.navigation.step(self.path[0]);
        }, self.config.delayStepAfterHighlight);
    };

    /**
     * When the response comes back and still animating, unhighlight the focus node and after a delay make
     * the next step.
     */
    self.onResponse = function () {
        if (!self.playing) return;

        self.path = self.path.slice(1);

        setTimeout(self._unhighlightCurrentFocusNode, self.config.delayUnhighlightAfterResponse);

        if (self.path.length === 0) return self.stop();

        setTimeout(self.highlightAndStep, self.config.delayHighlightAfterResponse);
    };

    // Directly bind this method to the navigation's response event
    self.navigation.bind("response", self.onResponse);

    /**
     * Stop the animation.
     */
    self.stop = function () {
        self.playing = false;
        self.path = [];

        // Clear highlights set by the animation.
        self.radialNodes.removeMarker(self.highlightedNodes);
        self.highlightedNodes = [];
    };

    /**
     * Unhighlight the current focus node
     * @private
     */
    self._unhighlightCurrentFocusNode = function () {
        var current_pk = self.navigation.getCurrentPublicKey();
        if (current_pk) {
            self.radialNodes.removeMarker(current_pk);

            // Remove the current_pk from the highlighted nodes list
            var index = self.highlightedNodes.indexOf(current_pk);
            if(index >= 0) self.highlightedNodes.splice(index, 1);
        }
    };

}
