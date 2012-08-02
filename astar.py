import copy
import math
import operator
import random
import unittest

import euclid as eu

class Rect(object):
    def __init__(self, x, y, w, h):
        self.x,self.y,self.w,self.h = x,y,w,h

    def inflate_ip(self, dx,dy):
        self.x -= dx/2
        self.w += dx
        self.y -= dy/2
        self.h += dy

    def inflate(self, dx,dy):
        x = self.x - dx/2
        w = self.w + dx
        y = self.y - dy/2
        h = self.h + dy
        return Rect(x,y,w,h)

    @property
    def topleft(self):
        return (self.x, self.y)

    @property
    def bottomleft(self):
        return (self.x, self.y+self.h)

    @property
    def topright(self):
        return (self.x+self.w, self.y)

    @property
    def bottomright(self):
        return (self.x+self.w, self.y+self.h)


class Action(object):
    def __init__(self, name, deltas):
        self.name, self.deltas = name, deltas

class Item(object):
    def __init__(self, name, x,y, solid = Rect(0,0,10,10)):
        self.x, self.y, self.solid_area = x,y,solid

def scaleadd(origin, offset, vectorx):
    """
    From a vector representing the origin,
    a scalar offset, and a vector, returns
    a Vector3 object representing a point 
    offset from the origin.

    (Multiply vectorx by offset and add to origin.)
    """
    multx = vectorx * offset
    return multx + origin

def getinsetpoint(pt1, pt2, pt3, offset):
    """
    Given three points that form a corner (pt1, pt2, pt3),
    returns a point offset distance OFFSET to the right
    of the path formed by pt1-pt2-pt3.

    pt1, pt2, and pt3 are two tuples.

    Returns a Vector3 object.
    """
    origin = eu.Vector3(pt2[0], pt2[1], 0.0)
    v1 = eu.Vector3(pt1[0] - pt2[0], pt1[1] - pt2[1], 0.0)
    v1.normalize()
    v2 = eu.Vector3(pt3[0] - pt2[0], pt3[1] - pt2[1], 0.0)
    v2.normalize()
    v3 = copy.copy(v1)
    v1 = v1.cross(v2)
    v3 += v2
    if v1.z < 0.0:
        retval = scaleadd(origin, -offset, v3)
    else:
        retval = scaleadd(origin, offset, v3)
    return retval
 
#LOS algorithm/code provided by David Clark (silenus at telus.net) from pygame code repository
#Constants for line-segment tests
DONT_INTERSECT = 0
COLINEAR = -1

def have_same_signs(a, b):
    return ((int(a) ^ int(b)) >= 0)

def line_seg_intersect(line1point1, line1point2, line2point1, line2point2):
    x1 = line1point1[0]
    y1 = line1point1[1]
    x2 = line1point2[0]
    y2 = line1point2[1]
    x3 = line2point1[0]
    y3 = line2point1[1]
    x4 = line2point2[0]
    y4 = line2point2[1]

    a1 = y2 - y1  
    b1 = x1 - x2  
    c1 = (x2 * y1) - (x1 * y2)

    r3 = (a1 * x3) + (b1 * y3) + c1  
    r4 = (a1 * x4) + (b1 * y4) + c1

    if ((r3 != 0) and (r4 != 0) and have_same_signs(r3, r4)):
        return(DONT_INTERSECT)

    a2 = y4 - y3  
    b2 = x3 - x4  
    c2 = x4 * y3 - x3 * y4

    r1 = a2 * x1 + b2 * y1 + c2  
    r2 = a2 * x2 + b2 * y2 + c2

    if ((r1 != 0) and (r2 != 0) and have_same_signs(r1, r2)):  
         return(DONT_INTERSECT)

    denom = (a1 * b2) - (a2 * b1)  
    if denom == 0:  
        return(COLINEAR)
    elif denom < 0:
        offset = (-1 * denom / 2)
    else:
        offset = denom / 2
    
    num = (b1 * c2) - (b2 * c1)
    if num < 0:
        x = (num - offset) / denom
    else:
        x = (num + offset) / denom

    num = (a2 * c1) - (a1 * c2)  
    if num <0:
        y = (num - offset) / denom
    else:
        y = (num - offset) / denom

    return (x, y)

   
