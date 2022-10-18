""" Backdrop utilities """

# nuke
import nuke

from node_graph_utils.colors import random_colour, rgba_float_to_dec
from node_graph_utils.dag import NodeWrapper


# Backdrops
def auto_backdrop(nodes=None, padding=50, font_size=40, text=None, backdrop_node=None):
    """
    Automatically puts a backdrop behind the provided/selected nodes.

    Args:
        nodes (list[nuke.Node]): Nuke nodes to create a backdrop for
        padding(int): Add padding around the nodes (default 50px)
        font_size (int): Size for the label (default 40px)
        text (str): Label for the backdrop. Will prompt user if None
        backdrop_node (nuke.Node): Optionally pass an existing backdrop node which
            will be re-used as the auto-backdrop.

    Returns:
        nuke.Node: Created backdrop node
    """
    if not nodes:
        nodes = nuke.selectedNodes()
        if not nodes:
            nuke.message('no nodes are selected')
            return None

    if text is None:
        text = nuke.getInput('Backdrop Label', '')
    backdrop = NodeWrapper(backdrop_node or nuke.nodes.BackdropNode())
    backdrop.node['note_font_size'].setValue(font_size)
    if text:
        backdrop.node['label'].setValue(text)
        backdrop.node.setName('Backdrop_{}'.format(text))

    # Calculate bounds for the backdrop node.
    backdrop.place_around_nodes(nodes, padding=padding)

    # Define Z Order
    z_order = 0
    selected_backdrop_nodes = [n for n in nodes if n.Class() == 'BackdropNode']
    # if there are backdropNodes in our list put the new one immediately behind the farthest one
    if selected_backdrop_nodes:
        z_order = min([node['z_order'].value() for node in selected_backdrop_nodes]) - 1
    else:
        # otherwise (no backdrop in selection) find the nearest backdrop if exists and set the new one in front of it
        # add 3 so that it has 2 empty spots in between
        other_backdrops = [NodeWrapper(bd) for bd in nuke.allNodes('BackdropNode') if bd not in nodes]
        for other_backdrop in other_backdrops:
            if other_backdrop is backdrop:
                continue
            if backdrop.intersects(other_backdrop.bounds):
                z_order = max(z_order, other_backdrop.node['z_order'].value() + 3)

    brightness = 0.5 if z_order % 2 == 0 else 0.35

    # TODO: Use label as a seed for colors? Or categories with presets? Or use the nodes to guess?
    backdrop.node['tile_color'].setValue(rgba_float_to_dec(*random_colour(value=brightness, saturation=0.2)))
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
