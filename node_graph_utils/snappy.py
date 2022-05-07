import nuke
from Qt import QtCore, QtGui, QtWidgets

from node_graph_utils.dag import (get_current_dag, clear_selection,
                                  get_dag_node, NodeWrapper)


# TODO: This is almost the same class as Snippy, refactor to use a common base. Maybe scale widget too?
class ConnectWidget(QtWidgets.QWidget):

    def __init__(self, dag_widget):
        super(ConnectWidget, self).__init__(parent=dag_widget)

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
        self.drawing = False
        self.last_pos = None

        self.all_nodes = [NodeWrapper(n) for n in nuke.allNodes() if n.maxInputs()]
        self.nodes_to_connect = []
        self.stacks = []
        clear_selection()

        local_rect = self.geometry()
        local_rect.moveTopLeft(QtCore.QPoint(0, 0))
        with self.dag_node:
            scale = nuke.zoom()
            offset = QtCore.QPoint(self.width()/2, self.height()/2) / scale - QtCore.QPoint(*nuke.center())
        transform = QtGui.QTransform()
        transform.scale(scale, scale)
        transform.translate(offset.x(), offset.y())
        self.transform, _successful = transform.inverted()

    def paintEvent(self, event):
        """ Draw The widget """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = event.rect()

        # Draw the bounds rectangle
        black_pen = QtGui.QPen()
        black_pen.setColor(QtGui.QColor('green'))
        black_pen.setWidth(3)
        black_pen.setCosmetic(True)
        painter.setPen(black_pen)

        painter.drawRect(rect)

        painter.drawImage(rect, self.image, rect)

    def start_drawing(self, pos):
        self.drawing = True
        self.last_pos = pos
        self.nodes_to_connect = []
        self.stacks.append(self.nodes_to_connect)

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

        intersecting_nodes = []
        for node in self.all_nodes:
            if node.contains(self.transform.map(pos)):
                node.setSelected(True)
                intersecting_nodes.append(node)
        for node in intersecting_nodes:
            self.nodes_to_connect.append(node)
            self.all_nodes.remove(node)

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
        super(ConnectWidget, self).show()
        # Install Event filter
        QtWidgets.QApplication.instance().installEventFilter(self)

    def close(self):
        try:
            if self.stacks:
                undo = nuke.Undo()
                undo.begin('Draw Connections')
                try:
                    for nodes_to_connect in self.stacks:
                        if len(nodes_to_connect) > 1:
                            # Extract the nuke nodes:
                            nodes = [n.node for n in nodes_to_connect]
                            # Do 2 passes, first disconnect, then reconnect. In certain cases a circular dependency
                            #   blocks the connection from happening, disconnecting helps, but not 100%.
                            for node in nodes:
                                if node.input(0) in nodes:
                                    node.setInput(0, None)
                            for i, node in enumerate(nodes[1:]):
                                node.setInput(0, nodes[i])
                finally:
                    undo.end()
        finally:
            QtWidgets.QApplication.instance().removeEventFilter(self)
            super(ConnectWidget, self).close()


def snap():
    this_dag = get_current_dag()
    global snappy_widget
    snappy_widget = ConnectWidget(this_dag)
    snappy_widget.show()


nuke.menu('Nuke').menu('Edit').addCommand('Snap', snap, 'u', shortcutContext=2)
