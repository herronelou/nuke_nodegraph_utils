"""
Mini Dialog to re-label nodes on the fly

Based on:
http://www.nukepedia.com/python/nodegraph/ku_labler
"""

import nuke
from PySide2 import QtWidgets, QtGui, QtCore


class Labeller(QtWidgets.QDialog):
    def __init__(self):
        super(Labeller, self).__init__()
        self.nodes = []

        self.text_edit = QtWidgets.QTextEdit()
        title = QtWidgets.QLabel("<b>Set Label</b>")
        title.setAlignment(QtCore.Qt.AlignHCenter)

        help = QtWidgets.QLabel('<span style=" font-size:7pt; color:green;">'
                                'Enter to confirm, Ctrl+Enter for new line'
                                '</span>')
        help.setAlignment(QtCore.Qt.AlignRight)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.text_edit)
        layout.addWidget(help)
        self.setLayout(layout)
        self.resize(200, 200)
        self.setWindowTitle("Set Label")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Popup)

        self.text_edit.installEventFilter(self)

    def eventFilter(self, widget, event):
        if isinstance(event, QtGui.QKeyEvent):
            if event.key() == QtCore.Qt.Key_Return and not event.modifiers():
                # change label with enter-key is pressed
                new_label = self.text_edit.toPlainText()
                for n in self.nodes:
                    n['label'].setValue(new_label)
                self.close()
                self.nodes = []
                return True
        return False

    def get_current_label(self):
        """ Return the current label if all nodes have the same one """
        first_label = self.nodes[0]['label'].value()
        for node in self.nodes[1:]:
            if node['label'].value() != first_label:
                return ''
        return first_label

    def run(self):
        """ rerun instance"""
        self.nodes = nuke.selectedNodes()
        if not self.nodes:
            return
        cursor = QtGui.QCursor.pos()
        avail_space = QtWidgets.QApplication.instance().screenAt(cursor).availableGeometry()
        posx = min(max(cursor.x()-100, avail_space.left()), avail_space.right()-200)
        posy = min(max(cursor.y()-12, avail_space.top()), avail_space.bottom()-200)
        self.move(QtCore.QPoint(posx, posy))
        self.raise_()
        self.text_edit.setFocus()
        self.text_edit.setText(self.get_current_label())
        self.text_edit.selectAll()
        self.show()
