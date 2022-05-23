"""
Generic dag utilities
"""

# Qt
import re
from collections import namedtuple

from PySide2 import QtCore, QtWidgets, QtGui

# nuke
import nuke

DAG_TITLE = "Node Graph"
DAG_OBJECT_NAME = "DAG"

Direction = namedtuple('Direction', 'axis, descending, center')
AXIS_X = 0
AXIS_Y = 1
RIGHT = Direction(axis=AXIS_X, descending=False, center=False)
LEFT = Direction(axis=AXIS_X, descending=True, center=False)
DOWN = Direction(axis=AXIS_Y, descending=False, center=False)
UP = Direction(axis=AXIS_Y, descending=True, center=False)
CENTER_X = Direction(axis=AXIS_X, descending=False, center=True)
CENTER_Y = Direction(axis=AXIS_Y, descending=False, center=True)


# Group Dags
def get_dag_widgets(visible=True):
    """
    Gets all Qt objects with DAG in the object name

    Args:
        visible (bool): Whether or not to return only visible widgets.

    Returns:
        list[QtWidgets.QWidget]
    """
    dags = []
    all_widgets = QtWidgets.QApplication.instance().allWidgets()
    for widget in all_widgets:
        if DAG_OBJECT_NAME in widget.objectName():
            if not visible or (visible and widget.isVisible()):
                dags.append(widget)
    return dags


def get_current_dag():
    """
    Returns:
        QtWidgets.QWidget: The currently active DAG
    """
    visible_dags = get_dag_widgets(visible=True)
    for dag in visible_dags:
        if dag.hasFocus():
            return dag

    # IF None had focus, and we have at least one, use the first one
    if visible_dags:
        return visible_dags[0]
    return None


def get_dag_node(dag_widget):
    """ Get a DAG node for a given dag widget. """
    title = str(dag_widget.windowTitle())
    if DAG_TITLE not in title:
        return None
    if title == DAG_TITLE:
        return nuke.root()
    return nuke.toNode(title.replace(" " + DAG_TITLE, ""))


def with_active_dag(func):
    """
    Decorator: Runs the decorated functions with the context of the currently active DAG
    Notes:
        Seems not required anymore? Keeping around for now.
    """
    def wrapper(*args, **kwargs):
        original_context = nuke.thisGroup()
        active_dag = get_current_dag()
        dag_node = None
        if active_dag:
            dag_node = get_dag_node(active_dag)
        try:
            if dag_node:
                dag_node.begin()
            return func(*args, **kwargs)
        finally:
            if dag_node:
                dag_node.end()
            original_context.begin()

    return wrapper


# Bounds functions
def get_node_bounds(node):
    """
    Return a QRectF corresponding to the node dag bounding box / position

    Note: There is a bug in nuke when a freshly created node is being moved where the width/height
    collapses to 0:

        node = nuke.nodes.Grade()
        node.setXYpos(0, 0)
        print node.screenWidth(), node.screenHeight()
        # Result: 0 0
        # Result should be: 80 20

    We handle this in the code

    :param nuke.Node node: Nuke node to get bounds for
    :rtype: QtCore.QRectF
    """
    if isinstance(node, NodeWrapper):
        return node.bounds
    if node.Class() == "BackdropNode":
        width = node['bdwidth'].value()
        height = node['bdheight'].value()
    else:
        width = node.screenWidth()
        height = node.screenHeight()

    if width == 0:  # Handle a bug as mentioned in docstring
        temp_node = getattr(nuke.nodes, node.Class())()  # Make temp node with same class as corrupted node
        try:
            return get_node_bounds(temp_node)
        finally:
            nuke.delete(temp_node)

    return QtCore.QRectF(node.xpos(), node.ypos(), width, height)


def get_nodes_bounds(nodes, center_only=False):
    """
    Get the combined DAG bounding box of all the nodes in the list

    Args:
        nodes (list): List of nuke nodes to get bounds for
        center_only (bool): If True, get the bounding rectangle that encompasses the center points of the nodes

    Returns:
        QtCore.QRectF
    """
    if not nodes:
        raise ValueError("No nodes provided to get_nodes_bounds()")
    all_bounds = [get_node_bounds(n) for n in nodes]
    if center_only:
        poly = QtGui.QPolygon([n.center().toPoint() for n in all_bounds])
        return poly.boundingRect()
    bounds = QtCore.QRectF(all_bounds[0])  # Make a new rect so we don't modify the initial one
    for bound in all_bounds[1:]:
        bounds |= bound
    return bounds