class Polygon(object):
    """
    >>> p = Polygon([(693, 455), (993, 494), (996, 637), (10, 637), (11, 490), (245, 466), (457, 474), (569, 527)])
    """
    def __init__(self, vertexarray = []):
        self.vertexarray = vertexarray
        self.center = None
        
    def __get__(self):
        return self.vertexarray
    def __set__(self, v):
        self.vertexarray = v

    def get_point(self, i):
        """ return a point by index """
        return self.vertexarray[i]

    def set_point(self, i, x, y):
        self.vertexarray[i] = (x, y)

    def count(self):
        """ number of points in vertex """
        return len(self.vertexarray)    

    def collide(self, x,y):
        """ Returns True if the point x,y collides with the polygon """
        pointsList = self.vertexarray
        xp = [float(p[0]) for p in pointsList]
        yp = [float(p[1]) for p in pointsList]
        # Initialize loop
        c=False
        i=0
        npol = len(pointsList)
        j=npol-1
        while i < npol:
            if ((((yp[i]<=y) and (y<yp[j])) or 
                ((yp[j]<=y) and(y<yp[i]))) and 
                (x < (xp[j] - xp[i]) * (y - yp[i]) / (yp[j] - yp[i]) + xp[i])):
                c = not c
            j = i
            i += 1
        return c

    def astar_points(self):
        #polygon offset courtesy http://pyright.blogspot.com/2011/07/pyeuclid-vector-math-and-polygon-offset.html
        polyinset = []
        OFFSET = -10
        i = 0
        old_points = copy.copy(self.vertexarray)
        old_points.insert(0,self.vertexarray[-1])
        old_points.append(self.vertexarray[0])        
        lenpolygon = len(old_points)
        while i < lenpolygon - 2:
            new_pt = getinsetpoint(old_points[i], old_points[i + 1], old_points[i + 2], OFFSET)
            polyinset.append((int(new_pt.x), int(new_pt.y)))
            i += 1
        return polyinset



def detect_intersect(start, end, r):
    """ Return True if the line between start and end intersects rect r """
    """ http://stackoverflow.com/questions/99353/how-to-test-if-a-line-segment-intersects-an-axis-aligned-rectange-in-2d """
    x1, y1 = start
    x2, y2 = end
    signs = []
    for x,y in [r.topleft, r.bottomleft, r.topright, r.bottomright]:
        f = (y2-y1)*x + (x1-x2)*y + (x2*y1-x1*y2)
        sign = int(f/abs(f)) if f != 0 else 0
        signs.append(sign) #remember if the line is above, below or crossing the point
    return False if len(set(signs)) == 1 else True #if any signs change, then it is an intersect

