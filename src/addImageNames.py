#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Add Image Names - GIMP Script
# By Yan Senez
# Version 1.1 - Improved with security fixes and refactoring

from gimpfu import *
import os
import time

# ============================================================================
# CONSTANTS
# ============================================================================

ENABLE_LOGS = True  # Activer/désactiver l'écriture des logs
POSITION_TOLERANCE = 10  # pixels tolerance for position matching

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

log_file_path = None

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def write_log(message):
    """Write log message"""
    if not ENABLE_LOGS:
        return
    
    global log_file_path
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    full_message = "{0} - {1}".format(timestamp, message)
    
    print(full_message)
    
    if log_file_path:
        try:
            with open(log_file_path, 'a') as f:
                f.write(full_message + '\n')
        except Exception as e:
            print("Error writing log: {0}".format(e))

def remove_file_extension(filename):
    """Remove file extension from filename"""
    last_dot = filename.rfind('.')
    if last_dot == -1:
        return filename
    return filename[:last_dot]

def convert_color_to_rgb(color_param):
    """Convert GIMP color parameter to RGB tuple (0-255)"""
    try:
        if hasattr(color_param, 'r') and hasattr(color_param, 'g') and hasattr(color_param, 'b'):
            r = int(color_param.r * 255)
            g = int(color_param.g * 255)
            b = int(color_param.b * 255)
            return (r, g, b)
        elif isinstance(color_param, (tuple, list)) and len(color_param) >= 3:
            return (int(color_param[0]), int(color_param[1]), int(color_param[2]))
        else:
            return (0, 0, 0)
    except Exception as e:
        write_log("Error converting color: {0}".format(e))
        return (0, 0, 0)

# ============================================================================
# BOARD FILE READING
# ============================================================================

def read_dit_file(dit_path):
    """Read .board file and extract cell coordinates"""
    write_log("Reading BOARD file: {0}".format(dit_path))
    
    if not os.path.exists(dit_path):
        write_log("ERROR: BOARD file not found: {0}".format(dit_path))
        return None
    
    cells = []
    metadata = {}
    
    try:
        with open(dit_path, 'r') as f:
            for line in f:
                line = line.strip()
                
                if not line:
                    continue
                
                if line.startswith('#'):
                    parts = line[1:].split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        metadata[key] = value
                else:
                    parts = line.split(',')
                    if len(parts) == 9:
                        cell = {
                            'index': int(parts[0]),
                            'topLeft': (float(parts[1]), float(parts[2])),
                            'bottomLeft': (float(parts[3]), float(parts[4])),
                            'bottomRight': (float(parts[5]), float(parts[6])),
                            'topRight': (float(parts[7]), float(parts[8]))
                        }
                        cells.append(cell)
        
        write_log("Successfully read {0} cells from BOARD file".format(len(cells)))
        return {'cells': cells, 'metadata': metadata}
    except Exception as e:
        write_log("ERROR reading BOARD file: {0}".format(e))
        return None

# ============================================================================
# ROW/COLUMN CALCULATION
# ============================================================================

