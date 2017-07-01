/**
 * Configuration file for style properties of the links and nodes in the graph.
 */

var config = {
    byteUnits: ["B", "kB", "MB", "GB", "TB", "PB"],
    triblerOrange: "#E67300",
    background: "#202020",
    hoverInDelay: 0,
    hoverOutDelay: 500,
    steppingAnimation: {
        delayStepAfterHighlight: 500,
        delayUnhighlightAfterResponse: 300,
        delayHighlightAfterResponse: 750
    },
    link: {
        color: "#22FFD5",
        highlightColor: "#DD002A",
        strokeWidthMin: 2,
        strokeWidthMax: 10,
        opacityMinimum: 0.05,
        opacityDecrementPerLevel: 0.02,
        highlightDimmedOpacity: 0.1,
        highlightInDuration: 200,
        highlightOutDuration: 1000
    },
    node: {
        userLabelText: "You",
        publicKeyLabel: {
            color: "#202020",
            fontSize: 10,
            fontFamily: "sans-serif",
            fontWeight: "bold",
            characters: 3
        },
        marker: {
            radiusFactor: 2,
            startRadius: 60,
            fadeInDuration: 500,
            fadeOutDuration: 500
        },
        userMarker: {
            radiusFactor: 2,
            color: "#FFFFFF",
            opacity: 0.1
        },
        circle: {
            minRadius: 15,
            maxRadius: 25,
            cursor: "pointer",
            strokeWidth: 2,
            strokeColor: "#202020"
        },
        color: {
            domain: [0, 0.5, 1],
            range: ["#FF1D3E", "#F9FF15", "#0CFF18"]
        },
        hoverLabel: {
            publicKeyCharacters: 5,
            pageRankDecimals: 4,
            opacity: 0.85
        },
        highlightDimmedOpacity: 0.5,
        highlightInDuration: 200,
        highlightOutDuration: 1000
    },
    tooltip: {
        background: "#FFFFFF"
    },
    neighbor_ring: {
        strokeColor: "#333333"
    },
    radius_step: 120,
    neighbor_level: 2,
    help: {
        label: {
            fontSize: 10,
            fontFamily: "sans-serif",
            fontWeight: "bold",
            color: "#FFFFFF",
            offsetY: 10
        },
        nodes: {
            examplePublicKey: "#bcb",
            numberOfNodes: 5,
            circleColor: {
                nodeRadius: 20,
                labels: ["Freerider", "Unreliable", "Neutral", "Reliable", "Contributor"]
            },
            circleSize: {
                labels: ["Least", "Less", "Average", "More", "Most"]
            }
        },
        edges: {
            numberOfEdges: 3,
            edgeLength: 100,
            dividingWidth: 2,
            width: {
                labels: ["Little", "Average", "Much"]
            },
            separator: {
                labels: ["Right user", "Balanced", "Left user"]
            }
        },
        page: {
            // When the window width gets smaller than this, the help page and help button are not shown anymore
            minWindowWidth: 640
        }
    }
};

if (typeof module !== "undefined") {
    module.exports = config;
}