class Astar(object):
    def __init__(self, name, solids, walkarea, available_actions, nodes=[]):
        """
        solids: a list of Rects where path planning can not go through
        walkarea: a pyvida Polygon encompassing the entire walk area
        available_actions: WIP
        nodes: a raw list of nodes 
        """
        self.name = name
        self.solids = solids
        self.walkarea = walkarea 
        self.available_actions = available_actions
        self.nodes = nodes #a list of nodes
        print
        print "initial nodes",nodes
        self.nodes.extend(self.convert_solids_to_nodes())
        self.nodes.extend(self.convert_walkarea_to_nodes())
        self.nodes.extend(self.square_nodes())
        self.nodes = self.clean_nodes(self.nodes)
        print("all nodes", self.nodes)

    def convert_solids_to_nodes(self):
        """ inflate the rectangles and add them to a list of nodes """
        nodes = []
        for solid in self.solids:
            r = solid.inflate(2,2)
            for node in [r.topleft, r.bottomleft, r.topright, r.bottomright]:
                nodes.append(node)
        return nodes

    def convert_walkarea_to_nodes(self):
        """ deflate the walkarea and add its points to a list of nodes """
        if self.walkarea:
           print "walkarea points",self.walkarea.astar_points()
        nodes = self.walkarea.astar_points() if self.walkarea else []
        return nodes

    def square_nodes(self, nodes=None):
        """ Create nodes at right angles for other nodes """
        squared_nodes = []
        nodes = nodes if nodes else self.nodes
        for node in nodes:
            for node2 in nodes:
                if node != node2:
                    n1 = (node[0], node2[1])
                    n2 = (node2[0], node[1])
                    if n1 not in squared_nodes: squared_nodes.append(n1)
                    if n2 not in squared_nodes: squared_nodes.append(n2)
        print "square",squared_nodes
        return squared_nodes

    def clean_nodes(self, raw_nodes):
        """ Return a list of nodes that only exist inside the walkarea """
        if not self.walkarea: return raw_nodes
        nodes = []
        for node in raw_nodes:
            if node not in nodes and self.walkarea.collide(*node): nodes.append(node)
        return nodes

    def heuristic_cost_estimate(self, start, goal):
        return self.dist_between(start, goal)

    def reconstruct_path(self, came_from, current_node):
        if current_node in came_from:
            p = self.reconstruct_path(came_from, came_from[current_node])
            p.append(current_node)
            return p
        else:
            return [current_node]

    def neighbour_nodes(self, current):
        """ only return nodes:
        1. are not the current node
        2. that nearly vertical of horizontal to current
        3. that are inside the walkarea
        4. that the vector made up of current and new node doesn't intersect walkarea
        """
        #run around the walkarea and test each segment
        #if the line between source and target intersects with any segment of 
        #the walkarea, then disallow, since we want to stay inside the walkarea
        nodes = []
        for node in self.nodes:
            if node != current and (node[0] == current[0] or node[1] == current[1]):
                append_node = True
                if self.walkarea:
                    w0 = w1 = self.walkarea.vertexarray[0]
                    for w2 in self.walkarea.vertexarray[1:]:
                        if line_seg_intersect(node, current, w1, w2): 
                            append_node = False
                            break
                        w1 = w2
                    if line_seg_intersect(node, current, w2, w0): append_node = False
                if append_node == True and node not in nodes: nodes.append(node)
        return nodes

    def dist_between(self, current, neighbour):
        a = current[0] - neighbour[0]
        b = current[1] - neighbour[1]
        return math.sqrt(a**2 + b**2)

    def astar(self, start, goal):
        if goal not in self.nodes: self.nodes.append(goal)
        closedset = [] # set of nodes already evaluated
        openset = [start,]  # set of nodes to be evaluated, initially containing the start node

        came_from = {}  # map of navigated nodes (with their scores?)
        g_score = { start: 0, } #Cost from start along best know path
    
        # estimated total cost from start to goal through y
        f_score = {start: g_score[start] + self.heuristic_cost_estimate(start, goal)}
    
        while openset:
            f_score_sorted = sorted(f_score.iteritems(), key=operator.itemgetter(1))
            current = f_score_sorted[0][0]
            if current == goal:
                return self.reconstruct_path(came_from, goal)
            #if current not in openset: 
            openset.remove(current)
            del f_score[current]

            closedset.append(current)
            for neighbour in self.neighbour_nodes(current):
                if neighbour in closedset:
                    continue
                tentative_g_score = g_score[current] + self.dist_between(current, neighbour)
                if neighbour not in openset or tentative_g_score < g_score[neighbour]:
                     openset.append(neighbour)
                     came_from[neighbour] = current
                     g_score[neighbour] = tentative_g_score
                     f_score[neighbour] = g_score[neighbour] + self.heuristic_cost_estimate(neighbour, goal)
        return False

