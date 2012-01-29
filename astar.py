from math import hypot
import copy

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


def can_see(source, target, blocking_rects_list, walkarea):

    """
    Performs a los check from the center of the source to the center of the target.
    Makes the following assumtion:
        1 - Both the source and target are objects that include a pygame.Rect() member object
            called object.rect.

    Returns 1 of line of sight is clear. Returns 0 if it is blocked.
    """
    los_line_p1 = source
    los_line_p2 = target
    for rect in blocking_rects_list:
        block_p1 = rect[0], rect[1]
        block_p2 = rect[0], rect[1] + rect[3]
        if line_seg_intersect(los_line_p1, los_line_p2, block_p1, block_p2):
            return 0
        block_p1 = rect[0] + rect[2], rect[1]
        block_p2 = rect[0] +rect[2], rect[1]  + rect[3]
        if line_seg_intersect(los_line_p1, los_line_p2, block_p1, block_p2):
            return 0
    #run around the walkarea and test each segment
    #if the line between source and target intersects with any segment of 
    #the walkarea, then disallow, since we want to stay inside the walkarea
    if walkarea:
#        print los_line_p1, los_line_p2, #walkarea.polygon.vertexarray
        w0 = w1 = walkarea.polygon.vertexarray[0]
        for w2 in walkarea.polygon.vertexarray[1:]:
            if line_seg_intersect(los_line_p1, los_line_p2, w1, w2): 
#                print "intersect",w1,w2
                return 0
            w1 = w2
        if line_seg_intersect(los_line_p1, los_line_p2, w2, w0): 
#            print "intersectb",w2,w0
            return 0 #close loop
#        print "safe"
    return 1



def distance(a, b):
    """ distance between two points """
    return hypot((b[0]-a[0]), (b[1]-a[1]))

def successors(x, nodes, solids, walkarea=None):
    """ return list of nodes sorted by distance from x node """
    dists = []
    for n in nodes: #only add node if we can see it from x node
        if can_see(x, n, solids, walkarea):
            dists.append((int(distance(n,x)), n))
    dists.sort()
    s = [[b[1]] for b in dists if b[0] != 0]
#	print "from",x,"can go",s
    return s

def enqueue(q,p,y):
	q.append(y)
	
def square_off_nodes(start, nodes, walkarea):
    """ add nodes to existing list that are at right angles between nodes """
    
    original_nodes = copy.copy(nodes)
    original_nodes.append(start)
    print(original_nodes)
    r = []
    w = 20
    for node1 in original_nodes: #add our corner nodes to master node list
        for node2 in original_nodes:
            if node1 != node2:
                new1 = node1[0], node2[1]
                new2 = node2[0], node1[1]
                for x,y in [new1, new2]:
                    nodes.append((x,y))

    print(nodes)                 
    for i, node in enumerate(nodes):
        add_node = True
        if walkarea and not walkarea.polygon.collide(*node): add_node = False
        if add_node == True:
            for j,node2 in enumerate(r): #test for nodes that are too similar
                x,y=node
                tx,ty=node2
                if tx-w < x < tx + w and ty-w < y < ty + w: 
                    pass
#                    print("too close")
                    add_node = False
            if add_node == True: r.append((x,y))
    print(len(r))                        
    return r
	
MAP_NODES = []

def AStar(start, goal, nodes, solids,walkarea=None):
     """ <nodes> is a list of points that the path could go through
       <solids> is a list of rectangles (x,y,w,h) that the path may not go through
       <walkarea> is a list of points that describe the area the path between nodes must be contained in. 
     """
     closed = []
     q = [[start]]
     nodes.append(goal)
#     nodes = square_off_nodes(start, nodes, walkarea)
#     global MAP_NODES
#     MAP_NODES = nodes
#     return nodes[:3]
     while len(q) > 0:
         p = q.pop(0) #a path to try
         x = p[-1]  #a node to try
         if x in closed: continue
         if x == goal: return p #found path
         closed.append([x])
         for y in successors(x, nodes, solids, walkarea): #nodes nearest to x
             newP = copy.copy(p)
             newP.extend(y)
             q.append(newP)
     return False

def main():
	start = 100,100
	end = 700,120
	nodes = [(400,50), (400,160), (500,160), (500, 50)]
        solids = [(405, 25, 90, 100)]
#	solids = []
	p = AStar(start, end, nodes, solids)
	if p == False:
		print "unable to find path"
	else:
		print "path",p
	

if __name__ == "__main__":
    main()
