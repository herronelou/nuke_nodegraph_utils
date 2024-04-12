""" Backdrop utilities """

# nuke
import nuke
from Qt import QtWidgets

from .colors import random_colour, rgba_float_to_dec
from .dag import NodeWrapper


# Backdrops
class BackdropDialog(QtWidgets.QDialog):

    presets = {
        'Despill': {'label': 'DESPILL', 'hue': 0.105, 'saturation': 0.15},
        'Denoise': {'label': 'DENOISE', 'saturation': 0},
        'Key:blue': {'label': 'KEY', 'hue': 0.57, 'saturation': 1},
        'Key:green': {'label': 'KEY', 'hue': 0.33, 'saturation': 0.8},
        'Paint': {'label': 'PAINT', 'hue': 0.8, 'saturation': 1},
        'Prep': {'label': 'PREP', 'hue': 0.8, 'saturation': 1},
        'Roto': {'label': 'ROTO', 'hue': 0.57, 'saturation': .3},
    }

    def __init__(self, parent=None):
        super(BackdropDialog, self).__init__(parent=parent)

        # Knobs
        self.label = QtWidgets.QComboBox()
        self.label.setEditable(True)  # Allow typing
        self.label.setInsertPolicy(self.label.InsertAtTop)  # Add typed entries to the top

        self.label.addItem('')
        for preset in self.presets:
            self.label.addItem(preset)

        self.centered = QtWidgets.QCheckBox("Center Label")
        self.centered.setChecked(True)

        # Create the button box
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        # Make a layout
        layout = QtWidgets.QVBoxLayout()
        form = QtWidgets.QFormLayout()
        form.addRow('Label', self.label)
        form.addWidget(self.centered)
        layout.addLayout(form)
        layout.addWidget(button_box)
        self.setLayout(layout)

        # Connect Signals
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def make_backdrop(self):
        label = self.label.currentText()

        text = label
        hue = saturation = None
        center = self.centered.isChecked()
        if label in self.presets:
            settings = self.presets[label]
            text = settings.get('label', text)
            hue = settings.get('hue')
            saturation = settings.get('saturation')
        bd = auto_backdrop(text=text, hue=hue, saturation=saturation, center_label=center)
        if bd:
            bd.setSelected(True)


def auto_backdrop_dialog():
    dialog = BackdropDialog(parent=QtWidgets.QApplication.activeWindow())
    accepted = dialog.exec_()
    if accepted:
        dialog.make_backdrop()


def auto_backdrop(nodes=None, padding=50, font_size=40, text=None, center_label=False, bold=False,
                  hue=None, saturation=None, brightness=None, backdrop_node=None):
    """
    Automatically puts a backdrop behind the provided/selected nodes.

    Args:
        nodes (list[nuke.Node]): Nuke nodes to create a backdrop for
        padding(int): Add padding around the nodes (default 50px)
        font_size (int): Size for the label (default 40px)
        text (str): Label for the backdrop. Will prompt user if None
        center_label (bool): If True, label text will be centered, via html tags
        bold (bool): If true, Text label will be bold, via html tags.
        hue (float): Color Hue for the backdrop, optional
        saturation (float): Saturation of the backdrop color, optional
        brightness (float): Brightness of the backdrop color, optional
        backdrop_node (nuke.Node): Optionally pass an existing backdrop node which
            will be re-used as the auto-backdrop.

    Returns:
        nuke.Node: Created backdrop node
    """
    if nodes is None:
        nodes = nuke.selectedNodes()
        if not nodes:
            nuke.message('no nodes are selected')
            return None

    backdrop = NodeWrapper(backdrop_node or nuke.nodes.BackdropNode())
    backdrop.node['note_font_size'].setValue(font_size)
    if text:
        formatted_text = text
        if bold:
            formatted_text = '<b>{}</b>'.format(formatted_text)
        if center_label:
            formatted_text = '<center>{}</center>'.format(formatted_text)
        backdrop.node['label'].setValue(formatted_text)
        if len(text) <= 64:
            try:
                backdrop.node.setName('Backdrop_{}'.format(text))
            except ValueError:
                pass  # Illegal for a name, we keep default name

    # Calculate bounds for the backdrop node.
    backdrop.place_around_nodes(nodes, padding=padding)

    # Define Z Order
    z_order = 0
    selected_backdrop_nodes = [n for n in nodes if n.Class() == 'BackdropNode']
    # if there are backdropNodes in our list put the new one immediately behind the farthest one
    if selected_backdrop_nodes:
        z_order = min([node['z_order'].value() for node in selected_backdrop_nodes]) - 1
    else:
        # otherwise, (no backdrop in selection) find the nearest backdrop if exists and set the new one in front of it
        # add 3 so that it has 2 empty spots in between
        other_backdrops = [NodeWrapper(bd) for bd in nuke.allNodes('BackdropNode') if bd not in nodes]
        for other_backdrop in other_backdrops:
            if other_backdrop is backdrop:
                continue
            if backdrop.intersects(other_backdrop.bounds):
                z_order = max(z_order, other_backdrop.node['z_order'].value() + 3)

    # Define color
    if brightness is None:
        brightness = 0.5 if z_order % 2 == 0 else 0.35
    if saturation is None:
        saturation = 0.2

    # TODO: Use label as a seed for colors? Or categories with presets? Or use the nodes to guess?
    backdrop.node['tile_color'].setValue(rgba_float_to_dec(*random_colour(hue, saturation, brightness)))
    backdrop.node['z_order'].setValue(z_order)

    return backdrop.node


def auto_layer_backdrops():
    backdrop_nodes = sorted(nuke.allNodes('BackdropNode'),
                            key=lambda bd: bd['bdheight'].value() * bd['bdwidth'].value(),
                            reverse=True)

    current_index = 0
    for backdrop in backdrop_nodes:
        # As we have some logic in auto_backdrops to make light or dark backdrops based on odd/even numbers,
        # we keep track of the original value and assign a new z_order based on it
        increment = 2 - (backdrop['z_order'].value() - current_index) % 2
        current_index += increment
        backdrop['z_order'].setValue(current_index)


def snap_backdrops_to_contents():
    nodes = nuke.selectedNodes('BackdropNode')
    if not nodes:
        nodes = nuke.allNodes('BackdropNode')

    backdrops = [NodeWrapper(n)for n in nodes]

    backdrops = sorted(backdrops, key=lambda bd: bd.node['z_order'].value(), reverse=True)

    for backdrop in backdrops:
        backdrop.place_around_nodes(backdrop.node.getNodes(), 50)
