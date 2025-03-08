# nuke nodegraph_utils
Collection of utilities for manipulating Nuke's NodeGraph

## Installation
### Easy install
There are two releases of this tool, the 'nukepedia' release, and the github one.
The release on nukepedia is fully self-contained and doesn't have any dependencies, but is not maintained as much as the github one.
The GitHub code has a dependency on https://github.com/mottosso/Qt.py.
#### Installing the tools
Download the whole .zip file of the project and uncompress it somewhere, for example `C:\Users\my_user\.nuke\node_graph_utils`.
In your `init.py` (see https://learn.foundry.com/nuke/developers/131/pythondevguide/startup.html for more info on init.py), add the following line:

    nuke.pluginAddPath(r"C:\Users\my_user\.nuke\node_graph_utils")

(Ensure you adjust the path to your own install path. It should point to where the provided menu.py lives.)  
If you are getting the code from GitHub, you will also need to install the Qt.py library. You can do so by downloading the library from
the link provided above and placing it in the same folder as the node_graph_utils package.

### Custom Install
You could modify the installation to fit your needs. The simplest modification you could do is to exclude the experimental features.
To do so, locate the provided menu.py and change the line:

    node_graph_utils.install_menus(icons_root=ICONS_ROOT, install_experimental_menus=True)

to

    node_graph_utils.install_menus(icons_root=ICONS_ROOT, install_experimental_menus=False)
If you would like, you could also store the icons in a different location and provide the icons path to this method.

For advanced users, using the pre-made `install_menus` method is optional and all functions can be exposed manually from scratch. 


### Customizing keyboard shortcuts
All the menus and keyboard shortcuts are defined in the `install_menus` method, which lives in the package's `__init__.py` file.
By default, I have mapped the shortcuts to be used along with the meta key (windows key on keyboards).
If for example you wanted to remap the "AutoBackdrop" command to Ctrl+B instead of my default Alt+B (because somehow you use nuke's Branch command, which normally has the Alt+B shortcut).
You would locate the line where the command is added:

    backdrop_menu.addCommand('AutoBackdrop', backdrops.auto_backdrop, 'alt+b', shortcutContext=2, icon='Backdrop.png')
and change the shortcut like so:

    backdrop_menu.addCommand('AutoBackdrop', backdrops.auto_backdrop, 'ctrl+b', shortcutContext=2, icon='Backdrop.png')

## Nuke 16+ compatibility
In Nuke 16, Foundry updated Qt, using PySide6 instead of PySide2.
You need Qt.py with at least version 1.4.1 to use this tool in Nuke 16+, as well as pulling a version of this repository that is more recent than 2025-03-08.
