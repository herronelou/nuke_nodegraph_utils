import random
import nuke


# Color Conversion utils
def _hex_validate(hex_value):
    """ Validate a hex string is the right length and append an alpha if not present"""
    hex_value.strip('#')
    if len(hex_value) not in [6, 8]:
        raise ValueError("hexadecimal value expected to have 6 or 8 characters ('FFFFFF' or 'FFFFFFFF')")
    if len(hex_value) == 6:
        hex_value += 'ff'
    return hex_value


def hex_to_dec(hex_value):
    """ Convert a web type hexadecimal color string to nuke's tile_color int value """
    hex_value = _hex_validate(hex_value)
    return int(hex_value, 16)


def hex_to_rgba_int(hex_value):
    """ Convert a web type hexadecimal color string to 8bit int RGBA values """
    hex_value = _hex_validate(hex_value)
    rgba = (int(hex_value[i:i+2], 16) for i in [0, 2, 4, 6])
    return rgba


def hex_to_rgb_int(hex_value):
    """ Convert a web type hexadecimal color string to 8bit int RGB values """
    r, g, b, _a = hex_to_rgba_int(hex_value)
    return r, g, b


def hex_to_rgba_float(hex_value):
    """ Convert a web type hexadecimal color string to a float RGBA """
    rgba = hex_to_rgba_int(hex_value)
    return (color/255.0 for color in rgba)


def hex_to_rgb_float(hex_value):
    """ Convert a web type hexadecimal color string to a float RGB """
    r, g, b, _a = hex_to_rgba_float(hex_value)
    return r, g, b


def rgba_int_to_hex(r, g, b, a=255):
    """ Convert 8bit int RGBA values to a web_type hexadecimal color (with 8 chars, strip to 6 for RGB only)"""
    return ''.join('{:02X}'.format(c) for c in (r, g, b, a))


def rgba_float_to_hex(r, g, b, a=1.0):
    """ Convert float RGBA values to a web_type hexadecimal color (with 8 chars, strip to 6 for RGB only)"""
    return rgba_int_to_hex(*(int(n * 255) for n in (r, g, b, a)))


def rgba_int_to_dec(r, g, b, a=255):
    """ Convert 8bit int RGBA values to nuke's tile_color int value"""
    return hex_to_dec(rgba_int_to_hex(r, g, b, a))


def rgba_float_to_dec(r, g, b, a=1.0):
    """ Convert float RGBA values to nuke's tile_color int value"""
    return hex_to_dec(rgba_float_to_hex(r, g, b, a))


def dec_to_hex(decimal):
    """ Convert nuke's tile_color int value to a web type hexadecimal color"""
    return '{:X}'.format(decimal)


def dec_to_rgba_int(decimal):
    """ Convert nuke's tile_color int value to 8bit int RGB values """
    return hex_to_rgba_int(dec_to_hex(decimal))


def dec_to_rgba_float(decimal):
    """ Convert nuke's tile_color int value to  float RGBA values"""
    return hex_to_rgba_float(dec_to_hex(decimal))


# Other color helpers
def random_colour(hue=None, saturation=None, value=None):
    """
    Generates a random color.

    Args:
        hue (float, optional): The hue value. If None, a random value will be generated.
        saturation (float, optional): The saturation value. If None, a random value will be generated.
        value (float, optional): The value value (brightness). If None, a random value will be generated.

    Returns:
        tuple[float]: The RGB values of the generated color.
    """
    import colorsys
    if hue is None:
        hue = random.random()
    if saturation is None:
        saturation = random.random()
    if value is None:
        value = random.random()

    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)

    return r, g, b


def node_color(node):
    """
    Get the color of a node, even if set to default.

    Args:
        node (nuke.Node): The node to get the color of.

    Returns:
        int: The color of the node.
    """
    if not node:
        return 0
    color = node.knob('tile_color').value()
    if not color:
        color = nuke.defaultNodeColor(node.Class())
    return color


# Auto Dot color callbacks
def auto_dot_color_callback():
    """
    Change the color of a dot to that of its parent node.
    """
    def real_parent(_node):
        """
        Get the parent non-dot parent node.

        Args:
            _node (nuke.Node): The node to find the parent of.

        Returns:
            nuke.Node: The parent node.
        """
        _parent = _node.input(0)
        while _parent and _parent.Class() == 'Dot':
            _parent = _parent.input(0)
        return _parent

    node = nuke.thisNode()
    if nuke.thisKnob().name() in ['inputChange']:
        parent = real_parent(node)
        color = node_color(parent)

        recursive_tile_color(node, color)

    elif nuke.thisKnob().name() in ['selected']:
        # On selection, we run a less expensive version of the same function.
        # We avoid recursive calls as we may have a lot of dots in the selection.
        # This should only come into play when opening a script that didn't have the callback enabled.
        parent = node.input(0)
        color = node_color(parent)
        node.knob('tile_color').setValue(color)


def tile_color_changed_callback():
    """
    When the tile color changes, we need to update children dots color.
    """
    if nuke.thisKnob().name() != 'tile_color':
        return
    node = nuke.thisNode()
    color = nuke.thisKnob().value()
    recursive_tile_color(node, color)


def recursive_tile_color(node, color):
    """
    Recursively set the tile color of a node and its dot-children.

    Args:
        node (nuke.Node): The node to set the color of.
        color (int): The color to set the node to.
    """
    node.knob('tile_color').setValue(color)
    inputs = nuke.INPUTS | nuke.HIDDEN_INPUTS
    dependents = [dependent for dependent in node.dependent(inputs, forceEvaluate=False) if dependent.Class() == 'Dot']
    for node in dependents:
        recursive_tile_color(node, color)
