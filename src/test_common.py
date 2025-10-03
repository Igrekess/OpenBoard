#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for openboard_common module
Place this in GIMP plug-ins folder to test the import
"""

from gimpfu import *

def test_openboard_common_import():
    """Test if openboard_common can be imported"""
    try:
        from openboard_common import (
            write_log, safe_float, safe_int,
            convert_hex_to_rgb, convert_rgb_to_gimp_color,
            sanitize_filename, find_overlay_files,
            get_image_orientation, create_guide,
            build_layer_bounds_cache,
            ENABLE_LOGS, IMAGE_EXTENSIONS
        )
        
        # Test basic functions
        result = safe_float("123.45", 0.0)
        color = convert_hex_to_rgb("#FF5733")
        filename = sanitize_filename("test/../../file.xcf")
        
        message = "openboard_common import SUCCESS!\n\n"
        message += "Tested functions:\n"
        message += "- safe_float('123.45') = {0}\n".format(result)
        message += "- convert_hex_to_rgb('#FF5733') = {0}\n".format(color)
        message += "- sanitize_filename('test/../../file.xcf') = {0}\n".format(filename)
        message += "\nAll {0} functions available!".format(len(dir()))
        
        pdb.gimp_message(message)
        write_log("Test successful")
        
    except ImportError as e:
        pdb.gimp_message("Import FAILED: {0}".format(e))
    except Exception as e:
        pdb.gimp_message("Test FAILED: {0}".format(e))

register(
    "python_fu_test_openboard_common",
    "Test OpenBoard Common Module",
    "Test import and basic functionality of openboard_common",
    "Yan Senez",
    "Yan Senez",
    "2025",
    "<Toolbox>/Filters/Test OpenBoard Common",
    "",
    [],
    [],
    test_openboard_common_import
)

main()

