#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Open Board - Layout Creator for GIMP
# By Yan Senez
# Version 1.1 - Improved with security fixes and refactoring

from gimpfu import *
import os
import time
import json
import math
import re

# ============================================================================
# CONSTANTS
# ============================================================================

ENABLE_LOGS = True  # Activer/désactiver l'écriture des logs
DEFAULT_DPI = 72.0
DEFAULT_SPACING = 40.0
GUTTER_MIN_WIDTH = 2
GUTTER_WIDTH_DIVISOR = 500
GUTTER_HEIGHT_RATIO = 0.9
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.xcf', '.psd', '.bmp', '.gif']
GUTTER_COLOR = (34, 34, 34)
MIN_LEGEND_MARGIN = 60  # Marge minimale en bas pour la légende (en pixels)
MIN_LOGO_MARGIN = 60  # Marge minimale en haut pour le logo (en pixels)

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

global_dest_folder = None
log_file_cleared = False

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal"""
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\s\-.]', '', filename)
    return filename

def safe_float(value, default=0.0):
    """Safely convert to float"""
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except:
        return default

def safe_int(value, default=0):
    """Safely convert to int"""
    try:
        return int(safe_float(value, default))
    except:
        return default

def write_log(message, log_folder_path=None):
    """Write log messages"""
    if not ENABLE_LOGS:
        return True
    
    try:
        if log_folder_path is None:
            import tempfile
            log_folder_path = tempfile.gettempdir()
        
        log_file_path = os.path.join(log_folder_path, "board_gimp_log.txt")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        full_message = "{0} - {1}".format(timestamp, message)
        
        with open(log_file_path, 'a') as log_file:
            log_file.write(full_message + "\n")
        print(full_message)
        return True
    except Exception as e:
        print("Error writing to log: {0}".format(e))
        return False

def ensure_folder_exists(folder_path):
    """Ensure folder exists"""
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            write_log("Created folder: {0}".format(folder_path))
        return folder_path
    except Exception as e:
        write_log("Error creating folder: {0}".format(e))
        return None

def convert_hex_to_rgb(hex_color):
    """Convert hex color to RGB (0-255)"""
    if hasattr(hex_color, 'r') and hasattr(hex_color, 'g') and hasattr(hex_color, 'b'):
        return (int(hex_color.r * 255), int(hex_color.g * 255), int(hex_color.b * 255))
    elif isinstance(hex_color, (tuple, list)) and len(hex_color) >= 3:
        return (int(hex_color[0]), int(hex_color[1]), int(hex_color[2]))
    
    try:
        hex_color = str(hex_color).lstrip('#')
        if len(hex_color) != 6:
            write_log("Invalid hex color: {0}, using white".format(hex_color))
            return (255, 255, 255)
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
    except Exception as e:
        write_log("Error converting color: {0}".format(e))
        return (255, 255, 255)

def convert_rgb_to_gimp_color(rgb):
    """Convert RGB to GIMP color (0.0-1.0)"""
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)

def convert_to_pixels(value, unit, resolution):
    """Convert dimensions to pixels"""
    try:
        value = safe_float(value, 0.0)
        resolution = safe_float(resolution, DEFAULT_DPI)
        
        if resolution <= 0:
            resolution = DEFAULT_DPI
        
        if unit.lower() == "mm":
            return float((value / 25.4) * resolution)
        elif unit.lower() == "cm":
            return float((value / 2.54) * resolution)
        elif unit.lower() == "in":
            return float(value * resolution)
        elif unit.lower() == "pt":
            return float((value / 72.0) * resolution)
        else:
            return float(value)
    except Exception as e:
        write_log("Error in convert_to_pixels: {0}".format(e))
        return 0.0

def write_cell_coordinates(rectangle, dit_path, cell_number):
    """Write cell coordinates to .board file"""
    try:
        with open(dit_path, 'a') as dit_file:
            line = "{0},{1},{2},{3},{4},{5},{6},{7},{8}".format(
                cell_number, rectangle[0][0], rectangle[0][1], rectangle[1][0], rectangle[1][1],
                rectangle[2][0], rectangle[2][1], rectangle[3][0], rectangle[3][1])
            dit_file.write(line + "\n")
    except Exception as e:
        write_log("Error writing cell: {0}".format(e))

def remove_dit_file(file_path):
    """Remove .board file if exists"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            write_log("Removed .board file: {0}".format(file_path))
        return True
    except Exception as e:
        write_log("Error removing .board file: {0}".format(e))
        return False

