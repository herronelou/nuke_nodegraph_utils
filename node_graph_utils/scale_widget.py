import nuke
from PySide2 import QtCore, QtGui, QtWidgets, QtOpenGL

from node_graph_utils.dag import (get_nodes_bounds, get_dag_widgets,
                                  NodeWrapper, get_dag_node, calculate_bounds_adjustment)


class ScaleWidget(QtWidgets.QWidget):
    class _VectorWrapper(object):
        def __init__(self, node, bounds, corner=None):
            """
            Store a NodeWrapper and its relative position to the bounds for simplified manipulation.

            :param dag_utils.dag.NodeWrapper node:
            :param QtCore.QRectF bounds: bounds to calculating relative position to
            :param int corner: (Optional)
            """
            def _clamp(v):
                """ Clamp vector between 0 and 1 """
                return QtGui.QVector2D(0 if v.x() < 0 else 1 if v.x() > 1 else v.x(),
                                       0 if v.y() < 0 else 1 if v.y() > 1 else v.y())
            self.node_wrapper = node
            self.corner = corner
            self.original_point = self.get_point()
            # Store the corner coordinates relative to the bounds, saves us from calculating it in event loop
            bs = QtGui.QVector2D(bounds.size().width(), bounds.size().height())  # bounds size
            vector = (QtGui.QVector2D(self.get_point()) - QtGui.QVector2D(bounds.topLeft())) / bs
            self.vector = _clamp(vector)
            self.offset = (vector - self.vector) * bs

        def get_point(self):
            """ Return QPoint corresponding to one of the 4 corners or the center of the node """
            if self.corner is None:
                return self.node_wrapper.center()
            elif self.corner == 0:
                return self.node_wrapper.topLeft()
            elif self.corner == 1:
                return self.node_wrapper.topRight()
            elif self.corner == 2:
                return self.node_wrapper.bottomRight()
            return self.node_wrapper.bottomLeft()

        def move(self, new_point, grid_size=None):
            """ Apply the transformation to the node """
            if grid_size:
                new_point = self._snap_to_grid(new_point, grid_size)
            if self.corner is None:
                self.node_wrapper.moveCenter(new_point)
            elif self.corner == 0:
                self.node_wrapper.setTopLeft(new_point)
            elif self.corner == 1:
                self.node_wrapper.setTopRight(new_point)
            elif self.corner == 2:
                self.node_wrapper.setBottomRight(new_point)
            else:
                self.node_wrapper.setBottomLeft(new_point)
                self.node_wrapper.normalize()  # We've moved all corners, normalize the backdrop

        def _snap_to_grid(self, new_point, grid_size):
            old = QtGui.QVector2D(self.original_point)
            new = QtGui.QVector2D(new_point)
            offset = (new - old) / grid_size
            return (old + QtGui.QVector2D(offset.toPoint()) * grid_size).toPoint()

    handles_cursors = (QtCore.Qt.SizeFDiagCursor,
                       QtCore.Qt.SizeVerCursor,
                       QtCore.Qt.SizeBDiagCursor,
                       QtCore.Qt.SizeHorCursor)

    def __init__(self, dag_widget):
        super(ScaleWidget, self).__init__(parent=dag_widget)

        # Group context
        self.dag_node = get_dag_node(self.parent())  # 'dag_widget', but it's garbage collected..

        # Make Widget transparent
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        # Enable mouse tracking so we can get move move events
        self.setMouseTracking(True)

        # Overlay it with the DAG exactly
        dag_rect = dag_widget.geometry()
        dag_rect.moveTopLeft(dag_widget.parentWidget().mapToGlobal(dag_rect.topLeft()))
        self.setGeometry(dag_rect)

        # Attributes
        self.transform = None
        self.grabbed_handle = None
        with self.dag_node:
            self.nodes = nuke.selectedNodes()
        self.bounds = get_nodes_bounds(self.nodes, center_only=True)
        visual_bounds = get_nodes_bounds(self.nodes) + (QtCore.QMargins() + 10)
        adjustment = calculate_bounds_adjustment(self.bounds, visual_bounds)
        self.margins = QtCore.QMargins(adjustment[0] * -1, adjustment[1] * -1, adjustment[2], adjustment[3])
        self.coordinates = self.store_coordinates()
        self.undo = None

        self.translate_mode = False
        self.move_all = False
        prefs = nuke.toNode('preferences')

        self.snap_to_grid = prefs['SnapToGrid'].value()
        self.grid_size = QtGui.QVector2D(max(prefs['GridWidth'].value(), 1),
                                         max(prefs['GridHeight'].value(), 1))

    def store_coordinates(self):
        """ Get the coordinates of all nodes and store them in a VectorWrapper """
        all_coords = []
        with self.dag_node:
            for node in nuke.allNodes():
                node_wrapper = NodeWrapper(node)
                if node_wrapper.is_backdrop:
                    all_coords += [self._VectorWrapper(node_wrapper, self.bounds, corner) for corner in range(4)]
                else:
                    all_coords.append(self._VectorWrapper(node_wrapper, self.bounds))
        return all_coords

    def reset_state(self):
        """ Re-grab the coordinates of all the nodes """
        self.grabbed_handle = None
        self.coordinates = self.store_coordinates()

    def paintEvent(self, event):
        """ Draw The widget """
        painter = QtGui.QPainter(self)
        painter.save()

        # Calculate the proper place to draw the stuff
        local_rect = self.geometry()
        local_rect.moveTopLeft(QtCore.QPoint(0, 0))
        with self.dag_node:
            scale = nuke.zoom()
            offset = local_rect.center()/scale - QtCore.QPoint(*nuke.center())
        painter.scale(scale, scale)
        painter.translate(offset)
        self.transform = painter.combinedTransform()

        # Draw the bounds rectangle
        black_pen = QtGui.QPen()
        black_pen.setColor(QtGui.QColor('black'))
        black_pen.setWidth(3)
        black_pen.setCosmetic(True)

        painter.setPen(black_pen)
        painter.drawRect(self.bounds.marginsAdded(self.margins))

        # Draw the handles
        yellow_brush = QtGui.QBrush()
        yellow_brush.setColor(QtGui.QColor('yellow'))
        yellow_brush.setStyle(QtCore.Qt.SolidPattern)

        handle_size = int(16/scale)
        handle = QtCore.QRectF(0, 0, handle_size, handle_size)
        painter.setBrush(yellow_brush)
        for point in self.get_handles_points():
            handle.moveCenter(point)
            painter.drawRect(handle)

        # Add a text hint for usage
        painter.restore()
        local_rect.setTop(local_rect.bottom() - 70)
        text = 'Resize Mode enabled'
        if self.snap_to_grid:
            text += ' (Snap to Grid: ON)'
        text += "\nDrag any handle to affect the spacing between your nodes."
        text += "\nCtrl+Drag: affect all nodes, Shift+Drag: Translate, 'S': Toggle Snap to grid, 'Esc': Cancel, "
        text += "Any other key: Confirm and close"
        painter.setPen(black_pen)
        painter.drawText(local_rect,  QtCore.Qt.AlignCenter, text)
        painter.setPen(QtGui.QPen(QtGui.QColor('white')))
        painter.drawText(local_rect.translated(1, -1), QtCore.Qt.AlignCenter, text)

    def get_handles_points(self):
        """ Return a list of 8 QPoints representing the 8 handles we want to draw """
        bounds = self.bounds.marginsAdded(self.margins)
        return [
            bounds.topLeft(),
            QtCore.QPoint(bounds.center().x(), bounds.top()),
            bounds.topRight(),
            QtCore.QPoint(bounds.right(), bounds.center().y()),
            bounds.bottomRight(),
            QtCore.QPoint(bounds.center().x(), bounds.bottom()),
            bounds.bottomLeft(),
            QtCore.QPoint(bounds.left(),bounds.center().y())
        ]

    def get_handle_at_pos(self, pos):
        """ Get the handle nearest the provided position """
        handles = self.get_handles_points()
        nearest = (0, None)  # index, distance
        for i, handle in enumerate(handles):
            transformed = self.transform.map(handle)
            transformed -= pos
            dist = transformed.manhattanLength()
            if nearest[1] is None or dist < nearest[1]:
                nearest = (i, dist)
        return nearest[0]

    def resize_bounds(self, handle, pos):
        """ Resize the QRectF representing the bounding box controller based on the clicked handle """
        if handle is None:
            return
        # As the user interacts with the visual bounds rather than the computed ones, we need to take this into account
        bounds = self.bounds.marginsAdded(self.margins)
        invert_matrix, _invert_success = self.transform.inverted()
        pos = invert_matrix.map(pos)
        attr_prefix = 'move' if self.translate_mode else 'set'
        if handle == 0:
            getattr(bounds, '{}TopLeft'.format(attr_prefix))(pos)
        elif handle == 1:
            getattr(bounds, '{}Top'.format(attr_prefix))(pos.y())
        elif handle == 2:
            getattr(bounds, '{}TopRight'.format(attr_prefix))(pos)
        elif handle == 3:
            getattr(bounds, '{}Right'.format(attr_prefix))(pos.x())
        elif handle == 4:
            getattr(bounds, '{}BottomRight'.format(attr_prefix))(pos)
        elif handle == 5:
            getattr(bounds, '{}Bottom'.format(attr_prefix))(pos.y())
        elif handle == 6:
            getattr(bounds, '{}BottomLeft'.format(attr_prefix))(pos)
        elif handle == 7:
            getattr(bounds, '{}Left'.format(attr_prefix))(pos.x())
        self.bounds = bounds.marginsRemoved(self.margins)
        self.repaint()

    def scale_nodes(self, handle, pos, all_nodes=False):
        """ Moves either the selected nodes or all the nodes to their relative space to the bounding box controller """
        if not self.undo:
            # Start undo stack so that the operation can be reverted cleanly
            self.undo = nuke.Undo()
            self.undo.begin('Scale Nodes')

        self.resize_bounds(handle, pos)
        new_size = QtGui.QVector2D(self.bounds.size().width(), self.bounds.size().height())
        new_top_left = QtGui.QVector2D(self.bounds.topLeft())

        for coord in self.coordinates:
            if not all_nodes and coord.node_wrapper.node not in self.nodes:
                continue
            new_relative_pos = coord.vector * new_size
            new_pos = new_top_left + new_relative_pos + coord.offset
            coord.move(new_pos.toPoint(), self.grid_size if self.snap_to_grid else None)

    def mouseMoveEvent(self, event):
        """ Check which handle is nearest the mouse and set the appropriate cursor """
        if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
            self.setCursor(QtCore.Qt.SizeAllCursor)
        else:
            handle_index = self.get_handle_at_pos(event.pos())
            self.setCursor(self.handles_cursors[handle_index % 4])

    def eventFilter(self, widget, event):
        """ Filter all the events happening while the bounding box controller is shown """
        if event.type() in [QtCore.QEvent.MouseButtonPress]:
            if not self.geometry().contains(event.globalPos()):
                # Clicked outside the widget
                self.close()
                return False

            if event.button() == QtCore.Qt.LeftButton:
                if widget is self:
                    # Clicked on one of the opaque areas of the widget
                    self.grabbed_handle = self.get_handle_at_pos(event.pos())
                    self.move_all = bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier)
                    self.translate_mode = bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier)
                    return True

                # Left mouse button was clicked, outside the widget.
                if not QtWidgets.QApplication.keyboardModifiers() and event.buttons() == event.button():
                    # The mouse press event had no other button pressed at the same time
                    # However, events can happen on other widgets, so check click position
                    if isinstance(widget, QtOpenGL.QGLWidget):
                        self.close()
                    return False

        elif event.type() in [QtCore.QEvent.MouseButtonRelease]:
            if event.button() == QtCore.Qt.LeftButton and widget is self:
                self.reset_state()
                return True

        elif event.type() in [QtCore.QEvent.MouseMove]:
            # Mouse moved, if we had a handle grabbed, resize nodes.
            if self.grabbed_handle is not None:
                self.scale_nodes(self.grabbed_handle, event.pos(), all_nodes=self.move_all)
                return True

            # Otherwise, if a button is pressed, we might be moving the dag, so repaint.
            if event.buttons():
                self.repaint()

        elif event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Escape:
                self.cancel()
            elif event.key() == QtCore.Qt.Key_S:
                # toggle snap to grid
                self.snap_to_grid = not self.snap_to_grid
                self.repaint()
            # close and accept on any non modifier key
            elif event.key() not in [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift]:
                self.close()

            return True

        # Due to a QT bug, out transparent widget is swallowing wheel events, pass them back to DAG
        # See https://bugreports.qt.io/browse/QTBUG-53418
        elif event.type() == QtCore.QEvent.Wheel and widget is self:
            dag = get_dag_widgets()[0]
            gl_widget = dag.findChild(QtOpenGL.QGLWidget)
            if gl_widget:
                QtWidgets.QApplication.sendEvent(gl_widget, event)
                self.repaint()
                return True

        return False

    def show(self):
        if len(self.nodes) < 2:
            # self.restore_context()
            return
        # self.dag_node.begin()
        super(ScaleWidget, self).show()
        # Install Event filter
        QtWidgets.QApplication.instance().installEventFilter(self)

    def cancel(self):
        if self.undo:
            self.undo.cancel()
            self.undo = None
        self.close()

    # def restore_context(self):
    #     print '(end)'
    #     self.dag_node.end()
    #     # self.original_context.begin()

    def close(self):
        if self.undo:
            self.undo.end()
        # self.restore_context()
        QtWidgets.QApplication.instance().removeEventFilter(self)
        super(ScaleWidget, self).close()



