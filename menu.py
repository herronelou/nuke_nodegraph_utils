import os

import node_graph_utils

# ---------------------------
# Configure some options here
# ---------------------------
# Enable or Disable the experimental features, such as Snippy and Snappy (connection and disconnection tools)
EXPERIMENTAL_FEATURES = True
# Enable or Disable the auto color dot feature. This colors dots automatically based on the node they are connected to.
# It does run a callback which some might prefer to disable which is why it's off by default.
AUTO_DOT_COLOR = False

# ----------------
# Code starts here
# ----------------
ICONS_ROOT = os.path.join(os.path.dirname(__file__), 'icons')
node_graph_utils.install_menus(icons_root=ICONS_ROOT, install_experimental_menus=True)
if AUTO_DOT_COLOR:
    node_graph_utils.install_auto_dot_color()
