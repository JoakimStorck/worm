import numpy as np
from shapely.geometry import Point

def random_points_in_polygon(polygon, n_points):
    points = []
    minx, miny, maxx, maxy = polygon.bounds
    while len(points) < n_points:
        x, y = np.random.uniform(minx, maxx), np.random.uniform(miny, maxy)
        p = Point(x, y)
        if polygon.contains(p):
            points.append((x, y))
    return points
