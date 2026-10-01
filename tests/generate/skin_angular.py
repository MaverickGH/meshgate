"""Runnable via meshgate.py gen --code tests/generate/skin_angular.py --tiers pc."""
def build(mg):
    color = mg.color("fur", "#786968")
    points = [(0, 0, 0.1), (0, 0, 0.3), (0.1, 0, 0.4)]
    angular = mg.skin(points, 0.05, color, subdiv=0, smooth=False)
    rounded = mg.skin([(x + 0.3, y, z) for x, y, z in points], 0.05, color)
    assert len(angular.data.polygons) < len(rounded.data.polygons)
    assert all(not p.use_smooth for p in angular.data.polygons)
    mg.join("tail_shapes", [angular, rounded])