def find_overlay_files(path):
    """Find overlay files"""
    try:
        if not path or not os.path.exists(path):
            return []
        
        if os.path.isfile(path):
            return [path]
        
        if os.path.isdir(path):
            overlay_files = []
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        overlay_files.append(file_path)
            overlay_files.sort()
            return overlay_files
        return []
    except Exception as e:
        write_log("Error finding overlays: {0}".format(e))
        return []

def create_guide(img, position, orientation):
    """Create guide"""
    if orientation == "horizontal":
        pdb.gimp_image_add_hguide(img, position)
    else:
        pdb.gimp_image_add_vguide(img, position)

def fill_selection_with_color(img, drawable, rgb_color):
    """Fill selection with color"""
    old_fg = pdb.gimp_context_get_foreground()
    pdb.gimp_context_set_foreground((rgb_color[0], rgb_color[1], rgb_color[2]))
    pdb.gimp_edit_fill(drawable, FILL_FOREGROUND)
    pdb.gimp_context_set_foreground(old_fg)

def create_rectangular_selection(img, rectangle):
    """Create rectangular selection"""
    x = min(rectangle[0][0], rectangle[1][0], rectangle[2][0], rectangle[3][0])
    y = min(rectangle[0][1], rectangle[1][1], rectangle[2][1], rectangle[3][1])
    width = max(rectangle[0][0], rectangle[1][0], rectangle[2][0], rectangle[3][0]) - x
    height = max(rectangle[0][1], rectangle[1][1], rectangle[2][1], rectangle[3][1]) - y
    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE, x, y, width, height)
    return True

def get_image_orientation(image_path):
    """Get image orientation"""
    try:
        temp_img = pdb.gimp_file_load(image_path, image_path)
        width = temp_img.width
        height = temp_img.height
        pdb.gimp_image_delete(temp_img)
        return "Landscape" if width > height else "Portrait" if height > width else "Square"
    except:
        return "Landscape"

def calculate_overlay_dimensions(cell_width, cell_height, cell_type, orientation, margin):
    """Calculate overlay dimensions"""
    result = {
        'position': 'center',
        'dimensions': {'width': cell_width, 'height': cell_height, 'x': 0, 'y': 0}
    }
    
    if cell_type.lower() == "spread" and orientation == "Portrait":
        half_width = cell_width / 2
        result['position'] = 'split'
        result['dimensions'] = {
            'left': {'width': half_width, 'height': cell_height, 'x': 0, 'y': 0},
            'right': {'width': half_width, 'height': cell_height, 'x': half_width, 'y': 0}
        }
    return result

def place_overlay_in_cell(img, overlay_path, cell_x, cell_y, cell_width, cell_height, 
                          cell_type, overlay_group, position_info):
    """Place overlay in cell"""
    try:
        overlay_img = pdb.gimp_file_load(overlay_path, overlay_path)
        overlay_layer = overlay_img.active_layer if overlay_img.active_layer else overlay_img.layers[0]
        
        new_layer = pdb.gimp_layer_new_from_drawable(overlay_layer, img)
        pdb.gimp_image_insert_layer(img, new_layer, overlay_group, 0)
        
        overlay_name = os.path.splitext(os.path.basename(overlay_path))[0]
        pdb.gimp_item_set_name(new_layer, "Overlay_{0}".format(overlay_name))
        
        if position_info['position'] == 'center':
            dims = position_info['dimensions']
            pdb.gimp_layer_scale(new_layer, int(dims['width']), int(dims['height']), True)
            pdb.gimp_layer_set_offsets(new_layer, int(cell_x), int(cell_y))
        
        pdb.gimp_image_delete(overlay_img)
        return new_layer
    except Exception as e:
        write_log("Error placing overlay: {0}".format(e))
        return None

def get_overlay_index_for_cell(row, col, nbr_cols, overlay_count, cell_type):
    """Get overlay index for cell"""
    if overlay_count == 0:
        return 0
    cell_number = (row - 1) * nbr_cols + (col - 1)
    if cell_type.lower() == "spread":
        return ((cell_number % 2) * 2) % overlay_count
    return cell_number % overlay_count

