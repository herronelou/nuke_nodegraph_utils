import random


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
    :param hue: float or None. Will generate randomly if None.
    :param saturation: float or None. Will generate randomly if None.
    :param value: float or None. Will generate randomly if None.
    :return: tuple(r, g, b)
    :rtype: tuple[float]
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
