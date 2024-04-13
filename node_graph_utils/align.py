""" Node alignment utilities. """
from collections import defaultdict

import nuke

from .dag import (sort_nodes_by_position, sort_nodes_by_distance,
                  get_nodes_bounds, NodeWrapper, node_center)


def smart_align(direction, selection=None):
    """
    Smart Align tool inspired by W_smartAlign from Nukepedia.
    Aligns single nodes to the closest node in the selected direction,
    or multiple nodes to the furthest in that direction.

    Args:
        direction (Direction): A Direction object with attributes axis, descending, center.
        selection (list[nuke.Node]): (Optional) list of nodes to align. Selected nodes if None
    """
    if not selection:
        return

    selection = [NodeWrapper(n) for n in selection]

    # Store margins for the backdrop nodes:
    backdrops = [nw for nw in selection if nw.is_backdrop]
    for backdrop in backdrops:
        backdrop.store_margins()

    # --------------------------------------
    # MULTIPLE NODES
    # if multiple nodes are selected, all the nodes will align to the node that's the furthest away
    # in the specified direction
    # --------------------------------------

    if len(selection) > 1:

        bounding_rect = get_nodes_bounds(selection, center_only=True)

        if direction.center:
            target = bounding_rect.center().toTuple()[direction.axis]
        else:
            coords = bounding_rect.getCoords()
            target = coords[direction.axis + int(not direction.descending) * 2]

        collision_nodes = []

    # --------------------------------------
    # SINGLE NODE
    # if only one node is selected,
    # the selected node will snap to the nearest connected node (both input and output) in the specified direction
    # --------------------------------------

    else:
        if direction.center:  # Align center with single node doesn't make sense, so return.
            return

        cur_node = selection[0]

        # create a list of all the connected nodes
        input_nodes = cur_node.dependencies(nuke.INPUTS)
        output_nodes = [n for n in cur_node.dependent(nuke.INPUTS, forceEvaluate=False) if n.Class() != 'Viewer']

        # Sort the nodes, so as soon as we find one of interest we can bail
        collision_nodes = sort_nodes_by_position(input_nodes + output_nodes, direction.axis, direction.descending)
        collision_nodes = [NodeWrapper(n) for n in collision_nodes]  # Wrap 'em

        target = None
        cur_node_pos = node_center(cur_node)[direction.axis]
        for node in collision_nodes:
            node_pos = node_center(node)[direction.axis]
            if direction.descending:
                if node_pos < cur_node_pos:
                    target = node_pos
                    break
            else:
                if node_pos > cur_node_pos:
                    target = node_pos
                    break

        if not target:
            # Choice here was to either bail, or just move the node in that direction by a set amount
            step = 5
            target = cur_node_pos - step if direction.descending else cur_node_pos + step

    # --------------------------------------
    # MOVE THE NODES
    # --------------------------------------

    undo = nuke.Undo()
    undo.begin('Align Nodes')
    try:
        for node in sort_nodes_by_distance(selection, direction.axis, target):
            if not node.is_backdrop:
                move_no_collision(node, collision_nodes, direction.axis, target)
                collision_nodes.append(node)  # We don't want to collide with a node until it's been placed

        # Realign backdrops
        backdrops = sorted(backdrops, key=lambda bd: bd.node['z_order'].value(), reverse=True)
        for backdrop in backdrops:
            backdrop.restore_margins()
    finally:
        undo.end()


def distribute_nodes(nodes, axis=0, tolerance=6):
    """
    Equalize the distance between nodes, taking their alignment into account.

    Args:
        nodes (list[nuke.Node]): List of nodes to distribute.
        axis (int): Axis index, 0 for X, 1 for Y
        tolerance (int): Consider nodes less than this distance apart to be in the same row when cataloguing
    """
    # Split backdrops from regular nodes
    backdrops = []
    other_nodes = []
    for node in nodes:
        wrapper = NodeWrapper(node)
        if wrapper.is_backdrop:
            backdrops.append(wrapper)
        else:
            other_nodes.append(wrapper)

    # Catalogue nodes
    rows = defaultdict(list)
    current_row = None
    for node in sort_nodes_by_position(other_nodes, axis=axis):
        pos = node_center(node)[axis]
        # In certain cases some nodes are very slightly offset from one another, and without tolerance it creates
        # multiple rows where it looks like there should be only one.
        # First method of rounding by tolerance failed, so rely on sorted nodes and keeping track of row:
        if current_row is None or abs(pos-current_row) > tolerance:
            rows[pos].append(node)
            current_row = pos
        else:
            rows[current_row].append(node)

    if len(rows) < 2:
        return

    # Store backdrops margins
    for bd in backdrops:
        bd.store_margins()

    positions = sorted(rows.items())
    last_row = positions[-1][0]
    first_row = positions[0][0]
    spacing = (last_row - first_row) // (len(positions) - 1)

    undo = nuke.Undo()
    undo.begin("Distribute Nodes")
    for i, (position, nodes) in enumerate(positions):
        new_pos = first_row + i * spacing
        for node in nodes:
            node.move_center(new_pos, axis)

    # Restore backdrops margins
    for bd in sorted(backdrops, key=lambda bd: bd.node['z_order'].value(), reverse=True):
        bd.restore_margins()

    undo.end()


def mirror_nodes(nodes, axis=0):
    """
    Mirror nodes either horizontally or vertically.

    Contributor: Frank Rueter
    Website: www.ohufx.com
    off of nukepedia.com

    Args:
        nodes (list[nuke.Node]): List of nodes to mirror.
        axis (int): 0 for X, 1 for Y
    """
    if len(nodes) < 2:
        return
    nodes = [NodeWrapper(n) for n in nodes]
    center = get_nodes_bounds(nodes).center().toTuple()[axis]
    for node in nodes:
        pos = node_center(node)[axis]
        node.move_center(pos - (2 * (pos - center)), axis)


# Utils - Move Nodes
def move_no_collision(node, nodes_to_collide, axis, destination, padding=3):
    """
    Moves a node on one axis making sure it's not intersecting another node (if this node is in nodes_to_collide)

    Args:
        node (dag_utils.dag.NodeWrapper): Node to move. Should be wrapped in a NodeWrapper.
        nodes_to_collide (list[dag_utils.dag.NodeWrapper]): List of NodeWrappers to use as collision objects.
        axis (int): Axis index, 0 for X, 1 for Y
        destination (int): target value that the node is trying to reach
        padding (int): padding to add around nodes
    """
    direction_mult = -1 if node_center(node)[axis] < destination else 1
    colliding = True
    i = 0
    while colliding and i < 100:
        colliding = False
        node.move_center(destination, axis)
        for collider in nodes_to_collide:
            if collider is node or collider.is_backdrop:
                continue
            if collider.intersects(node.bounds):
                destination += (collider.intersected(node.bounds).size().toTuple()[axis] + padding) * direction_mult
                colliding = True
                break
        i += 1
