import nuke
from Qt import QtCore, QtGui, QtWidgets

from node_graph_utils.dag import (get_current_dag, get_node_bounds,
                                  get_dag_node, node_center)


class Connection(object):
    def __init__(self, line, node, input):
        self.line = line
        self.node = node
        self.input = input

    def intersects(self, line):
        # QLineF.intersect will be deprecated in Qt 5.16+
        linef = QtCore.QLineF(line)
        intersection_type, _point = linef.intersect(self.line)
        return intersection_type == linef.BoundedIntersection

    def cut(self):
        self.node.setInput(self.input, None)


class SnippingWidget(QtWidgets.QWidget):

    def __init__(self, dag_widget):
        super(SnippingWidget, self).__init__(parent=dag_widget)

        # Group context
        self.dag_node = get_dag_node(self.parent())  # 'dag_widget', but it's garbage collected..

        # Make Widget transparent
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        # Enable mouse tracking so we can get move move events
        # self.setMouseTracking(True)

        # Overlay it with the DAG exactly
        dag_rect = dag_widget.geometry()
        dag_rect.moveTopLeft(dag_widget.parentWidget().mapToGlobal(dag_rect.topLeft()))
        self.setGeometry(dag_rect)

        # Attributes
        self.image = QtGui.QImage(dag_rect.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        self.nodes_image = QtGui.QImage(dag_rect.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        self.drawing = False
        self.last_pos = None

        local_rect = self.geometry()
        local_rect.moveTopLeft(QtCore.QPoint(0, 0))
        with self.dag_node:
            scale = nuke.zoom()
            offset = QtCore.QPoint(self.width()/2, self.height()/2) / scale - QtCore.QPoint(*nuke.center())
        self.transform = QtGui.QTransform()
        self.transform.scale(scale, scale)
        self.transform.translate(offset.x(), offset.y())

        self.connections = self.get_all_connections()
        self.cut_connections = []

    def paintEvent(self, event):
        """ Draw The widget """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = event.rect()

        # Draw the bounds rectangle
        black_pen = QtGui.QPen()
        black_pen.setColor(QtGui.QColor('red'))
        black_pen.setWidth(3)
        black_pen.setCosmetic(True)
        painter.setPen(black_pen)

        painter.drawRect(rect)

        for connection in self.cut_connections:
            painter.drawLine(connection.line)

        painter.setCompositionMode(painter.CompositionMode_DestinationOut)
        painter.drawImage(rect, self.nodes_image, rect)

        painter.setCompositionMode(painter.CompositionMode_SourceOver)
        painter.drawImage(rect, self.image, rect)

    def get_all_connections(self):
        """ Get all connections and draw the nodes"""
        painter = QtGui.QPainter(self.nodes_image)
        my_pen_color = QtGui.QColor('black')
        painter.setBrush(
            QtGui.QBrush(my_pen_color, QtCore.Qt.SolidPattern))

        all_connections = []
        for node in nuke.allNodes():
            if node.Class() in ['BackdropNode']:
                continue
            dependencies = node.dependencies(nuke.INPUTS)
            rect = get_node_bounds(node)
            painter.drawRect(self.transform.mapRect(rect))
            for i in range(node.inputs()):
                input_node = node.input(i)
                if input_node and input_node in dependencies:
                    line = QtCore.QLineF(rect.center(),
                                         QtCore.QPoint(*node_center(input_node)))
                    c = Connection(self.transform.map(line), node, i)
                    all_connections.append(c)
        return all_connections

    def start_drawing(self, pos):
        self.drawing = True
        self.last_pos = pos

    def stop_drawing(self):
        self.drawing = False
        self.last_pos = None

    def draw_segment(self, pos):
        painter = QtGui.QPainter(self.image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        my_pen_color = QtGui.QColor('white')
        my_pen_width = 2
        painter.setPen(QtGui.QPen(my_pen_color, my_pen_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        line = QtCore.QLine(self.last_pos, pos)
        painter.drawLine(line)

        about_to_cut = []
        for connection in self.connections:
            if connection.intersects(line):
                about_to_cut.append(connection)
        for connection in about_to_cut:
            self.connections.remove(connection)
        self.cut_connections.extend(about_to_cut)

        self.last_pos = pos
        self.update()

    def eventFilter(self, widget, event):
        """ Filter all the events happening while the bounding box controller is shown """
        if event.type() in [QtCore.QEvent.MouseButtonPress]:
            if not self.geometry().contains(event.globalPos()):
                # Clicked outside the widget
                self.close()
                return False

            if event.button() == QtCore.Qt.LeftButton:
                # Clicked on one of the opaque areas of the widget
                self.start_drawing(event.pos())
                return True

            # Any other click we bail
            self.close()
            return False

        elif event.type() in [QtCore.QEvent.MouseButtonRelease]:
            if event.button() == QtCore.Qt.LeftButton:
                self.stop_drawing()
                return True

        elif event.type() in [QtCore.QEvent.MouseMove]:
            # Mouse moved, if we had a handle grabbed, resize nodes.
            if self.drawing:
                self.draw_segment(event.pos())
                return True

        elif event.type() == QtCore.QEvent.KeyRelease:
            if event.isAutoRepeat():
                return True
            self.close()
            return True

        elif event.type() == QtCore.QEvent.KeyPress:
            if event.isAutoRepeat():
                return True

        return False  # Swallow everything

    def show(self):
        super(SnippingWidget, self).show()
        # Install Event filter
        QtWidgets.QApplication.instance().installEventFilter(self)

    def close(self):
        if self.cut_connections:
            undo = nuke.Undo()
            undo.begin('Snip Connections')
            try:
                for connection in self.cut_connections:
                    connection.cut()
            finally:
                undo.end()
        QtWidgets.QApplication.instance().removeEventFilter(self)
        super(SnippingWidget, self).close()


def snip():
    this_dag = get_current_dag()
    global scale_tree_widget
    scale_tree_widget = SnippingWidget(this_dag)
    scale_tree_widget.show()


nuke.menu('Nuke').menu('Edit').addCommand('Snip', snip, 'y', shortcutContext=2)
