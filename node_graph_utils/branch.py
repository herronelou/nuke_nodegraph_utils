from contextlib import contextmanager
import nuke
from Qt import QtCore, QtGui

from node_graph_utils.dag import NodeWrapper, get_node_bounds, get_nodes_bounds, last_clicked_position
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

        if not start:
            start = last_clicked_position()

        # We can start a branch either from a position or a node
        if isinstance(start, nuke.Node):
            start = NodeWrapper(start)

        if isinstance(start, NodeWrapper):
            self.cursor = start.center().toPoint()
            self.move_cursor(rows=1)
            self.root = start.node
            self.leaf = start.node
            self._nodes.append(start.node)
        else:
            self.cursor = self._nearest_grid(self._to_q_point(start))

        self.trunk_branch = None
        self.sub_branches = []

    @staticmethod
    def _stepped_ceil(value, step):
        return step * (value // step + int(bool(value % step)))

    @staticmethod
    def _to_q_point(value):
        if isinstance(value, QtCore.QPoint):
            return value
        elif isinstance(value, tuple):
            return QtCore.QPoint(*value)
        elif isinstance(value, QtCore.QPointF):
            return value.toPoint()
        else:
            raise TypeError("Invalid point provided for branch. Expected tuple or QPoint.")

    def _nearest_grid(self, point):
        x = self._grid_size.width() * int(float(point.x()) / self._grid_size.width() + 0.5)
        y = self._grid_size.height() * int(float(point.y()) / self._grid_size.height() + 0.5)
        return QtCore.QPoint(x, y)

    def _add_sub_branch(self, sub_branch):
        """"""
        # If sub_branch is the trunk of this, reverse the order.
        # TODO: What to do if a branch is the sub_branch of multiple other ones? Can a branch have multiple trunks?
        if sub_branch is self.trunk_branch:
            self.trunk_branch = None
        if self in sub_branch.sub_branches:
            sub_branch.sub_branches_branche.remove(self)

        # Make self the sub_branch's trunk, and add the sub_branch to sub_branches
        sub_branch.trunk_branch = self
        if sub_branch not in self.sub_branches:
            self.sub_branches.append(sub_branch)

    # TODO: root attribute to get top root or local root?
    # TODO: Would it be useful to have an option to crawl nodes upstream of the root to add to the branch?

    def bounds(self, include_sub_branches=True):
        return get_nodes_bounds(self.nodes(include_sub_branches=include_sub_branches))

    def flattened_stack(self, stack=None):
        if stack is None:
            stack = []
        stack.append(self)
        for sub_branch in self.sub_branches:
            if sub_branch not in stack:
                sub_branch.flattened_stack(stack)
        return stack

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
        # TODO: If current branch is empty, do what?
        if not self.root:
            return
        if alignment:
            if alignment == self.ALIGN_ROOTS:
                y = int(get_node_bounds(self.root).center().y())
                other_y = int(get_node_bounds(other_branch.root).center().y())
            else:  # self.ALIGN_LEAVES
                y = int(get_node_bounds(self.leaf).center().y())
                other_y = int(get_node_bounds(other_branch.leaf).center().y())

            offset_y = y-other_y
            other_branch.translate_by((0, offset_y))
            # De-intersect
            step = 1 if other_branch.cursor.x() >= self.cursor.x() else -1

            branches_to_place = other_branch.flattened_stack()
            fixed_branches = [branch for branch in self.flattened_stack() if branch not in branches_to_place]
            columns_offset = calculate_non_colliding_column_offset(branches_to_place, fixed_branches,
                                                                   self._grid_size.width(), step)
            other_branch.translate_by((columns_offset * self._grid_size.width(), 0))

        # Sort out cursors. Cursor should be moved to the max Y of both cursors.
        cursor_y = max(self.cursor.y(), other_branch.cursor.y())
        self.cursor.setY(cursor_y)
        other_branch.cursor.setY(cursor_y)
        # Add Dot in other branch
        dot = nuke.nodes.Dot()
        other_branch.add_node(dot)
        self.add_node(merge_node)
        merge_node.setInput(merge_input, dot)
        self._add_sub_branch(other_branch)

    def append(self, other_branch):
        """"""
        other_branch.move_root_to(self.cursor)
        for node in other_branch.nodes():
            if node not in self._nodes:
                self._nodes.append(node)

        other_branch.root.setInput(0, self.leaf)
        self.leaf = other_branch.leaf
        self.cursor = other_branch.cursor
        self.move_cursor(rows=1)

    def fork(self, columns=1):
        """"""
        # TODO: add arg to make disconnected branch
        start = self.cursor
        self.add_node(nuke.nodes.Dot())

        new_branch = NodeBranch()
        new_branch.add_node(nuke.nodes.Dot())
        new_branch.root.setInput(0, self.leaf)
        new_branch.move_root_to(start + QtCore.QPoint(self._grid_size.width() * columns, 0))
        return new_branch

    def move_root_to(self, position, snap_to_grid=False, include_sub_branches=True):
        """"""
        if not self.root:
            offset = position - self.cursor
        else:
            position = self._to_q_point(position)
            offset = position - get_node_bounds(self.root).center().toPoint()
        self.translate_by(offset, snap_to_grid=snap_to_grid, include_sub_branches=include_sub_branches)

    def move_leaf_to(self, position, snap_to_grid=False, include_sub_branches=True):
        """"""
        if not self.leaf:
            offset = position - self.cursor
        else:
            position = self._to_q_point(position)
            offset = position - get_node_bounds(self.leaf).center().toPoint()
        self.translate_by(offset, snap_to_grid=snap_to_grid, include_sub_branches=include_sub_branches)

    def translate_by(self, offset, snap_to_grid=False, include_sub_branches=True):
        """"""
        offset = self._to_q_point(offset)
        if snap_to_grid:
            offset = self._nearest_grid(offset)  # TODO: Snap each node instead?
        for node in self.nodes(include_sub_branches=include_sub_branches):
            NodeWrapper(node).translate(offset)
        # Move cursor too
        self.cursor += offset

    def move_cursor(self, rows=0, columns=0):
        """"""
        self.cursor += QtCore.QPoint(self._grid_size.width() * columns, self._grid_size.height() * rows)

    def nodes(self, include_sub_branches=True):
        """"""
        if include_sub_branches:
            nodes = []
            stack = self.flattened_stack()
            for branch in stack:
                for node in branch.nodes(include_sub_branches=False):
                    if node not in nodes:
                        nodes.append(node)
        else:
            nodes = self._nodes

        return nodes

    def add_backdrop(self, label=None, include_sub_branches=True):
        """"""
        backdrop = auto_backdrop(self.nodes(include_sub_branches=include_sub_branches), text=label)
        self._nodes.append(backdrop)
        # TODO: Offset the cursor down a bit to accommodate the bottom of backdrop

    @contextmanager
    def backdrop_context(self, label=None):
        """ Only supports adding nodes """
        # TODO: Offset the cursor down a bit to accommodate the label
        nodes_at_enter = set(self._nodes)
        backdrop = nuke.nodes.BackdropNode()
        yield backdrop

        nodes_at_exit = set(self._nodes)
        added_nodes = nodes_at_exit - nodes_at_enter
        auto_backdrop(list(added_nodes), text=label, backdrop_node=backdrop)
        self._nodes.append(backdrop)


def calculate_non_colliding_column_offset(branches_to_move, branches_to_collide, column_width, direction):
    movable_rects = [branch.bounds(include_sub_branches=False) for branch in branches_to_move]
    fixed_rects = [branch.bounds(include_sub_branches=False) for branch in branches_to_collide
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


#
# class NodeFork(object):
#     """ A Horizontal line of dots. Can be used as a Branch root. Creates, moves and reconnects the dots on demand. """
#     # TODO: Moving in Y needs pushing all nodes up or down, possibly cursors too? Or up only?


# TODO: Backdrop context manager, group context manager (autostarts a new branch at input, connects output on exit?)
#  - Has a cursor, join(connection_node, join in A, autoplace), fork (allow multiple forks (fork_at(node))? forks create dots + new branch), select all
#  - check the bug again, what was it? something about sets of nodes? (yes, not like sets or list+list when in a drop data callback, so use the old append way) ID 476523
#  - move whole tree
#  - move cursor, leaf prop, root prop, roots prop? (list of roots?)