def get_nodes_in_bounds(bounds, include_overlapping=False):
    """
    Return all the nodes that are within a rectangle (bounds).
    If include_overlapping is True, a node will be included even if isn't fully contained by the bounds.

    Args:
        bounds (QtCore.QRectF): QRectF representing the bounds
        include_overlapping (bool): Whether to include nodes that aren't fully enclosed by the bounds.

    Returns:
        list: nuke nodes
    """
    if include_overlapping:
        return [node for node in nuke.allNodes() if get_node_bounds(node).intersects(bounds)]
    return [node for node in nuke.allNodes() if bounds.contains(get_node_bounds(node))]


def calculate_bounds_adjustment(bounds, target_bounds):
    """ Calculate adjust values to apply to 'bounds' in order to match 'target_bounds'

    Args:
        bounds (QtCore.QRectF or NodeWrapper): Original Bounds
        target_bounds (QtCore.QRectF or NodeWrapper): Desired Bounds

    Returns:
        tuple[int, int, int, int]: Bounds adjustments
    """
    bounds_coords = bounds.getCoords()
    target_coords = target_bounds.getCoords()
    return tuple(target_coords[i] - bounds_coords[i] for i in range(4))


# Utils - Querying
def node_center(node):
    """
    A simple function to find a node's center point.
    :param node:
    :return x_pos, y_pos:
    """
    if not isinstance(node, NodeWrapper):
        node = NodeWrapper(node)
    return node.center().toTuple()


def last_clicked_position():
    """
    returns the x and y coordinates of the last position clicked by the user

    Returns:
        QtCore.QPoint(): Last clicked position in node graph
    """
    selection = clear_selection()

    temp = nuke.createNode("Dot", inpanel=False)
    try:
        return get_node_bounds(temp).center()
    finally:
        nuke.delete(temp)
        select(selection)


def get_label_size(node):
    """ Calculate the size of a label for a nuke Node

    Args:
        node (nuke.Node):

    Returns:
        QtCore.QSize: Size of the label
    """
    regex = r'^(.+?)( Bold)?( Italic)?$'
    match = re.match(regex, node['note_font'].value())
    font = QtGui.QFont(match.group(1))
    font.setBold(bool(match.group(2)))
    font.setItalic(bool(match.group(3)))
    font.setPixelSize(node['note_font_size'].value())
    metrics = QtGui.QFontMetrics(font)
    return metrics.size(0, node['label'].value())


# Sorting
def sort_nodes_by_position(nodes, axis=0, reverse=False):
    """
    Sort nodes based by position, using either axis X or Y as primary key, other axis as secondary key.

    Args:
        nodes (list): List of Nuke Nodes
        axis (int): 0 for x, 1 for y
        reverse (bool): whether to reverse order

    Returns:
        list: sorted list
    """
    return sorted(nodes, key=lambda n: (node_center(n)[axis], node_center(n)[1-axis]), reverse=reverse)


def sort_nodes_by_distance(nodes, axis, target):
    """
    Sort nodes based on their distance from the target, on provided axis
    Args:
        nodes (list): List of Nuke Nodes
        axis (int): 0 for x, 1 for y
        target (int): Point from which the distance should be calculated

    Returns:
        list: sorted list
    """
    return sorted(nodes, key=lambda n: abs(node_center(n)[axis] - target))


# Selection
def clear_selection():
    """ Deselect all nodes, and return previous selection """
    selection = nuke.selectedNodes()

    for selected_nodes in selection:
        selected_nodes.setSelected(False)

    return selection


def select(nodes):
    """ Select the provided nodes """
    for node in nodes:
        node.setSelected(True)


def create_node_with_defaults(node_class_name):
    """ Create a node with the default values from the user, but do not select it, place it, or connect it """
    node_class = getattr(nuke.nodes, node_class_name)
    node = node_class()
    node.resetKnobsToDefault()