def write_overlay_metadata_to_dit(dit_path, overlay_files, overlay_indexes):
    """Write overlay metadata"""
    try:
        existing_content = ""
        if os.path.exists(dit_path):
            with open(dit_path, 'r') as f:
                existing_content = f.read()
        
        with open(dit_path, 'w') as f:
            if overlay_files:
                f.write("#overlayFiles={0}\n".format(json.dumps(overlay_files)))
            for cell_key, index in overlay_indexes.items():
                f.write("#{0}={1}\n".format(cell_key, index))
            
            for line in existing_content.split('\n'):
                if not line.startswith('#overlayFiles=') and not line.startswith('#overlay_index_cell_'):
                    if line.strip():
                        f.write(line + "\n")
        return True
    except Exception as e:
        write_log("Error writing overlay metadata: {0}".format(e))
        return False

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def create_board_layout(board_name, dest_folder,
                       layout_units, layout_resolution, layout_width, layout_height,
                       nbr_col, nbr_row, cell_type, cell_units, cell_width, cell_height, margin_mask,
                       spacing_units, layout_spacing,
                       bg_color_hex, border_color_hex, layout_color_hex,
                       baseline_text, selected_font, baseline_text_size, baseline_text_color_hex,
                       logo_folder_path,
                       overlay_mask_on, overlay_file_path, overlay_folder_path,
                       should_create_guides):
    """Main function to create board layout"""
    
    write_log("Open Board - Layout Creator started")
    
    # Sanitize and validate
    board_name = sanitize_filename(board_name)
    if not board_name:
        pdb.gimp_message("Invalid board name")
        return
    
    # Validate destination folder
    if not dest_folder or not isinstance(dest_folder, str) or dest_folder.strip() == "":
        pdb.gimp_message("Please select a destination folder")
        return
    
    # Ensure destination folder exists
    if not os.path.exists(dest_folder):
        try:
            os.makedirs(dest_folder)
            write_log("Created destination folder: {0}".format(dest_folder))
        except Exception as e:
            pdb.gimp_message("Cannot create destination folder: {0}".format(e))
            return
    
    # Convert parameters
    units_list = ["px", "mm", "cm", "in", "pt"]
    cell_type_list = ["single", "spread"]
    
    if isinstance(layout_units, int):
        layout_units = units_list[layout_units]
    if isinstance(cell_units, int):
        cell_units = units_list[cell_units]
    if isinstance(spacing_units, int):
        spacing_units = units_list[spacing_units]
    if isinstance(cell_type, int):
        cell_type = cell_type_list[cell_type]
    if isinstance(should_create_guides, bool):
        should_create_guides = "true" if should_create_guides else "false"
    
    global global_dest_folder
    global_dest_folder = dest_folder
    
    # Convert colors
    bg_color = convert_hex_to_rgb(bg_color_hex)
    border_color = convert_hex_to_rgb(border_color_hex)
    layout_color = convert_hex_to_rgb(layout_color_hex)
    baseline_text_color = convert_hex_to_rgb(baseline_text_color_hex)
    
    # Convert dimensions
    px_layout_width = safe_int(convert_to_pixels(layout_width, layout_units, layout_resolution))
    px_layout_height = safe_int(convert_to_pixels(layout_height, layout_units, layout_resolution))
    px_cell_width = safe_int(convert_to_pixels(cell_width, cell_units, layout_resolution))
    px_cell_height = safe_int(convert_to_pixels(cell_height, cell_units, layout_resolution))
    px_layout_spacing = safe_int(convert_to_pixels(layout_spacing, spacing_units, layout_resolution))
    px_margin = safe_int(convert_to_pixels(margin_mask, cell_units, layout_resolution))
    
    write_log("Dimensions - Layout: {0}x{1}, Cell: {2}x{3}, Spacing: {4}, Margin: {5}".format(
        px_layout_width, px_layout_height, px_cell_width, px_cell_height, px_layout_spacing, px_margin))
    
    # Calculate totals
    total_cells_width = (nbr_col * px_cell_width) + ((nbr_col - 1) * px_layout_spacing)
    total_cells_height = (nbr_row * px_cell_height) + ((nbr_row - 1) * px_layout_spacing)
    
    maxWidth = safe_int(px_cell_width - (2 * px_margin))
    maxHeight = safe_int(px_cell_height - (2 * px_margin))
    
    # Auto-scaling
    if total_cells_width > px_layout_width or total_cells_height > px_layout_height:
        write_log("AUTO-SCALING OPTIMIZATION")
        scale_factor = min(float(px_layout_width) / total_cells_width, 
                          float(px_layout_height) / total_cells_height) * 0.95
        
        px_cell_width = safe_int(math.floor(px_cell_width * scale_factor))
        px_cell_height = safe_int(math.floor(px_cell_height * scale_factor))
        px_layout_spacing = safe_int(math.floor(px_layout_spacing * scale_factor))
        px_margin = safe_int(math.floor(px_margin * scale_factor))
        
        total_cells_width = (nbr_col * px_cell_width) + ((nbr_col - 1) * px_layout_spacing)
        total_cells_height = (nbr_row * px_cell_height) + ((nbr_row - 1) * px_layout_spacing)
        
        maxWidth = safe_int(px_cell_width - (2 * px_margin))
        maxHeight = safe_int(px_cell_height - (2 * px_margin))
        write_log("Optimized dimensions - Max image: {0}x{1}".format(maxWidth, maxHeight))
    
    global max_width, max_height
    max_width = maxWidth
    max_height = maxHeight
    
    # File paths
    xcf_path = os.path.join(dest_folder, "{0}.xcf".format(board_name))
    dit_path = os.path.join(dest_folder, "{0}.board".format(board_name))
    
    remove_dit_file(dit_path)
    
    # Create .board file
    try:
        with open(dit_path, 'w') as dit_file:
            dit_file.write("# Board Layout File\n")
            dit_file.write("#boardName={0}\n".format(board_name))
            dit_file.write("#nbrCols={0}\n".format(nbr_col))
            dit_file.write("#nbrRows={0}\n".format(nbr_row))
            dit_file.write("#cellWidth={0}\n".format(px_cell_width))
            dit_file.write("#cellHeight={0}\n".format(px_cell_height))
            dit_file.write("#cellType={0}\n".format(cell_type))
            dit_file.write("#adjustedMargin={0}\n".format(px_margin))
    except Exception as e:
        pdb.gimp_message("Error creating .board file: {0}".format(e))
        return
    
    # Create image
    img = gimp.Image(px_layout_width, px_layout_height, RGB)
    img.resolution = (layout_resolution, layout_resolution)
    
    # Background
    bg_layer = gimp.Layer(img, "Background", px_layout_width, px_layout_height, RGB_IMAGE, 100, NORMAL_MODE)
    img.add_layer(bg_layer, 0)
    pdb.gimp_context_set_foreground(convert_rgb_to_gimp_color(bg_color))
    pdb.gimp_edit_fill(bg_layer, FILL_FOREGROUND)
    
    # Layer groups
    try:
        board_content_group = pdb.gimp_layer_group_new(img)
        img.add_layer(board_content_group, 0)
        pdb.gimp_item_set_name(board_content_group, "Board Content")
        
        layout_masks_group = pdb.gimp_layer_group_new(img)
        img.add_layer(layout_masks_group, 0)
        pdb.gimp_item_set_name(layout_masks_group, "Board Elements")
        
        has_layer_groups = True
        parent_layer = layout_masks_group
    except:
        has_layer_groups = False
        layout_masks_layer = gimp.Layer(img, "Board Elements", px_layout_width, px_layout_height, RGBA_IMAGE, 100, NORMAL_MODE)
        img.add_layer(layout_masks_layer, 0)
        board_content_layer = gimp.Layer(img, "Board Content", px_layout_width, px_layout_height, RGBA_IMAGE, 100, NORMAL_MODE)
        img.add_layer(board_content_layer, 0)
        parent_layer = layout_masks_layer
    
    # Create layers
    if cell_type.lower() == "spread":
        if has_layer_groups:
            single_page_group = pdb.gimp_layer_group_new(img)
            img.add_layer(single_page_group, 0)
            pdb.gimp_image_reorder_item(img, single_page_group, parent_layer, 0)
            pdb.gimp_item_set_name(single_page_group, "Simple page Mask")
            
            for row in range(1, nbr_row + 1):
                for col in range(1, nbr_col + 1):
                    mask_layer = gimp.Layer(img, "R{0}C{1}".format(row, col), px_layout_width, px_layout_height, RGBA_IMAGE, 100, NORMAL_MODE)
                    img.add_layer(mask_layer, 0)
                    pdb.gimp_image_reorder_item(img, mask_layer, single_page_group, 0)
                    pdb.gimp_item_set_visible(mask_layer, False)
        
        gutters_layer = gimp.Layer(img, "Gutters", px_layout_width, px_layout_height, RGBA_IMAGE, 100, NORMAL_MODE)
        img.add_layer(gutters_layer, 0)
        if has_layer_groups:
            pdb.gimp_image_reorder_item(img, gutters_layer, parent_layer, 0)
    
    borders_layer = gimp.Layer(img, "Borders", px_layout_width, px_layout_height, RGBA_IMAGE, 100, NORMAL_MODE)
    img.add_layer(borders_layer, 0)
    if has_layer_groups:
        pdb.gimp_image_reorder_item(img, borders_layer, parent_layer, 0)
    
    mask_layer = gimp.Layer(img, "Mask", px_layout_width, px_layout_height, RGBA_IMAGE, 100, NORMAL_MODE)
    img.add_layer(mask_layer, 0)
    if has_layer_groups:
        pdb.gimp_image_reorder_item(img, mask_layer, parent_layer, 0)
    
    # Fill layers
    pdb.gimp_selection_all(img)
    img.active_layer = borders_layer
    fill_selection_with_color(img, borders_layer, border_color)
    pdb.gimp_selection_none(img)
    
    pdb.gimp_selection_all(img)
    img.active_layer = mask_layer
    fill_selection_with_color(img, mask_layer, layout_color)
    pdb.gimp_selection_none(img)
    
    # Calculate centering avec marges pour logo et légende
    available_vertical_space = px_layout_height - MIN_LOGO_MARGIN - MIN_LEGEND_MARGIN
    
    # Si l'espace disponible est insuffisant, on réduit les marges proportionnellement
    if total_cells_height > available_vertical_space:
        vertical_margin_top = MIN_LOGO_MARGIN * 0.5
        vertical_margin_bottom = MIN_LEGEND_MARGIN * 0.5
    else:
        vertical_margin_top = MIN_LOGO_MARGIN
        vertical_margin_bottom = MIN_LEGEND_MARGIN
    
    decal_to_center_x = safe_int(math.floor((px_layout_width - total_cells_width) / 2))
    decal_to_center_y = safe_int(math.floor(vertical_margin_top + (available_vertical_space - total_cells_height) / 2))
    
    first_cell_x = safe_int(math.floor(decal_to_center_x))
    first_cell_y = safe_int(math.floor(decal_to_center_y))
    
    write_log("Centering - Top margin: {0}px, Bottom margin: {1}px".format(
        int(vertical_margin_top), int(vertical_margin_bottom)))
    
    # Overlays
    overlay_files = []
    overlay_indexes = {}
    overlay_group = None
    
    if isinstance(overlay_mask_on, str):
        overlay_mask_on = overlay_mask_on.lower() == "true"
    
    if overlay_mask_on:
        if overlay_file_path and os.path.exists(overlay_file_path):
            overlay_files = find_overlay_files(overlay_file_path)
        elif overlay_folder_path and os.path.exists(overlay_folder_path):
            overlay_files = find_overlay_files(overlay_folder_path)
        
        if overlay_files:
            try:
                overlay_group = pdb.gimp_layer_group_new(img)
                pdb.gimp_item_set_name(overlay_group, "Overlay")
                pdb.gimp_image_insert_layer(img, overlay_group, parent_layer, 0)
                
                for r in range(1, nbr_row + 1):
                    for c in range(1, nbr_col + 1):
                        cell_key = "overlay_index_cell_{0}_{1}".format(r, c)
                        overlay_index = get_overlay_index_for_cell(r, c, nbr_col, len(overlay_files), cell_type)
                        overlay_indexes[cell_key] = overlay_index
            except Exception as e:
                write_log("Error creating overlay group: {0}".format(e))
    
    # Create cells
    for r in range(1, nbr_row + 1):
        for c in range(1, nbr_col + 1):
            x = safe_int(math.floor(decal_to_center_x + (c - 1) * (px_cell_width + px_layout_spacing)))
            y = safe_int(math.floor(decal_to_center_y + (r - 1) * (px_cell_height + px_layout_spacing)))
            cell_number = (r - 1) * nbr_col + c
            
            rectangle_ref = [[x, y], [x, y + px_cell_height], [x + px_cell_width, y + px_cell_height], [x + px_cell_width, y]]
            write_cell_coordinates(rectangle_ref, dit_path, cell_number)
            
            inner_rectangle = [
                [x + px_margin, y + px_margin],
                [x + px_margin, y + px_cell_height - px_margin],
                [x + px_cell_width - px_margin, y + px_cell_height - px_margin],
                [x + px_cell_width - px_margin, y + px_margin]
            ]
            
            img.active_layer = borders_layer
            create_rectangular_selection(img, inner_rectangle)
            pdb.gimp_edit_clear(borders_layer)
            pdb.gimp_selection_none(img)
            
            img.active_layer = mask_layer
            create_rectangular_selection(img, rectangle_ref)
            pdb.gimp_edit_clear(mask_layer)
            pdb.gimp_selection_none(img)
            
            if cell_type.lower() == "spread" and 'gutters_layer' in locals():
                gutter_width = safe_int(max(GUTTER_MIN_WIDTH, round(px_cell_width / float(GUTTER_WIDTH_DIVISOR))))
                middle_x = safe_int(x + (px_cell_width / 2))
                
                img.active_layer = gutters_layer
                gutter_height = safe_int(px_cell_height * GUTTER_HEIGHT_RATIO)
                gutter_y_offset = safe_int((px_cell_height - gutter_height) / 2)
                
                gutter_rect = [
                    [safe_int(middle_x - gutter_width/2), safe_int(y + gutter_y_offset)],
                    [safe_int(middle_x - gutter_width/2), safe_int(y + gutter_y_offset + gutter_height)],
                    [safe_int(middle_x + gutter_width/2), safe_int(y + gutter_y_offset + gutter_height)],
                    [safe_int(middle_x + gutter_width/2), safe_int(y + gutter_y_offset)]
                ]
                
                create_rectangular_selection(img, gutter_rect)
                fill_selection_with_color(img, gutters_layer, GUTTER_COLOR)
                pdb.gimp_selection_none(img)
                
                if has_layer_groups:
                    single_page_id = "R{0}C{1}".format(r, c)
                    for child in single_page_group.children:
                        if not pdb.gimp_item_is_group(child) and pdb.gimp_item_get_name(child) == single_page_id:
                            single_page_rect = [
                                [middle_x - px_margin, y],
                                [middle_x - px_margin, y + px_cell_height],
                                [middle_x + px_margin, y + px_cell_height],
                                [middle_x + px_margin, y]
                            ]
                            img.active_layer = child
                            create_rectangular_selection(img, single_page_rect)
                            fill_selection_with_color(img, child, border_color)
                            pdb.gimp_selection_none(img)
                            break
            
            if overlay_mask_on and overlay_group and overlay_files:
                try:
                    cell_key = "overlay_index_cell_{0}_{1}".format(r, c)
                    overlay_index = overlay_indexes.get(cell_key, 0)
                    if overlay_index >= len(overlay_files):
                        overlay_index = overlay_index % len(overlay_files)
                    
                    overlay_path = overlay_files[overlay_index]
                    orientation = get_image_orientation(overlay_path)
                    position_info = calculate_overlay_dimensions(px_cell_width, px_cell_height, cell_type, orientation, px_margin)
                    
                    if position_info['position'] == 'center':
                        place_overlay_in_cell(img, overlay_path, x, y, px_cell_width, px_cell_height, cell_type, overlay_group, position_info)
                    elif position_info['position'] == 'split':
                        left_info = {'position': 'center', 'dimensions': position_info['dimensions']['left']}
                        place_overlay_in_cell(img, overlay_path, x, y, 
                            safe_int(position_info['dimensions']['left']['width']),
                            safe_int(position_info['dimensions']['left']['height']),
                            cell_type, overlay_group, left_info)
                        
                        if len(overlay_files) > 1:
                            next_index = (overlay_index + 1) % len(overlay_files)
                            next_overlay_path = overlay_files[next_index]
                            right_info = {'position': 'center', 'dimensions': position_info['dimensions']['right']}
                            place_overlay_in_cell(img, next_overlay_path,
                                safe_int(x + position_info['dimensions']['right']['x']), y,
                                safe_int(position_info['dimensions']['right']['width']),
                                safe_int(position_info['dimensions']['right']['height']),
                                cell_type, overlay_group, right_info)
                except Exception as e:
                    write_log("Error placing overlay: {0}".format(e))
            
            if should_create_guides == "true":
                if r == 1:
                    create_guide(img, safe_int(x), "vertical")
                    create_guide(img, safe_int(x + px_cell_width), "vertical")
                    create_guide(img, safe_int(x + px_margin), "vertical")
                    create_guide(img, safe_int(x + px_cell_width - px_margin), "vertical")
                    if cell_type.lower() == "spread":
                        create_guide(img, safe_int(x + px_cell_width/2), "vertical")
                if c == 1:
                    create_guide(img, safe_int(y), "horizontal")
                    create_guide(img, safe_int(y + px_cell_height), "horizontal")
                    create_guide(img, safe_int(y + px_margin), "horizontal")
                    create_guide(img, safe_int(y + px_cell_height - px_margin), "horizontal")
    
    # Legend
    if baseline_text and isinstance(baseline_text, str) and len(baseline_text) > 0:
        try:
            text_layer = pdb.gimp_text_fontname(img, None, 0, 0, baseline_text, 0, True, baseline_text_size, PIXELS, selected_font)
            pdb.gimp_item_set_name(text_layer, "Legend")
            pdb.gimp_text_layer_set_color(text_layer, baseline_text_color)
            
            last_cell_right = safe_int(first_cell_x + (nbr_col * px_cell_width) + ((nbr_col - 1) * px_layout_spacing))
            last_row_bottom = safe_int(first_cell_y + (nbr_row * px_cell_height) + ((nbr_row - 1) * px_layout_spacing))
            
            # Positionner la légende avec une marge de sécurité
            text_height = pdb.gimp_drawable_height(text_layer)
            text_width = pdb.gimp_drawable_width(text_layer)
            
            # Position Y : au milieu de l'espace disponible sous les cellules, avec marge minimale du bord
            available_bottom_space = px_layout_height - last_row_bottom
            legend_margin_from_bottom = max(20, MIN_LEGEND_MARGIN * 0.3)  # 20px minimum du bord
            legend_y = safe_int(last_row_bottom + (available_bottom_space - text_height) / 2)
            
            # S'assurer qu'on ne dépasse pas trop près du bord
            max_y = px_layout_height - text_height - legend_margin_from_bottom
            legend_y = min(legend_y, safe_int(max_y))
            
            # Position X : aligné à droite avec une petite marge
            legend_x = safe_int(last_cell_right - text_width - 10)
            
            pdb.gimp_layer_set_offsets(text_layer, legend_x, legend_y)
            write_log("Legend positioned at X:{0}, Y:{1}".format(legend_x, legend_y))
            
            if has_layer_groups:
                pdb.gimp_image_reorder_item(img, text_layer, parent_layer, 0)
        except Exception as e:
            write_log("Error adding legend: {0}".format(e))
    
    # Logo
    if logo_folder_path and isinstance(logo_folder_path, str) and len(logo_folder_path) > 0:
        try:
            if os.path.exists(logo_folder_path):
                logo_layer = pdb.gimp_file_load_layer(img, logo_folder_path)
                img.add_layer(logo_layer, 0)
                pdb.gimp_item_set_name(logo_layer, "Logo")
                if has_layer_groups:
                    pdb.gimp_image_reorder_item(img, logo_layer, parent_layer, 0)
                
                # Utiliser l'espace disponible au-dessus des cellules avec une marge de sécurité
                available_top_space = first_cell_y
                logo_margin = max(15, MIN_LOGO_MARGIN * 0.25)  # Marge minimale du haut
                target_height = safe_int(available_top_space * 0.6)  # 60% de l'espace disponible
                
                resize_percent = safe_float(target_height / float(logo_layer.height))
                pdb.gimp_layer_scale(logo_layer, safe_int(logo_layer.width * resize_percent), safe_int(logo_layer.height * resize_percent), True)
                
                # Centrer le logo verticalement dans l'espace disponible
                new_x = safe_int(first_cell_x)
                new_y = safe_int(logo_margin + (available_top_space - logo_layer.height - logo_margin) / 2)
                new_y = max(safe_int(logo_margin), new_y)  # S'assurer de ne pas dépasser en haut
                
                pdb.gimp_layer_set_offsets(logo_layer, new_x, new_y)
                write_log("Logo positioned at X:{0}, Y:{1}".format(new_x, new_y))
        except Exception as e:
            write_log("Error adding logo: {0}".format(e))
    
    # Size info
    try:
        size_info_text = "Img max size w x h : {0} x {1} px".format(max_width, max_height)
        parent_for_info = board_content_group if has_layer_groups else board_content_layer
        size_info_layer = pdb.gimp_text_fontname(img, None, 10, 10, size_info_text, 0, True, 12, PIXELS, "Sans")
        pdb.gimp_item_set_name(size_info_layer, size_info_text)
        if has_layer_groups:
            pdb.gimp_image_reorder_item(img, size_info_layer, parent_for_info, 0)
    except Exception as e:
        write_log("Error creating size info: {0}".format(e))
    
    # Write overlay metadata
    if overlay_files and overlay_indexes:
        write_overlay_metadata_to_dit(dit_path, overlay_files, overlay_indexes)
    
    # Save
    try:
        pdb.gimp_xcf_save(0, img, img.layers[0], xcf_path, xcf_path)
        pdb.gimp_image_clean_all(img)
        pdb.gimp_image_set_filename(img, xcf_path)
    except Exception as e:
        write_log("Error saving: {0}".format(e))
    
    pdb.gimp_display_new(img)
    return img