class TestAstarBasic(unittest.TestCase):
    def setUp(self):
        actions = {
            "left": Action("left", [(-5, 0), (-4, 0), (-2, 0)]),
            "right": Action("right", [(5, 0), (4, 0), (2, 0)]),
            "up": Action("up", [(0,-4)]),
            "down": Action("down", [(0,2)]),
            }
        nodes = [
            (0,0), (50,0), (50,100), (70,70), (100,100),
        ]
        walkarea = None
        self.astar = Astar("map1", [], walkarea, actions, nodes=nodes)

    def test_intersect(self):
        r = Rect(25,25,50,50)
        #line above
        f = detect_intersect((0,0), (100,0), r)
        self.assertFalse(f)
        #line below
        f = detect_intersect((0,100), (100,100), r)
        self.assertFalse(f)
        #line to left
        f = detect_intersect((0,0), (0,100), r)
        self.assertFalse(f)
        #line to right
        f = detect_intersect((100,0), (100,100), r)
        self.assertFalse(f)
        f = detect_intersect((100,50), (100,100), r)
        self.assertFalse(f)
        #line intersects
        f = detect_intersect((0,0), (100,100), r)
        self.assertTrue(f)

    def test_neighbour_nodes(self):
        nodes = self.astar.neighbour_nodes((0,0))
        self.assertEqual(nodes, [(50, 0), (0, 100), (0, 70), (70, 0), (100, 0)])

        nodes = self.astar.neighbour_nodes((50,0))
        self.assertEqual(nodes, [(0, 0), (50, 100), (70, 0), (100, 0), (50, 70)])

        nodes = self.astar.neighbour_nodes((50,100))
        self.assertEqual(nodes, [(50, 0), (100, 100), (0, 100), (50, 70), (70, 100)])

        nodes = self.astar.neighbour_nodes((100,100))
        self.assertEqual(nodes, [(50, 100), (0, 100), (100, 0), (70, 100), (100, 70)])

    def test_basic(self):
        path = self.astar.astar((0,0), (100, 100))
        self.assertEquals(path, [(0,0), (70,0),(70,100), (100,100)])

    def test_basic2(self):
        path = self.astar.astar((0,0), (50, 50))
        self.assertEquals(path, [(0,0), (50,0),(50,50)])



class TestAstarWalkarea(unittest.TestCase):
    def setUp(self):
        actions = {
            "left": Action("left", [(-5, 0), (-4, 0), (-2, 0)]),
            "right": Action("right", [(5, 0), (4, 0), (2, 0)]),
            "up": Action("up", [(0,-4)]),
            "down": Action("down", [(0,2)]),
            }
        walkarea = Polygon([(-10, -10),(140,-10),(140,40),(160,45),(160,-10),(210,-10),(210,110),(160,110),(165,62),(140,60),(140,110),(-10,110)])
        self.astar = Astar("map1", [], walkarea, actions)

    def test_neighbour_nodes(self):
        nodes = self.astar.neighbour_nodes((0,0))
        self.assertEqual(nodes, [(130, 0), (0, 100), (0, 47), (0, 57), (0, 52), (0, 49)])

        nodes = self.astar.neighbour_nodes((50,0))
        self.assertEqual(nodes, [(0,0), (130, 0)])

        nodes = self.astar.neighbour_nodes((50,100))
        self.assertEqual(nodes, [(130,100), (0,100)])

        nodes = self.astar.neighbour_nodes((100,100))
        self.assertEqual(nodes, [(130,100), (0,100)])

    def test_basic(self):
        path = self.astar.astar((0,0), (100, 100))
        self.assertEquals(path, [(0,0), (0,100), (100,100)])

    def test_basic2(self):
        path = self.astar.astar((0,0), (50, 50))
        self.assertEquals(path, [(130, 0), (0, 100), (0, 47), (0, 57), (0, 52), (0, 49)])

    def test_choke(self):
        path = self.astar.astar((0,0), (200, 0))
        self.assertEquals(path, [(0, 0), (0, 47), (200, 47), (200, 0)])


if __name__ == "__main__":
    print("To run tests, python -m unittest astar2.TestAstar")