class NodeWrapper(object):
    """ Wraps a nuke node with its bounds, and exposes all the methods from QRectF to be used on the node """

    def __init__(self, node):
        """
        Args:
            node (nuke.Node): Node to wrap
        """
        self.bounds = get_node_bounds(node)
        self.node = node
        self.is_backdrop = node.Class() == "BackdropNode"
        self._nodes_and_margins = None  # For backdrops only

    def __getattr__(self, item):
        try:
            attr = getattr(self.bounds, item)
        except AttributeError:
            return getattr(self.node, item)
        if callable(attr):
            return self._wrapped(attr)
        return attr

    def _wrapped(self, func):
        def wrapper(*args, **kwargs):
            before_size = self.bounds.size()
            result = func(*args, **kwargs)
            self._commit_move()
            if self.bounds.size() != before_size:
                self._commit_resize()
            return result
        return wrapper

    def _commit_move(self):
        new_pos = self.bounds.topLeft().toPoint()
        self.node.setXYpos(new_pos.x(), new_pos.y())

    def _commit_resize(self):
        if not self.is_backdrop:
            raise NotImplementedError(
                "Tried to resize a node other than a backdrop, which is not supported. You may get unexpected results."
            )
        self._commit_move()
        self.node['bdwidth'].setValue(int(self.bounds.width()))
        self.node['bdheight'].setValue(int(self.bounds.height()))

    def normalize(self):
        self.bounds = self.bounds.normalized()
        self._commit_move()
        self._commit_resize()

    def move_center(self, value, axis):
        """ Extra method to allow moving a node center based on a single axis

        Args:
            value (int): New center position
            axis (int): Axis index, 0 for X, 1 for Y
        """
        current_center = list(self.center().toTuple())
        t = current_center[:]
        current_center[axis] = value
        self.moveCenter(QtCore.QPoint(*current_center))

    def store_margins(self):
        if not self.is_backdrop:
            raise NotImplementedError("Tried to calculate margins on a non-backdrop node")
        nodes = self.node.getNodes()
        nodes_bounds = get_nodes_bounds(nodes)
        margins = calculate_bounds_adjustment(nodes_bounds, self)
        self._nodes_and_margins = {'nodes': nodes, 'margins': margins}

    def restore_margins(self):
        if not self.is_backdrop:
            raise NotImplementedError("Tried to set margins on a non-backdrop node")
        if not self._nodes_and_margins:
            raise RuntimeError("No margins were saved for this backdrop, can't restore")
        nodes_bounds = get_nodes_bounds(self._nodes_and_margins['nodes'])
        nodes_bounds.adjust(*self._nodes_and_margins['margins'])
        self.setCoords(*nodes_bounds.getCoords())

    def place_around_nodes(self, nodes, padding=50):
        if not self.is_backdrop:
            raise NotImplementedError("Can only place backdrops around nodes")
        if not nodes:
            return
        label_height = get_label_size(self.node).height()
        nodes_bounds = get_nodes_bounds(nodes)
        nodes_bounds.adjust(-padding, -(padding+label_height), padding, padding)
        self.setCoords(*nodes_bounds.getCoords())


def de_intersect():
    """ Experimental: Get nodes to push each other if intersecting. """
    progress = nuke.ProgressTask('De-Intersecting Nodes')
    undo = nuke.Undo()
    undo.begin('De-Intersecting Nodes')

    candidates = nuke.selectedNodes()
    if not candidates:
        candidates = nuke.allNodes()

    try:
        speed_squared = 15*15
        nodes = [NodeWrapper(n) for n in candidates if n.Class() != 'BackdropNode']
        intersecting = True
        margins = QtCore.QMargins()
        margins += 7
        loop = 0
        max_loops = 500
        while intersecting and loop < max_loops:
            if progress.isCancelled():
                break
            loop += 1
            progress.setMessage('resolving intersections pass {}/{}(max)'.format(loop, max_loops))
            progress.setProgress(int(float(loop) / max_loops * 100))
            intersecting = False
            for node in nodes:
                for other_node in nodes:
                    if other_node is node:
                        continue
                    if node.marginsAdded(margins).intersects(other_node.bounds):
                        intersecting = True
                        offset = QtGui.QVector2D(node.center() - other_node.center())
                        if offset.isNull():
                            offset.setY(1)
                        offset = offset * (float(speed_squared) / offset.lengthSquared())
                        node.translate(offset.toPoint())
                        break  # go to the next node to avoid pingpong
    finally:
        progress.setProgress(100)
        undo.end()


