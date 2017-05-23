/**
 * Configuration file for style properties of the links and nodes in the graph.
 */

var config = {
    link : {
        colorLinkSource : "#ffff00",
        colorLinkTarget : "#ff0000",
        strokeWidthMin : 2,
        strokeWidthMax : 10
    },
    node : {
        publicKeyLabel : {
            color : "#ffff00",
            fontSize : "12",
            fontFamily : "sans-serif",
            x : 24,
            y : 24
        },
        circle : {
            radius : 20,
            cx : 0,
            cy : 0,
            cursor : "pointer"
        },
        color : {
            domain : [0, 0.5, 1],
            range : ["red", "yellow", "green"]
        }
    }
};

if (typeof module !== "undefined") {
    module.exports = config;
}
