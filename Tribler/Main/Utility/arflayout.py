# Written by Egbert Bouman
import random
import math


class ArfLayout():

    def __init__(self):
        self.layout = {}

    def remove(self, toRemove):
        for vertexid in toRemove:
            if vertexid in self.layout:
                self.layout.pop(vertexid)

        new_layout = {}
        for index, vertexid in enumerate(sorted(self.layout)):
            new_layout[index] = self.layout[vertexid]
        self.layout = new_layout

    def calculate(self, toInsert, graph):
        # We just run one iteration, as we want the algorithm to use as little resources as possible.

        numNodes = graph.vcount()
        self.advance(toInsert, numNodes, graph)

        # Calculate positions in advance
        x, y = zip(*self.layout.values())
        minX, maxX, minY, maxY = min(x), max(x), min(y), max(y)
        xRange, yRange = maxX - minX, maxY - minY

        positions = {}

        if xRange != 0 and yRange != 0:
            for vertexid in range(graph.vcount()):
                if not self.layout.has_key(vertexid):
                    continue
                x, y = self.layout[vertexid][0], self.layout[vertexid][1]
                x_scaled, y_scaled = (x - minX) / xRange, (y - minY) / yRange
                positions[vertexid] = (x_scaled, y_scaled)

        return positions

    def advance(self, toInsert, numNodes, graph):
        for vertexid in toInsert:
            self.layout[vertexid] = self.get_position(vertexid, numNodes, graph)
        toInsert.clear()

        for index in range(numNodes):
            pos = self.layout.get(index, None)
            if pos:
                fX, fY = self.get_force(index, numNodes, graph)
                self.layout[index] = [ pos[0] + fX * 2, pos[1] + fY * 2 ]

    def get_force(self, vertexid, numNodes, graph):
        x, y = self.layout.get(vertexid, (0.0, 0.0))

        forceX, forceY = (0, 0)

        if x == 0 and y == 0:
            return (forceX, forceY)

        for otherVertexid in range(0, numNodes):
            if vertexid != otherVertexid:
                otherX, otherY = self.layout.get(otherVertexid, (0, 0))
                if otherX == 0 and otherY == 0:
                    continue

                tempX = otherX - x
                tempY = otherY - y

                mult = 3 if graph.are_connected(vertexid, otherVertexid) else 1
                mult *= 0.2 / math.sqrt(numNodes)
                addX = tempX * mult
                addY = tempY * mult
                forceX += addX
                forceY += addY

                mult = 8 / math.sqrt(tempX ** 2 + tempY ** 2)
                addX = tempX * mult
                addY = tempY * mult
                forceX -= addX
                forceY -= addY

        return (forceX, forceY)

    def get_position(self, vertexid, numNodes, graph):
        nvertices = []
        if vertexid < numNodes:
            for otherVertexid in graph.neighbors(vertexid):
                if otherVertexid in self.layout.keys():
                    nvertices.append(otherVertexid)

        pos = self.layout.get(vertexid, None)
        if not pos:
            pos = [random.random(), random.random()]

        if nvertices:
            for otherVertexid in nvertices:
                x2, y2 = self.layout[otherVertexid]
                pos[0] += x2
                pos[1] += y2
            mult = 1.0 / len(nvertices)
            pos[0] = pos[0] * mult
            pos[1] = pos[1] * mult
        return pos

def CubicHermite(t, p0, p1, m0, m1):
    t2 = t * t
    t3 = t2 * t
    return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1

def CubicHermiteInterpolate(t1, t2, t3, x1, x2, t):
    v = (x2 - x1) / (t1 / 2.0 + t2 + t3 / 2.0)
    d1 = v * t1 / 2.0
    d2 = v * t2

    if t <= t1:
        interpolate = CubicHermite(t / t1, x1, x1 + d1, 0, d2 / t2 * t1)
    elif t <= t1 + t2:
        interpolate = x1 + d1 + d2 * (t - t1) / t2
    else:
        interpolate = CubicHermite((t - t1 - t2) / t3, x1 + d1 + d2, x2, d2 / t2 * t3, 0)
    return interpolate
