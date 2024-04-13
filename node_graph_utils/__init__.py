"""
DAG utilities

github.com/herronelou/nuke_nodegraph_utils
"""
import os
from functools import partial

import nuke

from . import align
from . import backdrops
from . import colors
from . import dag
from . import labeler
from . import scale_widget
# Experimental
from . import snippy
from . import snappy

# TODO: Refactor for delayed imports


# Mini functions definitions, can be called via menus or API
def align_selection(direction):
    nodes = nuke.selectedNodes()
    align.smart_align(direction, nodes)


def scale_tree():
    """ Scale tree with a bounding widget. """
    global scale_tree_widget
    this_dag = dag.get_current_dag()
    scale_tree_widget = scale_widget.ScaleWidget(this_dag)
    scale_tree_widget.show()


def mirror_nodes():
    """ Mirror nodes in X """
    align.mirror_nodes(nuke.selectedNodes())


def relabel():
    """ Change the node(s) label"""
    global relabel_popup
    relabel_popup = labeler.Labeller()
    relabel_popup.run()


def interval(axis=dag.AXIS_X):
    align.distribute_nodes(nuke.selectedNodes(), axis, 6 if axis == dag.AXIS_X else 2)


def install_menus(icons_root=None, install_experimental_menus=False):
    """ Create menu entry for all the alignment nodes """
    def _get_icon(name):
        if not icons_root:
            return '/'
        path = os.path.join(icons_root, name) + '.png'
        return path.replace('\\', '/')

    organize_menu = nuke.menu('Nuke').addMenu('Organize Nodes', icon=_get_icon('align_center_x'))

    organize_menu.addCommand('Align Nodes - Left', partial(align_selection, dag.LEFT), 'meta+4', shortcutContext=2,
                             icon=_get_icon('align_left'))
    organize_menu.addCommand('Align Nodes - Right', partial(align_selection, dag.RIGHT), 'meta+6', shortcutContext=2,
                             icon=_get_icon('align_right'))
    organize_menu.addCommand('Align Nodes - Center X', partial(align_selection, dag.CENTER_X), 'meta+5',
                             shortcutContext=2, icon=_get_icon('align_center_x'))
    organize_menu.addCommand('Align Nodes - Top', partial(align_selection, dag.UP), 'meta+8', shortcutContext=2,
                             icon=_get_icon('align_top'))
    organize_menu.addCommand('Align Nodes - Bottom', partial(align_selection, dag.DOWN), 'meta+2', shortcutContext=2,
                             icon=_get_icon('align_bottom'))
    organize_menu.addCommand('Align Nodes - Center Y', partial(align_selection, dag.CENTER_Y), 'meta+ctrl+5',
                             shortcutContext=2, icon=_get_icon('align_center_y'))
    organize_menu.addSeparator()

    organize_menu.addCommand('Scale Nodes', scale_tree, 'ctrl++', shortcutContext=2, icon=_get_icon('scale_nodes'))
    organize_menu.addCommand('Distribute Nodes Horizontally', partial(interval, dag.AXIS_X), 'meta+0',
                             shortcutContext=2, icon=_get_icon('space_x'))
    organize_menu.addCommand('Distribute Nodes Vertically', partial(interval, dag.AXIS_Y), 'meta+ctrl+0',
                             shortcutContext=2, icon=_get_icon('space_y'))
    organize_menu.addCommand('Mirror Nodes', mirror_nodes, 'meta+/', shortcutContext=2, icon=_get_icon('mirror_x'))
    organize_menu.addCommand('Summon Nodes', dag.summon_nodes, 'ctrl+f', shortcutContext=2, icon=_get_icon('summon'))

    organize_menu.addSeparator()

    organize_menu.addCommand('Re-Label Nodes', relabel, 'shift+n', shortcutContext=2, icon=_get_icon('label_node'))

    organize_menu.addSeparator()

    backdrop_menu = organize_menu.addMenu('Backdrops', icon="Backdrop.png")
    backdrop_menu.addCommand('AutoBackdrop', backdrops.auto_backdrop_dialog, 'alt+b', shortcutContext=2, icon='Backdrop.png')
    backdrop_menu.addCommand('Sort backdrops', backdrops.auto_layer_backdrops, icon=_get_icon('sort_backdrop'))
    backdrop_menu.addCommand('Snap Backdrops to contents', backdrops.snap_backdrops_to_contents,
                             icon=_get_icon('snap_backdrop'))

    if install_experimental_menus:
        experimental_menu = organize_menu.addMenu('Experimental')
        experimental_menu.addCommand('Draw Connections', snappy.snap, 'u', shortcutContext=2)
        experimental_menu.addCommand('Snip Connections', snippy.snip, 'y', shortcutContext=2)
        experimental_menu.addCommand('De-Intersect Nodes', dag.de_intersect)