# Register
register(
    "Open_Board",
    "Open Board - Create a board layout",
    "Creates an optimized layout with cells for placing images",
    "Yan Senez",
    "Yan Senez",
    "2025",
    "<Toolbox>/File/Open Board/1.Create Board...",
    "",
    [
        (PF_STRING, "board_name", "─────────── 📋 PROJECT ───────────\nBoard Name", "MyBoard"),
        (PF_DIRNAME, "dest_folder", "Destination Folder", ""),
        (PF_OPTION, "layout_units", "─────────── 📐 CANVAS ───────────\nCanvas Units", 0, ("px", "mm", "cm", "in", "pt")),
        (PF_FLOAT, "layout_resolution", "Resolution (DPI)", 300),
        (PF_FLOAT, "layout_width", "Canvas Width", 4961),
        (PF_FLOAT, "layout_height", "Canvas Height", 3508),
        (PF_INT, "nbr_col", "─────────── 🔲 GRID ───────────\nColumns", 3),
        (PF_INT, "nbr_row", "Rows", 4),
        (PF_OPTION, "cell_type", "Cell Type", 1, ("single", "spread")),
        (PF_OPTION, "cell_units", "Cell Units", 2, ("px", "mm", "cm", "in", "pt")),
        (PF_FLOAT, "cell_width", "Cell Width", 80),
        (PF_FLOAT, "cell_height", "Cell Height", 50),
        (PF_FLOAT, "margin_mask", "Margin", 2),
        (PF_OPTION, "spacing_units", "Spacing Units", 1, ("px", "mm", "cm", "in", "pt")),
        (PF_FLOAT, "layout_spacing", "Spacing", 40),
        (PF_COLOR, "bg_color_hex", "─────────── 🎨 COLORS ───────────\nBackground", (255, 255, 255)),
        (PF_COLOR, "border_color_hex", "Border", (200, 200, 200)),
        (PF_COLOR, "layout_color_hex", "Layout Mask", (0, 0, 0)),
        (PF_STRING, "baseline_text", "─────────── ✏️  LEGEND ───────────\nText", "My Board"),
        (PF_FONT, "selected_font", "Font", "Sans"),
        (PF_FLOAT, "baseline_text_size", "Size", 36),
        (PF_COLOR, "baseline_text_color_hex", "Color", (255, 255, 255)),
        (PF_FILE, "logo_folder_path", "Logo File", ""),
        (PF_TOGGLE, "overlay_mask_on", "─────────── 🎭 OVERLAY ───────────\nEnable", False),
        (PF_FILE, "overlay_file_path", "File", ""),
        (PF_DIRNAME, "overlay_folder_path", "Folder", ""),
        (PF_TOGGLE, "should_create_guides", "─────────── ⚙️  OPTIONS ───────────\nGuides", False),
    ],
    [],
    create_board_layout
)

main()