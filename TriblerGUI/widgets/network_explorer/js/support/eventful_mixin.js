/**
 * Adds event-handling functionality to an object.
 */
function applyEventfulMixin(object) {

    object.listeners = {};

    /**
     * Bind a listener to a particular event.
     * @param {String} eventName
     * @param {Function} listener
     */
    object.bind = function (eventName, listener) {
        (object.listeners[eventName] = object.listeners[eventName] || []).push(listener);
    };

    /**
     * Fire an event, calling all listeners.
     * @param {String} eventName
     * @param {Array} args - the arguments to pass to the listener
     * @param {Object|null} thisArg - the argument to pass as 'this'
     */
    object.fire = function (eventName, args, thisArg) {
        if (object.listeners[eventName]) {
            object.listeners[eventName].forEach(function (listener) {listener.apply(thisArg || object, args)});
        }
    };

    /**
     * Passes the event, with provided arguments and this-object directly to all listeners.
     * @param eventName
     * @returns {Function}
     */
    object.getEventHandlers = function (eventName) {
        return function () { object.fire(eventName, arguments, this); }
    }

}

/**
 * Export functions so Mocha can test it
 */
if (typeof module !== 'undefined') {
    module.exports = {
        applyEventfulMixin: applyEventfulMixin
    };
}
