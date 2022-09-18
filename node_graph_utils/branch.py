from contextlib import contextmanager
import nuke
from Qt import QtCore, QtGui

from node_graph_utils.dag import NodeWrapper, get_node_bounds, get_nodes_bounds
from node_graph_utils.backdrops import auto_backdrop


class NodeBranch(object):

    NO_MOVE = 0
    ALIGN_ROOTS = 1
    ALIGN_LEAVES = 2

    def __init__(self, start=None):

        prefs = nuke.toNode('preferences')
        # Set the grid size to be at least 150*48, but be a multiple of the user's grid size.
        self._grid_size = QtCore.QSize(self._stepped_ceil(150, prefs['GridWidth'].value()),
                                       self._stepped_ceil(48, prefs['GridHeight'].value()))

        self.root = None
        self.leaf = None
        self._nodes = []

        # We can start a branch either from a position or a node
        if isinstance(start, nuke.Node):
            start = NodeWrapper(start)

        if isinstance(start, NodeWrapper):
            self.cursor = start.center()
            self.move_cursor(rows=1)
            self.root = start.node
            self.leaf = start.node
            self._nodes.append(start.node)
        elif isinstance(start, (QtCore.QPoint, QtCore.QPoint)):
            self.cursor = self._nearest_grid(start)
        elif isinstance(start, tuple):
            self.cursor = self._nearest_grid(QtCore.QPoint(*start))
        else:
            ValueError("Invalid start point provided for branch. Expected tuple, Node or QPoint")

        self.parent_branch = None
        self.children_branches = []

    @staticmethod
    def _stepped_ceil(value, step):
        return step * (value // step + int(bool(value % step)))

    def _nearest_grid(self, point):
        x = self._grid_size.width() * int(float(point.x()) / self._grid_size.width() + 0.5)
        y = self._grid_size.height() * int(float(point.y()) / self._grid_size.height() + 0.5)
        return QtCore.QPoint(x, y)

    def _add_child(self, child):
        """"""
        # If child branch is the parent of this, reverse the order.
        # TODO: What to do if a branch is the child of multiple other ones? Can a branch have multiple parents?
        if child is self.parent_branch:
            self.parent_branch = None
        if self in child.children_branches:
            child.children_branche.remove(self)

        # Make self the child's parent, and add the child to children
        child.parent_branch = self
        if child not in self.children_branches:
            self.children_branches.append(child)

    def flattened_stack(self, stack=None):
        if stack is None:
            stack = []
        stack.append(self)
        for child in self.children_branches:
            if child not in stack:
                child.flattened_stack(stack)
        return stack
        # TODO test

    def add_node(self, node):
        """"""
        self._nodes.append(node)
        node.setInput(0, self.leaf)
        wrapper = NodeWrapper(node)
        wrapper.moveCenter(self.cursor)
        self.move_cursor(rows=1)
        if self.root is None:
            self.root = node
        self.leaf = node

    def merge(self, merge_node, other_branch, merge_input=1, alignment=NO_MOVE):
        """"""
        # TODO Sort out alignment first
        if alignment:
            if alignment == self.ALIGN_ROOTS:
                y = int(get_node_bounds(self.root).center().y())
            else:  # self.ALIGN_LEAVES
                y = int(get_node_bounds(self.leaf).center().y())
            step = 1 if other_branch.cursor.x() > self.cursor.x() else -1
            # TODO: Flatten stack of other branch, flatten stack of this, but exclude the ones already in other stack, then get the bounding rectangles for all the branches, and iterate collisions
            branches_to_place = other_branch.flattened_stack()
            fixed_branches = [branch for branch in self.flattened_stack() if branch not in branches_to_place]
            columns_to_move = calculate_non_colliding_column_offset(branches_to_place, fixed_branches,
                                                                    self._grid_size.width(), step)


        # Sort out cursors. Cursor should be moved to the max Y of both cursors.
        self.cursor.setY(max(self.cursor.y(), other_branch.cursor.y()))
        # Add Dot in other branch
        dot = nuke.nodes.Dot()
        other_branch.add_node(dot)
        self.add_node(merge_node)
        merge_node.setInput(merge_input, dot)
        self._add_child(other_branch)


    def fork(self, label):
        """"""

    def move_root_to(self, position):
        """"""

    def move_leaf_to(self, position):
        """"""

    def translate_by(self, offset):
        """"""

    def move_cursor(self, rows=0, columns=0):
        """"""
        self.cursor += QtCore.QPoint(self._grid_size.width() * columns, self._grid_size.height() * rows)

    def nodes(self, include_children=True):
        """"""

    def add_backdrop(self, include_children=True):
        """"""

    @contextmanager
    def backdrop_context(self, label=None):
        """ Only supports adding nodes """
        # TODO: Offset the cursor down a bit to accomodate the label
        nodes_at_enter = set(self._nodes)
        backdrop = nuke.nodes.BackdropNode()
        yield backdrop

        nodes_at_exit = set(self._nodes)
        added_nodes = nodes_at_exit - nodes_at_enter
        auto_backdrop(list(added_nodes), text=label, backdrop_node=backdrop)
        self._nodes.append(backdrop)


def calculate_non_colliding_column_offset(branches_to_move, branches_to_collide, column_width, direction):
    movable_rects = [get_nodes_bounds(branch.nodes(include_children=False)) for branch in branches_to_move]
    fixed_rects = [get_nodes_bounds(branch.nodes(include_children=False)) for branch in branches_to_collide
                   if branch not in branches_to_move]
    columns = 0
    collides = True
    while collides:
        collides = False
        for i in movable_rects:
            if collides:
                break  # No need to continue if we collide already
            for j in fixed_rects:
                if i.intersects(j):
                    collides = True
                    break
        if collides:
            columns += 1
            for rect in movable_rects:
                rect.translate(column_width*direction, 0)
    return columns * direction



class NodeFork(object):
    """ A Horizontal line of dots. Can be used as a Branch root. Creates, moves and reconnects the dots on demand. """
    # TODO: Moving in Y needs pushing all nodes up or down, possibly cursors too? Or up only?


# TODO: Backdrop context manager, group context manager (autostarts a new branch at input, connects output on exit?)
#  - Has a cursor, join(connection_node, join in A, autoplace), fork (allow multiple forks (fork_at(node))? forks create dots + new branch), select all
#  - check the bug again, what was it? something about sets of nodes? (yes, not like sets or list+list when in a drop data callback, so use the old append way) ID 476523
#  - move whole tree
#  - move cursor, leaf prop, root prop, roots prop? (list of roots?)
