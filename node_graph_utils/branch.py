from contextlib import contextmanager
import nuke

import math
from Qt import QtCore

from .dag import NodeWrapper, get_node_bounds, get_nodes_bounds, last_clicked_position, get_label_size
from .backdrops import auto_backdrop


class NodeBranch(object):

    NO_MOVE = 0
    ALIGN_ROOTS = 1
    ALIGN_LEAVES = 2

    @classmethod
    def from_existing_nodes(cls, nodes, root, leaf):
        branch = cls()
        branch.root = root
        branch.leaf = leaf
        branch._nodes = nodes
        wrapper = NodeWrapper(leaf)
        branch.cursor = wrapper.center().toPoint()
        branch.move_cursor(rows=1)
        return branch

    def __init__(self, start=None):

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
            self.cursor = DagGrid.nearest_grid_point(self._to_q_point(start))

        self.trunk_branch = None
        self.sub_branches = []

    def __nonzero__(self):
        return bool(self.nodes())

    def __bool__(self):
        return self.__nonzero__()

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
        wrapper = NodeWrapper(node)

        # In case the given node is backdrop, we add it in the flow and move the cursor below the backdrop.
        # This should only really be used with empty backdrops, for backdrops with nodes it's better to either use:
        # - a different branch, use that other branch's `add_backdrop` method and append the other branch to this one
        # - Use the `backdrop_context` context manager so all newly added nodes go into a backdrop.
        if not wrapper.is_backdrop:
            wrapper.moveCenter(self.cursor)
            self.move_cursor(rows=1)
        else:
            wrapper.moveCenter(self.cursor + QtCore.QPoint(0, wrapper.height() // 2))
            self.move_cursor(rows=DagGrid.convert_position_to_cells(QtCore.QPoint(*wrapper.size().toTuple())).y() + 1)

        if self.root is None:
            self.root = node

        if node.Class() in ['StickyNote', 'BackdropNode']:
            return

        if node.Class() not in ['Read']:
            node.setInput(0, self.leaf)
        self.leaf = node

    def merge(self, merge_node, other_branch, merge_input=1, alignment=NO_MOVE):
        """"""
        # TODO: If current branch is empty, do what?
        if not self.root:
            return
        if alignment:  # TODO: Refactor the alignment to own method
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
                                                                   DagGrid.width(), step)
            other_branch.translate_by((columns_offset * DagGrid.width(), 0))

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

        if other_branch:
            if other_branch.root.Class() not in ['StickyNote', 'Backdrop', 'Read']:
                # Weirdly enough, Nuke won't complain is trying to set input on these input-less nodes,
                # but will result in an odd script state.
                other_branch.root.setInput(0, self.leaf)
            self.leaf = other_branch.leaf
            self.cursor = other_branch.cursor
            # self.move_cursor(rows=1)  # Creates mismatch with forks, cursor should be already good

    def fork(self, columns=1, fork_from='leaf'):
        """"""
        # TODO: add arg to make disconnected branch
        # TODO: Option to fork from root
        # TODO: Option to tag nodes and fork from any tag?

        # If our leaf is a Dot, we use it directly as our fork node
        if not self.leaf or not self.leaf.Class() == "Dot":
            self.add_node(nuke.nodes.Dot())

        start = get_node_bounds(self.leaf).center()

        new_branch = NodeBranch()
        new_branch.add_node(nuke.nodes.Dot())
        new_branch.root.setInput(0, self.leaf)
        new_branch.move_root_to(start + QtCore.QPoint(DagGrid.width() * columns, 0))
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
            offset = DagGrid.nearest_grid_point(offset)  # TODO: Snap each node instead?
        for node in self.nodes(include_sub_branches=include_sub_branches):
            NodeWrapper(node).translate(offset)
        # Move cursor too
        self.cursor += offset

    def move_cursor(self, rows=0, columns=0):
        """"""
        self.cursor += QtCore.QPoint(DagGrid.width() * columns, DagGrid.height() * rows)

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

    def add_backdrop(self, label=None, include_sub_branches=True, **kwargs):  # TODO: Allow color attribute
        """"""
        backdrop = auto_backdrop(self.nodes(include_sub_branches=include_sub_branches), text=label, **kwargs)
        self._nodes.append(backdrop)

        # Offset the cursor to have it now under the backdrop
        wrapper = NodeWrapper(backdrop)
        offset = wrapper.bottom() - self.cursor.y()
        self.move_cursor(rows=DagGrid.convert_position_to_cells(QtCore.QPoint(0, offset)).y() + 1)

        return backdrop

    @contextmanager
    def backdrop_context(self, label=None, font_size=40, hue=None, saturation=None, brightness=None,
                         center_label=False, bold=False):
        """ Only supports adding nodes """
        nodes_at_enter = set(self._nodes)
        backdrop = nuke.nodes.BackdropNode()
        wrapper = NodeWrapper(backdrop)
        backdrop['note_font_size'].setValue(font_size)
        if label:
            backdrop['label'].setValue(label)
        # Place the node where the cursor is
        wrapper.moveCenter(self.cursor + QtCore.QPoint(0, wrapper.height() // 2))
        # Place the cursor within the backdrop, under the label
        label_height = get_label_size(backdrop).height()
        self.move_cursor(rows=DagGrid.convert_position_to_cells(QtCore.QPoint(0, label_height)).y())

        yield backdrop

        # Wrap around added nodes
        nodes_at_exit = set(self._nodes)
        added_nodes = nodes_at_exit - nodes_at_enter
        auto_backdrop(list(added_nodes), text=label, font_size=font_size, hue=hue, saturation=saturation,
                      brightness=brightness, center_label=center_label, bold=bold, backdrop_node=backdrop)

        # Put cursor under the backdrop
        wrapper.refresh()  # The autobackdrop has likely moved the backdrop without using the wrapper.
        offset = wrapper.bottom() - self.cursor.y()
        self.move_cursor(rows=DagGrid.convert_position_to_cells(QtCore.QPoint(0, offset)).y() + 1)

        self._nodes.append(backdrop)


# TODO: Need to find a system to make grid snapping not create too many odd gaps both with the regular layout and the
#  grid layout. Doing both a minimum size to grid size AND snap to grid is causing issues. Maybe it's a matter
#  of allowing one less grid when it would result in a big gap.

class BranchLayoutBase(object):
    """
    Layout which can be used to place NodeBranches relative to other NodeBranches.
    Also supports placing other BranchLayouts.
    Idea is strongly inspired by Qt Layouts.

    The `spacing` attribute can be set to define how much space should be inserted between items.
    Note that only multiples of the user's grid size will be used, with a minimum of one grid size of spacing, so this
    number should be considered more like a hint than an actual value.  TODO: Allow disabling grid
    """
    def __init__(self, items=None):
        """
        Parameters
        ----------
        items: list[NodeBranch or BranchLayoutBase]
        """
        self._items = []
        self._backdrop = None

        self.spacing = 50

        if items:
            self.add_items(items)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.do_layout()

    def add_items(self, items):
        """
        Add a multiple items to the Layout

        Parameters
        ----------
        items: Iterable
        """
        for item in items:
            self.add_item(item)

    def add_item(self, item):
        """
        Add a single item to the Layout

        Parameters
        ----------
        item: NodeBranch or BranchLayoutBase
        """
        if not isinstance(item, (NodeBranch, BranchLayoutBase)):
            raise TypeError("BranchLayout item must be BranchLayout our NodeBranch, not {}".format(type(item)))
        self._items.append(item)

    def insert_item(self, index, item):
        """
        Insert a single item to the Layout

        Parameters
        ----------
        index: int
        item: NodeBranch or BranchLayoutBase
        """
        if not isinstance(item, (NodeBranch, BranchLayoutBase)):
            raise TypeError("BranchLayout item must be BranchLayout our NodeBranch, not {}".format(type(item)))
        self._items.insert(index, item)

    def bounds(self, exclude_backdrop=False):
        """
        Calculate bounding rectangle for this layout.
        Mostly used when inserted in another Layout

        Parameters
        ----------
        exclude_backdrop: bool, optional
            If False, return the bounds of the backdrop.
            Otherwise, calculate the internal bounds.

        Returns
        -------
        QtCore.QRectF
        """
        if self._backdrop and not exclude_backdrop:
            # Return a copy of the backdrop's bounds
            return QtCore.QRectF(self._backdrop.bounds)

        # Filter empty items as they have no bounds
        items = [item for item in self._items if item]
        if not items:
            return QtCore.QRectF(0, 0, 0, 0)

        bounds = items[0].bounds()
        for item in items[1:]:
            bounds |= item.bounds()
        return bounds

    def set_backdrop(self, backdrop):
        """
        Layout can have 1 and only one dynamic backdrop node, which will dynamically grow with the layout

        Parameters
        ----------
        backdrop: nuke.BackdropNode

        Returns
        -------
        nuke.BackdropNode
        """
        if backdrop is None:
            self._backdrop = None
            return
        if not isinstance(backdrop, NodeWrapper):
            backdrop = NodeWrapper(backdrop)
        backdrop.place_around_bounds(self.bounds(exclude_backdrop=True))
        self._backdrop = backdrop
        return backdrop.node

    def translate_by(self, offset):
        """
        Move this layout and its contents by the provided offset.

        Parameters
        ----------
        offset: QtCore.QPoint
        """
        for item in self._items:
            item.translate_by(offset)
        if self._backdrop:
            self._backdrop.translate(offset)

    def do_layout(self):
        """ Organize all the items in this layout """
        raise NotImplementedError()


class BranchLayout(BranchLayoutBase):
    """
    Layout which can be used to place NodeBranches relative to other NodeBranches.
    Also supports placing other BranchLayouts.
    Idea is strongly inspired by Qt Layouts.

    For generalization, both NodeBranches and BranchLayouts are called items here, and can be added with `add_item`,
    `insert_item` and `add_items`.
    No layout is being done until `do_layout` is called (preferably once everything is created). The class can be used
    as a context manager, to ensure `do_layout` is always called at the end even when running into an error somewhere
    else in the code.

    Six different alignments are supported, with 2 different directions, for a total of 12 different possible layouts:

    Horizontal:
    Set `align` attribute to one of:  QtCore.Qt.AlignTop (default), QtCore.Qt.AlignBottom, QtCore.Qt.AlignVCenter
    Set `direction` attribute to one of: QtCore.Qt.LeftToRight (default), QtCore.Qt.RightToLeft

    Vertical:
    Set `align` attribute to one of:  QtCore.Qt.AlignLeft, QtCore.Qt.AlignRight, QtCore.Qt.AlignHCenter
    Set `direction` attribute to one of: QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft
    Note that Qt does not provide vertical layout direction flags, so the horizontal ones are reused.
    Left to Right corresponds to Top to Bottom, and Right to Left corresponds to bottom to top
    (not that it should be commonly used...)


    The `spacing` attribute can be set to define how much space should be inserted between items.
    Note that only multiples of the user's grid size will be used, with a minimum of one grid size of spacing, so this
    number should be considered more like a hint than an actual value.
    """
    def __init__(self, items=None):
        """
        Parameters
        ----------
        items: list[NodeBranch or BranchLayout]
        """
        super(BranchLayout, self).__init__(items=items)

        self.alignment = QtCore.Qt.AlignTop
        self.direction = QtCore.Qt.LeftToRight

    def _calculate_offset(self, target_bounds, source_bounds):
        """ Calculate an offset between 2 rectangles based on direction and alignment"""
        source_point = target_point = None
        if self.direction == QtCore.Qt.LeftToRight:
            # Horizontal Layout
            if self.alignment == QtCore.Qt.AlignTop:
                source_point = source_bounds.topLeft()
                target_point = target_bounds.topRight()
            elif self.alignment == QtCore.Qt.AlignBottom:
                source_point = source_bounds.bottomLeft()
                target_point = target_bounds.bottomRight()
            elif self.alignment in [QtCore.Qt.AlignCenter, QtCore.Qt.AlignVCenter]:
                source_point = QtCore.QPointF(source_bounds.left(), source_bounds.center().y())
                target_point = QtCore.QPointF(source_bounds.right(), source_bounds.center().y())
            # Vertical
            # We also consider Left To Right as Top to Bottom as that doesn't exist in Qt
            elif self.alignment == QtCore.Qt.AlignLeft:
                source_point = source_bounds.topLeft()
                target_point = target_bounds.bottomLeft()
            elif self.alignment == QtCore.Qt.AlignRight:
                source_point = source_bounds.topRight()
                target_point = target_bounds.bottomRight()
            elif self.alignment == QtCore.Qt.AlignHCenter:
                source_point = QtCore.QPointF(source_bounds.center().x(), source_bounds.top())
                target_point = QtCore.QPointF(source_bounds.center().x(), source_bounds.bottom())
        elif self.direction == QtCore.Qt.RightToLeft:
            # Horizontal
            if self.alignment == QtCore.Qt.AlignTop:
                source_point = source_bounds.topRight()
                target_point = target_bounds.topLeft()
            elif self.alignment == QtCore.Qt.AlignBottom:
                source_point = source_bounds.bottomRight()
                target_point = target_bounds.bottomLeft()
            elif self.alignment in [QtCore.Qt.AlignCenter, QtCore.Qt.AlignVCenter]:
                source_point = QtCore.QPointF(source_bounds.right(), source_bounds.center().y())
                target_point = QtCore.QPointF(source_bounds.left(), source_bounds.center().y())
            # Vertical
            # We also consider Right To Left as Bottom to Top as that doesn't exist in Qt
            elif self.alignment == QtCore.Qt.AlignLeft:
                source_point = source_bounds.bottomLeft()
                target_point = target_bounds.topRight()
            elif self.alignment == QtCore.Qt.AlignRight:
                source_point = source_bounds.bottomRight()
                target_point = target_bounds.topRight()
            elif self.alignment == QtCore.Qt.AlignHCenter:
                source_point = QtCore.QPointF(source_bounds.center().x(), source_bounds.bottom())
                target_point = QtCore.QPointF(source_bounds.center().x(), source_bounds.top())
        if target_point is None or source_point is None:
            raise ValueError("Incompatible alignment and direction arguments: {} and {}".format(self.alignment,
                                                                                                self.direction))

        # For the time being, it seems like if spacing is at least equal to the grid size, we don't run into cases
        # where the nodes collapse onto themselves. If it does happen, the solution could be to translate the bounds
        # and test for intersection, but I would rather avoid it if not necessary.
        if self.alignment in [QtCore.Qt.AlignTop, QtCore.Qt.AlignBottom, QtCore.Qt.AlignCenter, QtCore.Qt.AlignVCenter]:
            # Horizontal Spacer
            spacer = QtCore.QPoint(max(self.spacing, DagGrid.width()), 0)
        else:
            # Vertical Spacer
            spacer = QtCore.QPoint(0, max(self.spacing, DagGrid.height()))
        if self.direction == QtCore.Qt.RightToLeft:
            # Inverted direction
            spacer *= -1

        offset = (target_point + spacer) - source_point
        # Snap the offset to grid, this ensures we offset with a round grid number, thus making sure nodes created on
        # grid stay on grid
        offset = DagGrid.nearest_grid_point(offset)
        return offset

    def do_layout(self):
        """ Organize all the items in this layout """
        last_bounds = None
        for item in self._items:
            if not item:
                # Could be an empty branch
                # We could move the cursor, but really this layout is meant to
                # run after the nodes are created, so just skip
                continue
            bounds = item.bounds()
            if bounds.width() == 0:
                continue  # Skip empty bounds
            if last_bounds is not None:
                offset = self._calculate_offset(last_bounds, bounds)
                item.translate_by(offset)
                bounds.translate(offset)
            last_bounds = bounds
        if self._backdrop:
            self._backdrop.place_around_bounds(self.bounds(exclude_backdrop=True))


class GridBranchLayout(BranchLayoutBase):
    """
    Layout which can be used to place NodeBranches relative to other NodeBranches.
    Also supports placing other BranchLayouts.
    Idea is strongly inspired by Qt Layouts.

    For generalization, both NodeBranches and BranchLayouts are called items here, and can be added with `add_item`,
    `insert_item` and `add_items`.
    No layout is being done until `do_layout` is called (preferably once everything is created). The class can be used
    as a context manager, to ensure `do_layout` is always called at the end even when running into an error somewhere
    else in the code.

    This Grid layout accepts the attribute `columns` (int) to define the number of columns to fill before going to
    the next row. You cannot set a number of rows, it's calculated automatically based on the number of items and the
    number of columns.

    Grid layout only supports 2 modes:
    - Regular (`transpose` attribute set to False): Columns are vertical (so column 1 will be on the left of column 2).
    This is the default.
    For example, with 3 columns and 8 items:
    +---+---+---+
    | 1 | 2 | 3 |
    +---+---+---+
    | 4 | 5 | 6 |
    +---+---+---+
    | 7 | 8 |   |
    +---+---+---+

    - Transposed (`transpose` attribute set to False): Columns are horizontal (so column 1 will be above column 2).
    It's named "transposed" because it resembles a matrix transposition.
    For example, with 3 columns and 8 items:
    +---+---+---+
    | 1 | 4 | 7 |
    +---+---+---+
    | 2 | 5 | 8 |
    +---+---+---+
    | 3 | 6 |   |
    +---+---+---+

    The `spacing` attribute can be set to define how much space should be inserted between items.
    Note that only multiples of the user's grid size will be used, with a minimum of one grid size of spacing, so this
    number should be considered more like a hint than an actual value.
    """
    def __init__(self, items=None):
        """
        Parameters
        ----------
        items: list[NodeBranch or BranchLayout]
        """
        super(GridBranchLayout, self).__init__(items=items)

        self.columns = 5
        self.transpose = False
        self.alignment = QtCore.Qt.AlignCenter

    def _get_correct_anchor(self, bounds):
        """ Get the correct anchor point based on alignment"""
        if self.alignment & QtCore.Qt.AlignLeft:
            if self.alignment & QtCore.Qt.AlignTop:
                return bounds.topLeft()
            elif self.alignment & QtCore.Qt.AlignBottom:
                return bounds.bottomLeft()
            else:
                return QtCore.QPoint(bounds.left(), bounds.center().y())
        elif self.alignment & QtCore.Qt.AlignRight:
            if self.alignment & QtCore.Qt.AlignTop:
                return bounds.topRight()
            elif self.alignment & QtCore.Qt.AlignBottom:
                return bounds.bottomRight()
            else:
                return QtCore.QPoint(bounds.right(), bounds.center().y())
        elif self.alignment & QtCore.Qt.AlignTop:
            return QtCore.QPoint(bounds.center().x(), bounds.top())
        elif self.alignment & QtCore.Qt.AlignBottom:
            return QtCore.QPoint(bounds.center().x(), bounds.bottom())
        else:
            return bounds.center()

    def do_layout(self):
        """ Organize all the items in this layout """

        # Before we move items, we need to know the largest width and the largest height, to define our cell size
        all_bounds = []  # Store the bounds so we only calculate them once
        non_null_items = []

        max_w = 0
        max_h = 0

        for item in self._items:
            if not item:
                continue
            bounds = item.bounds()
            if bounds.width() == 0:
                continue  # Skip empty bounds

            max_w = max(max_w, bounds.width())
            max_h = max(max_h, bounds.height())

            all_bounds.append(bounds)
            non_null_items.append(item)

        if not non_null_items:
            return

        spacer_x = QtCore.QPoint(max(self.spacing, DagGrid.width()) + max_w, 0)
        spacer_y = QtCore.QPoint(0, max(self.spacing, DagGrid.height()) + max_h)
        # The first item is used as our anchor (first item doesn't move,
        # everything gets placed relative to it)
        if self.transpose:
            column_spacer = spacer_y
            row_spacer = spacer_x
        else:
            column_spacer = spacer_x
            row_spacer = spacer_y

        start = None
        for i, item in enumerate(non_null_items):
            if i == 0:
                start = self._get_correct_anchor(all_bounds[i])
                continue
            row = i // self.columns
            column = i % self.columns

            target = start + row * row_spacer + column * column_spacer
            offset = target - self._get_correct_anchor(all_bounds[i])
            # offset = DagGrid.nearest_grid_point(offset)  # TODO: Make snap work better
            item.translate_by(offset)

        if self._backdrop:
            self._backdrop.place_around_bounds(self.bounds(exclude_backdrop=True))


class DagGrid(object):
    _size = None

    @classmethod
    def size(cls):
        if cls._size is None:
            if nuke.GUI:
                prefs = nuke.toNode('preferences')
                # Set the grid size to be at least 150*48, but be a multiple of the user's grid size.
                cls._size = QtCore.QSize(cls.stepped_ceil(150, prefs['GridWidth'].value()),
                                         cls.stepped_ceil(48, prefs['GridHeight'].value()))
            else:
                # When not in GUI, nuke throws warnings when accessing preferences.
                cls._size = QtCore.QSize(150, 48)
        return cls._size

    @classmethod
    def width(cls):
        return cls.size().width()

    @classmethod
    def height(cls):
        return cls.size().height()

    @staticmethod
    def stepped_ceil(value, step):
        """
        Return the nearest value that is greater or equal to `value` while being a multiple of `step`

        Parameters
        ----------
        value: int or float
        step: int or float

        Returns
        -------
        int or float
        """
        return step * (value // step + int(bool(value % step)))

    @classmethod
    def nearest_grid_point(cls, point):
        x = cls.size().width() * int(round(float(point.x()) / cls.size().width()))
        y = cls.size().height() * int(round(float(point.y()) / cls.size().height()))
        return QtCore.QPoint(x, y)

    @classmethod
    def convert_position_to_cells(cls, point, ceil=True):
        """
         Convert a position to a number of rows and columns

        Parameters
        ----------
        point: QtCore.QPoint
        ceil: bool
            If True, use a ceiling when rounding, else use the nearest grid.

        Returns
        -------
        QtCore.QPoint
        """
        rounding_type = math.ceil if ceil else round
        x = int(rounding_type(float(point.x()) / cls.size().width()))
        y = int(rounding_type(float(point.y()) / cls.size().height()))
        return QtCore.QPoint(x, y)


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


# def line_up_branches(branches, spacing=25):
#     # TODO: Implement different directions/anchors. For now Line up left to right, with the top lined-up
#
#     if not branches:
#         return
#     # Filter out the empty branches
#     branches = [branch for branch in branches if branch]
#     if not branches:
#         return
#
#     bounds = branches[0].bounds()
#     for branch in branches[1:]:
#         b_bounds = branch.bounds()
#         before_move = b_bounds.topLeft()
#         offset = bounds.topRight() + QtCore.QPoint(spacing, 0) - before_move
#         # Snap the offset to grid, this will prevent us from having to use "snap to grid" when translating,
#         # and potentially getting a disconnect between offset branch and offset bounds.
#         offset = DagGrid.nearest_grid_point(offset)
#         # Verify we didn't snap too close
#         if (before_move + offset).x() <= bounds.topRight().x():
#             offset.setX(offset.x() + DagGrid.width())
#         b_bounds.translate(offset)
#         branch.translate_by(offset, snap_to_grid=True)
#         bounds |= b_bounds


#
# class NodeFork(object):
#     """ A Horizontal line of dots. Can be used as a Branch root. Creates, moves and reconnects the dots on demand. """
#     # TODO: Moving in Y needs pushing all nodes up or down, possibly cursors too? Or up only?


# TODO: Backdrop context manager, group context manager (autostarts a new branch at input, connects output on exit?)
#  - Has a cursor, join(connection_node, join in A, autoplace), fork (allow multiple forks (fork_at(node))? forks create dots + new branch), select all
#  - check the bug again, what was it? something about sets of nodes? (yes, not like sets or list+list when in a drop data callback, so use the old append way) ID 476523
#  - move whole tree
#  - move cursor, leaf prop, root prop, roots prop? (list of roots?)
#  - would be cool to be able to tag certain nodes when added, to allow forking from them or retrieving them later