def calculate_row_col_from_position(cell, all_cells):
    """Calculate row and column from cell position
    
    This handles boards that have been extended and don't follow
    simple row-major ordering anymore.
    
    Args:
        cell: Current cell dict with position info
        all_cells: List of all cells in the board
        
    Returns:
        tuple: (row, col) both 1-based
    """
    try:
        # Get all unique Y positions (rows) and X positions (columns)
        unique_y_positions = sorted(set(c['topLeft'][1] for c in all_cells))
        unique_x_positions = sorted(set(c['topLeft'][0] for c in all_cells))
        
        # Create mappings from position to row/col number
        y_to_row = {y: idx + 1 for idx, y in enumerate(unique_y_positions)}
        x_to_col = {x: idx + 1 for idx, x in enumerate(unique_x_positions)}
        
        # Get current cell's position
        current_y = cell['topLeft'][1]
        current_x = cell['topLeft'][0]
        
        # Find matching row and column
        row = y_to_row.get(current_y)
        col = x_to_col.get(current_x)
        
        # If exact match not found, try with tolerance
        if row is None:
            for y_pos in unique_y_positions:
                if abs(y_pos - current_y) < POSITION_TOLERANCE:
                    row = y_to_row[y_pos]
                    break
        
        if col is None:
            for x_pos in unique_x_positions:
                if abs(x_pos - current_x) < POSITION_TOLERANCE:
                    col = x_to_col[x_pos]
                    break
        
        if row is None or col is None:
            write_log("WARNING: Could not determine row/col from position")
            return (None, None)
        
        write_log("Cell {0} mapped to R{1}C{2}".format(cell['index'], row, col))
        return (row, col)
        
    except Exception as e:
        write_log("ERROR calculating row/col: {0}".format(e))
        return (None, None)

# ============================================================================
# TEXT POSITIONING
# ============================================================================

def calculate_text_position(cell, cell_type, layer_info, text_offset):
    """Calculate position for text below image
    
    Args:
        cell: Cell dict with coordinates
        cell_type: 'single' or 'spread'
        layer_info: Dict with layer position and dimensions
        text_offset: User-specified offset from cell bottom
        
    Returns:
        tuple: (center_x, pos_y) for text placement
    """
    cell_left = cell['topLeft'][0]
    cell_right = cell['topRight'][0]
    cell_bottom = cell['bottomLeft'][1]
    cell_width = cell_right - cell_left
    
    # Y position is always below the cell
    pos_y = cell_bottom + text_offset
    
    # X position depends on cell type and image position
    if cell_type.lower() == "spread":
        # In spread mode, determine if image is on left or right
        cell_center_x = cell_left + (cell_width / 2)
        
        if layer_info['center_x'] < cell_center_x:
            # Image on left
            center_x = cell_left + (cell_width / 4)
            write_log("Spread mode: centering text under LEFT side")
        else:
            # Image on right
            center_x = cell_left + (3 * cell_width / 4)
            write_log("Spread mode: centering text under RIGHT side")
    else:
        # In single mode, center over entire cell
        center_x = (cell_left + cell_right) / 2
        write_log("Single mode: centering text under cell")
    
    return (center_x, pos_y)

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def add_image_names_to_board(img, drawable, text_font, text_size, text_color, text_offset):
    """Main function to add image names under cells
    
    Parameters:
    - img: Active GIMP image
    - drawable: Active layer
    - text_font: Font to use
    - text_size: Text size in pixels
    - text_color: Text color (gimpcolor.RGB object or tuple)
    - text_offset: Distance between cell bottom and text in pixels
    """
    global log_file_path
    
    try:
        write_log("====== Starting Add Image Names for GIMP ======")
        
        # Convert color to RGB (0-255)
        rgb_color = convert_color_to_rgb(text_color)
        write_log("Text settings - Font: {0}, Size: {1}, Color: RGB{2}, Offset: {3}px".format(
            text_font, text_size, rgb_color, text_offset))
        
        # Get XCF file path
        xcf_path = pdb.gimp_image_get_filename(img)
        if not xcf_path:
            pdb.gimp_message("Please save the document first")
            write_log("ERROR: Document not saved")
            return
        
        write_log("Document path: {0}".format(xcf_path))
        
        # Build .board file path
        board_dir = os.path.dirname(xcf_path)
        board_name = os.path.splitext(os.path.basename(xcf_path))[0]
        dit_path = os.path.join(board_dir, "{0}.board".format(board_name))
        
        # Initialize log
        log_file_path = os.path.join(board_dir, "{0}_add_names.log".format(board_name))
        
        write_log("BOARD file path: {0}".format(dit_path))
        
        # Check if .board file exists
        if not os.path.exists(dit_path):
            pdb.gimp_message("Board file not found. Please open a valid board XCF file.")
            write_log("ERROR: BOARD file not found")
            return
        
        # Read .board file
        board_data = read_dit_file(dit_path)
        if not board_data:
            pdb.gimp_message("Error reading board file")
            return
        
        # Get metadata
        adjusted_margin = float(board_data['metadata'].get('adjustedMargin', 0))
        adjusted_spacing = float(board_data['metadata'].get('adjustedSpacing', 40))
        
        write_log("Using adjustedMargin: {0}, adjustedSpacing: {1}".format(
            adjusted_margin, adjusted_spacing))
        
        # Find Board Elements and Board Content groups
        board_elements_group = None
        board_content_group = None
        
        for layer in img.layers:
            if pdb.gimp_item_is_group(layer):
                layer_name = pdb.gimp_item_get_name(layer)
                if layer_name == "Board Elements":
                    board_elements_group = layer
                elif layer_name == "Board Content":
                    board_content_group = layer
        
        if not board_elements_group:
            pdb.gimp_message("'Board Elements' group not found")
            write_log("ERROR: Board Elements group not found")
            return
        
        if not board_content_group:
            pdb.gimp_message("'Board Content' group not found")
            write_log("ERROR: Board Content group not found")
            return
        
        # Remove existing Image Names group if it exists
        write_log("Checking for existing 'Image Names' group to remove...")
        group_found = False
        try:
            if hasattr(board_elements_group, 'children') and board_elements_group.children:
                for child in board_elements_group.children:
                    child_name = pdb.gimp_item_get_name(child)
                    if child_name == "Image Names":
                        write_log("Found existing 'Image Names' group - removing it")
                        pdb.gimp_image_remove_layer(img, child)
                        group_found = True
                        write_log("Existing 'Image Names' group removed successfully")
                        break
        except Exception as e:
            write_log("Error while checking for existing Image Names group: {0}".format(e))
        
        if not group_found:
            write_log("No existing 'Image Names' group found")
        
        # Create new Image Names group
        write_log("Creating new 'Image Names' group...")
        image_names_group = pdb.gimp_layer_group_new(img)
        pdb.gimp_item_set_name(image_names_group, "Image Names")
        pdb.gimp_image_insert_layer(img, image_names_group, board_elements_group, 0)
        write_log("New 'Image Names' group created successfully")
        
        # Collect all image layers in Board Content with their positions
        content_layers = []
        
        if hasattr(board_content_group, 'children') and board_content_group.children:
            for child in board_content_group.children:
                if not pdb.gimp_item_is_group(child):
                    # Get layer offsets and dimensions
                    offsets = pdb.gimp_drawable_offsets(child)
                    width = pdb.gimp_drawable_width(child)
                    height = pdb.gimp_drawable_height(child)
                    
                    layer_info = {
                        'layer': child,
                        'name': pdb.gimp_item_get_name(child),
                        'left': offsets[0],
                        'top': offsets[1],
                        'right': offsets[0] + width,
                        'bottom': offsets[1] + height,
                        'center_x': offsets[0] + (width / 2),
                        'center_y': offsets[1] + (height / 2)
                    }
                    content_layers.append(layer_info)
        
        write_log("Found {0} image layers in Board Content".format(len(content_layers)))
        
        # Sort layers by Y then X position
        content_layers.sort(key=lambda x: (x['top'], x['left']))
        
        # Get cells from .board file
        cells = board_data.get('cells', [])
        write_log("Found {0} cells in board data".format(len(cells)))
        
        # Get cell type from metadata
        cell_type = board_data['metadata'].get('cellType', 'single')
        write_log("Board cell type: {0}".format(cell_type))
        
        # Start undo group
        pdb.gimp_image_undo_group_start(img)
        
        write_log("Starting to process {0} image layers...".format(len(content_layers)))
        
        # Process all sorted layers
        for i, layer_info in enumerate(content_layers):
            write_log("Processing layer {0}/{1}: {2}".format(
                i + 1, len(content_layers), layer_info['name']))
            
            # Extract file name (without extension)
            file_name = remove_file_extension(layer_info['name'])
            
            # Find matching cell for this image
            # Use image center to determine which cell it belongs to
            matching_cell = None
            for cell in cells:
                cell_left = cell['topLeft'][0]
                cell_top = cell['topLeft'][1]
                cell_right = cell['topRight'][0]
                cell_bottom = cell['bottomLeft'][1]
                
                # Check if image center is in this cell
                if (layer_info['center_x'] >= cell_left and 
                    layer_info['center_x'] <= cell_right and
                    layer_info['center_y'] >= cell_top and 
                    layer_info['center_y'] <= cell_bottom):
                    matching_cell = cell
                    write_log("Image '{0}' matched to cell {1}".format(file_name, cell['index']))
                    break
            
            if not matching_cell:
                write_log("WARNING: No matching cell found for image '{0}', skipping".format(file_name))
                continue
            
            # Calculate text position UNDER the image
            center_x, pos_y = calculate_text_position(
                matching_cell, cell_type, layer_info, text_offset)
            
            write_log("Creating text '{0}' at position ({1}, {2})".format(
                file_name, int(center_x), int(pos_y)))
            
            # Create text layer
            text_layer = pdb.gimp_text_fontname(
                img, None, 
                center_x, pos_y,
                file_name,
                0,  # border
                True,  # antialias
                text_size,
                PIXELS,
                text_font
            )
            
            # Set text color
            pdb.gimp_text_layer_set_color(text_layer, rgb_color)
            
            # Center text horizontally
            text_width = pdb.gimp_drawable_width(text_layer)
            new_x = int(center_x - (text_width / 2))
            pdb.gimp_layer_set_offsets(text_layer, new_x, int(pos_y))
            
            # Move layer into Image Names group
            pdb.gimp_image_reorder_item(img, text_layer, image_names_group, 0)
        
        # End undo group
        pdb.gimp_image_undo_group_end(img)
        
        # Refresh display
        pdb.gimp_displays_flush()
        
        write_log("====== Add Image Names completed successfully ======")
        write_log("Total images processed: {0}".format(len(content_layers)))
        
        # Auto-save XCF file
        try:
            write_log("Auto-saving XCF file")
            pdb.gimp_xcf_save(0, img, img.layers[0], xcf_path, xcf_path)
            pdb.gimp_image_clean_all(img)
            write_log("XCF file saved successfully")
        except Exception as save_error:
            write_log("ERROR saving XCF: {0}".format(save_error))
        
        # pdb.gimp_message("Image names added successfully! ({0} images)".format(len(content_layers)))
        
    except Exception as e:
        write_log("ERROR in add_image_names_to_board: {0}".format(e))
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()))
        # pdb.gimp_message("Error adding image names: {0}".format(e))
        
        # End undo group on error
        try:
            pdb.gimp_image_undo_group_end(img)
        except:
            pass

# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

register(
    "python_fu_board_add_image_names",
    "Open Board - Add image names under cells",
    "Add image file names as text layers under each image in the board layout. Customize font, size, and color of the text.",
    "Yan Senez",
    "Yan Senez",
    "2025",
    "<Image>/File/Open Board/3.Add Image Names...",
    "RGB*, GRAY*",
    [
        (PF_FONT, "text_font", "─────────── ✏️  TEXT SETTINGS ───────────\nFont", "Sans"),
        (PF_FLOAT, "text_size", "Text Size (px)", 25.0),
        (PF_COLOR, "text_color", "Text Color", (255, 255, 255)),
        (PF_FLOAT, "text_offset", "Distance from Cell (px)", 20.0)
    ],
    [],
    add_image_names_to_board
)

main()