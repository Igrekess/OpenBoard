#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Import Open Board - GIMP Script
# By Yan Senez
# Version 1.1 - Improved with security fixes and refactoring

from gimpfu import *
import os
import math
import time
import glob
import json

# Import du module commun OpenBoard
from openboard_common import (
    write_log, safe_float, safe_int,
    find_overlay_files, get_image_orientation, create_guide,
    calculate_overlay_dimensions, place_overlay_in_cell,
    get_overlay_index_for_cell,
    build_layer_bounds_cache, check_cell_occupancy_optimized,
    find_empty_cell_cached,
    ENABLE_LOGS, IMAGE_EXTENSIONS, DEFAULT_DPI,
    POSITION_TOLERANCE, MIN_LAYER_SIZE,
    CENTER_TOLERANCE_RATIO, WIDE_IMAGE_THRESHOLD,
    VERY_WIDE_IMAGE_THRESHOLD
)

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

log_file_path = None  # Chemin du fichier log pour cette session

def save_last_cell_index(board_path, cell_index):
    """Save last cell index"""
    try:
        board_dir = os.path.dirname(board_path)
        board_name = os.path.splitext(os.path.basename(board_path))[0]
        index_file = os.path.join(board_dir, "{0}_last_cell.txt".format(board_name))
        
        with open(index_file, "w") as f:
            f.write(str(cell_index))
        write_log("Saved last cell index: {0}".format(cell_index))
    except Exception as e:
        write_log("ERROR saving last cell index: {0}".format(e))

def load_last_cell_index(board_path):
    """Load last cell index"""
    try:
        board_dir = os.path.dirname(board_path)
        board_name = os.path.splitext(os.path.basename(board_path))[0]
        index_file = os.path.join(board_dir, "{0}_last_cell.txt".format(board_name))
        
        if os.path.exists(index_file):
            with open(index_file, "r") as f:
                index = int(f.read().strip())
            write_log("Loaded last cell index: {0}".format(index))
            return index
        return 0
    except Exception as e:
        write_log("ERROR loading last cell index: {0}".format(e))
        return 0

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
    overlay_files = []
    
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
                        
                        if key == 'overlayFiles':
                            try:
                                overlay_files = json.loads(value)
                                write_log("Found {0} overlay files".format(len(overlay_files)))
                            except Exception as e:
                                write_log("ERROR parsing overlayFiles: {0}".format(e))
                        else:
                            metadata[key] = value
                else:
                    parts = line.split(',')
                    if len(parts) == 9:
                        top_left_x = float(parts[1])
                        top_left_y = float(parts[2])
                        bottom_right_x = float(parts[5])
                        bottom_right_y = float(parts[6])
                        
                        cell = {
                            'index': int(parts[0]),
                            'topLeft': (top_left_x, top_left_y),
                            'bottomLeft': (float(parts[3]), float(parts[4])),
                            'bottomRight': (bottom_right_x, bottom_right_y),
                            'topRight': (float(parts[7]), float(parts[8])),
                            'minX': top_left_x,
                            'minY': top_left_y,
                            'maxX': bottom_right_x,
                            'maxY': bottom_right_y
                        }
                        cells.append(cell)
        
        write_log("Successfully read {0} cells".format(len(cells)))
        return {'cells': cells, 'metadata': metadata, 'overlay_files': overlay_files}
    except Exception as e:
        write_log("ERROR reading BOARD file: {0}".format(e))
        return None

# ============================================================================
# IMAGE PLACEMENT FUNCTIONS
# ============================================================================

def load_and_resize_image(image_path, target_width, target_height, resize_mode):
    """Load and resize image according to mode
    
    Returns: (layer, final_width, final_height)
    """
    try:
        loaded_image = pdb.gimp_file_load(image_path, image_path)
        source_layer = loaded_image.active_layer if loaded_image.active_layer else loaded_image.layers[0]
        
        img_width = source_layer.width
        img_height = source_layer.height
        
        if resize_mode == "noResize":
            final_width = img_width
            final_height = img_height
        else:
            width_ratio = float(target_width) / float(img_width)
            height_ratio = float(target_height) / float(img_height)
            
            if resize_mode == "cover":
                ratio = max(width_ratio, height_ratio)
            else:  # fit
                ratio = min(width_ratio, height_ratio)
            
            final_width = int(img_width * ratio)
            final_height = int(img_height * ratio)
            pdb.gimp_layer_scale(source_layer, final_width, final_height, True)
        
        return (loaded_image, source_layer, final_width, final_height)
    except Exception as e:
        write_log("ERROR loading image: {0}".format(e))
        return (None, None, 0, 0)

def calculate_position(cell, cell_type, final_width, final_height, use_side):
    """Calculate target position for image
    
    Returns: (target_x, target_y)
    """
    cell_left = cell['minX']
    cell_top = cell['minY']
    cell_width = cell['maxX'] - cell['minX']
    cell_height = cell['maxY'] - cell['minY']
    
    if cell_type.lower() == "single":
        target_x = cell_left + (cell_width - final_width) / 2
        target_y = cell_top + (cell_height - final_height) / 2
    else:  # spread
        orientation = "Landscape" if final_width > final_height else "Portrait"
        if orientation == "Landscape":
            target_x = cell_left + (cell_width - final_width) / 2
            target_y = cell_top + (cell_height - final_height) / 2
        else:  # Portrait
            half_width = cell_width / 2
            if use_side == "left":
                target_x = cell_left + (half_width - final_width) / 2
            else:
                target_x = cell_left + half_width + (half_width - final_width) / 2
            target_y = cell_top + (cell_height - final_height) / 2
    
    return (int(target_x), int(target_y))

def create_cell_mask(img, new_layer, cell, cell_type, use_side):
    """Create mask for image layer"""
    try:
        cell_left = cell['minX']
        cell_top = cell['minY']
        cell_right = cell['maxX']
        cell_bottom = cell['maxY']
        cell_width = cell_right - cell_left
        
        if cell_type.lower() == "single":
            mask_left = cell_left
            mask_top = cell_top
            mask_right = cell_right
            mask_bottom = cell_bottom
        else:  # spread
            layer_width = pdb.gimp_drawable_width(new_layer)
            orientation = "Landscape" if layer_width > (cell_width * 0.6) else "Portrait"
            
            if orientation == "Landscape":
                mask_left = cell_left
                mask_top = cell_top
                mask_right = cell_right
                mask_bottom = cell_bottom
            else:  # Portrait
                half_width = cell_width / 2
                if use_side == "left":
                    mask_left = cell_left
                    mask_right = cell_left + half_width
                else:
                    mask_left = cell_left + half_width
                    mask_right = cell_right
                mask_top = cell_top
                mask_bottom = cell_bottom
        
        mask = pdb.gimp_layer_create_mask(new_layer, ADD_ALPHA_MASK)
        pdb.gimp_layer_add_mask(new_layer, mask)
        
        pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE, 
            int(mask_left), int(mask_top), 
            int(mask_right - mask_left), int(mask_bottom - mask_top))
        
        pdb.gimp_context_set_foreground((255, 255, 255))
        pdb.gimp_edit_fill(mask, FILL_FOREGROUND)
        pdb.gimp_selection_none(img)
        
        write_log("Mask created successfully")
        return True
    except Exception as e:
        write_log("WARNING: Could not create mask: {0}".format(e))
        return False

def update_simple_page_mask(img, cell, cell_type, all_cells, board_metadata, orientation):
    """Update Simple page Mask visibility"""
    if cell_type.lower() != "spread":
        return
    
    try:
        board_elements_group = None
        for layer in img.layers:
            if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Elements":
                board_elements_group = layer
                break
        
        if not board_elements_group:
            return
        
        if not pdb.gimp_item_get_visible(board_elements_group):
            pdb.gimp_item_set_visible(board_elements_group, True)
        
        simple_page_group = None
        for child in board_elements_group.children:
            if pdb.gimp_item_is_group(child) and pdb.gimp_item_get_name(child) == "Simple page Mask":
                simple_page_group = child
                break
        
        if not simple_page_group:
            return
        
        if not pdb.gimp_item_get_visible(simple_page_group):
            pdb.gimp_item_set_visible(simple_page_group, True)
        
        # Calculate row/col from position
        unique_y_positions = sorted(set(c['minY'] for c in all_cells))
        unique_x_positions = sorted(set(c['minX'] for c in all_cells))
        
        y_to_row = {y: idx + 1 for idx, y in enumerate(unique_y_positions)}
        x_to_col = {x: idx + 1 for idx, x in enumerate(unique_x_positions)}
        
        current_y = cell['minY']
        current_x = cell['minX']
        
        row = y_to_row.get(current_y)
        col = x_to_col.get(current_x)
        
        if row is None or col is None:
            # Fallback with tolerance
            for y_pos in unique_y_positions:
                if abs(y_pos - current_y) < POSITION_TOLERANCE:
                    row = y_to_row[y_pos]
                    break
            for x_pos in unique_x_positions:
                if abs(x_pos - current_x) < POSITION_TOLERANCE:
                    col = x_to_col[x_pos]
                    break
        
        if row is None or col is None:
            # Final fallback
            nbr_cols = int(board_metadata.get('nbrCols', 3))
            cell_index = cell['index']
            row = ((cell_index - 1) // nbr_cols) + 1
            col = ((cell_index - 1) % nbr_cols) + 1
        
        mask_id = "R{0}C{1}".format(row, col)
        write_log("Looking for mask: {0}".format(mask_id))
        
        for child in simple_page_group.children:
            if not pdb.gimp_item_is_group(child) and pdb.gimp_item_get_name(child) == mask_id:
                should_enable = (orientation == "Portrait")
                pdb.gimp_item_set_visible(child, should_enable)
                write_log("Mask {0} visibility: {1}".format(mask_id, should_enable))
                break
    except Exception as e:
        write_log("WARNING: Could not update mask: {0}".format(e))

def place_image_in_cell(img, image_path, cell, cell_type, resize_mode, board_metadata, all_cells, use_side="left", should_create_guides=False):
    """Place image in cell - main function"""
    write_log("====== Placing image in cell {0} ======".format(cell['index']))
    write_log("Image: {0}".format(image_path))
    
    try:
        cell_width = int(cell['maxX'] - cell['minX'])
        cell_height = int(cell['maxY'] - cell['minY'])
        cell_left = int(cell['minX'])
        cell_top = int(cell['minY'])
        
        margin_size = safe_float(board_metadata.get('adjustedMargin', 0))
        
        # Determine target dimensions
        if cell_type.lower() == "single":
            target_width = cell_width - (2 * margin_size)
            target_height = cell_height - (2 * margin_size)
        else:  # spread
            orientation = get_image_orientation(image_path)
            if orientation == "Landscape":
                target_width = cell_width - (2 * margin_size)
                target_height = cell_height - (2 * margin_size)
            else:
                target_width = (cell_width / 2) - (2 * margin_size)
                target_height = cell_height - (2 * margin_size)
        
        # Load and resize
        loaded_image, source_layer, final_width, final_height = load_and_resize_image(
            image_path, target_width, target_height, resize_mode)
        
        if not loaded_image:
            return False
        
        # Copy to destination
        new_layer = pdb.gimp_layer_new_from_drawable(source_layer, img)
        pdb.gimp_image_insert_layer(img, new_layer, None, 0)
        
        layer_name = os.path.splitext(os.path.basename(image_path))[0]
        pdb.gimp_item_set_name(new_layer, layer_name)
        
        # Calculate and set position
        target_x, target_y = calculate_position(cell, cell_type, final_width, final_height, use_side)
        pdb.gimp_layer_set_offsets(new_layer, target_x, target_y)
        
        # Create mask
        create_cell_mask(img, new_layer, cell, cell_type, use_side)
        
        # Update simple page mask
        orientation = "Landscape" if final_width > final_height else "Portrait"
        update_simple_page_mask(img, cell, cell_type, all_cells, board_metadata, orientation)
        
        # Create guides if requested
        if should_create_guides:
            try:
                write_log("Creating guides for cell")
                # Cell borders
                create_guide(img, cell_left, "vertical")
                create_guide(img, cell_left + cell_width, "vertical")
                create_guide(img, cell_top, "horizontal")
                create_guide(img, cell_top + cell_height, "horizontal")
                
                # Margins
                if margin_size > 0:
                    create_guide(img, int(cell_left + margin_size), "vertical")
                    create_guide(img, int(cell_left + cell_width - margin_size), "vertical")
                    create_guide(img, int(cell_top + margin_size), "horizontal")
                    create_guide(img, int(cell_top + cell_height - margin_size), "horizontal")
                
                # Center guide for spread cells
                if cell_type.lower() == "spread":
                    create_guide(img, int(cell_left + cell_width / 2), "vertical")
                
                write_log("Guides created successfully")
            except Exception as guide_error:
                write_log("WARNING: Could not create guides: {0}".format(guide_error))
        
        # Move to Board Content group
        board_content_group = None
        for layer in img.layers:
            if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Content":
                board_content_group = layer
                break
        
        if board_content_group:
            pdb.gimp_image_reorder_item(img, new_layer, board_content_group, 0)
        
        pdb.gimp_image_delete(loaded_image)
        
        write_log("====== Image placed successfully ======")
        return True
        
    except Exception as e:
        write_log("ERROR placing image: {0}".format(e))
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()))
        return False

# ============================================================================
# CELL OCCUPANCY DETECTION - Utilise le cache de openboard_common
# ============================================================================

# NOTE: Les fonctions check_cell_occupancy() et find_empty_cell() ont été
# remplacées par check_cell_occupancy_optimized() et find_empty_cell_cached()
# du module openboard_common pour des gains de performance 10-15x

# ============================================================================
# BOARD EXTENSION
# ============================================================================

def extend_board(img, dit_path, cells, metadata, extension_direction, cell_type, overlay_files=None):
    """Extend board by adding row or column"""
    try:
        write_log("====== Extending board ======")
        write_log("Current cells: {0}".format(len(cells)))
        write_log("Direction: {0}".format(["Bottom", "Right", "Alternate"][extension_direction]))
        
        nbr_cols = int(metadata.get('nbrCols', 3))
        nbr_rows = int(metadata.get('nbrRows', 4))
        
        # Calculate spacing from existing cells
        layout_spacing = 40.0
        if len(cells) >= 2:
            cells_sorted = sorted(cells, key=lambda c: (c['minY'], c['minX']))
            for i in range(len(cells_sorted) - 1):
                cell1 = cells_sorted[i]
                cell2 = cells_sorted[i + 1]
                if abs(cell1['minY'] - cell2['minY']) < POSITION_TOLERANCE:
                    spacing_x = cell2['minX'] - cell1['maxX']
                    if spacing_x > 0:
                        layout_spacing = spacing_x
                        break
        
        write_log("Using spacing: {0}px".format(layout_spacing))
        
        # Get border color
        border_color = (200, 200, 200)
        
        # Determine effective direction
        effective_direction = extension_direction
        alternate_pref_file = None
        
        if extension_direction == 2:  # Alternate
            board_dir = os.path.dirname(dit_path)
            alternate_pref_file = os.path.join(board_dir, "extension_direction.txt")
            
            last_direction = None
            if os.path.exists(alternate_pref_file):
                try:
                    with open(alternate_pref_file, 'r') as f:
                        last_direction = f.read().strip()
                except:
                    pass
            
            if last_direction == "Right":
                effective_direction = 0  # Bottom
            else:
                effective_direction = 1  # Right
            
            write_log("Alternate mode: using {0}".format(["Bottom", "Right"][effective_direction]))
        
        # Calculate dimensions
        max_x = max(cell['maxX'] for cell in cells)
        max_y = max(cell['maxY'] for cell in cells)
        cell_width = cells[0]['maxX'] - cells[0]['minX']
        cell_height = cells[0]['maxY'] - cells[0]['minY']
        
        new_cells = []
        old_width = pdb.gimp_image_width(img)
        old_height = pdb.gimp_image_height(img)
        
        if effective_direction == 1:  # Right
            new_col_x = max_x + layout_spacing
            row_positions = sorted(set(cell['minY'] for cell in cells))
            
            for i, row_y in enumerate(row_positions):
                cell_row = i + 1
                cell_col = nbr_cols + 1
                new_cell = {
                    'index': len(cells) + i + 1,
                    'topLeft': (new_col_x, row_y),
                    'bottomLeft': (new_col_x, row_y + cell_height),
                    'bottomRight': (new_col_x + cell_width, row_y + cell_height),
                    'topRight': (new_col_x + cell_width, row_y),
                    'minX': new_col_x,
                    'maxX': new_col_x + cell_width,
                    'minY': row_y,
                    'maxY': row_y + cell_height,
                    'row': cell_row,
                    'col': cell_col
                }
                new_cells.append(new_cell)
            
            new_width = int(old_width + cell_width + layout_spacing)
            new_height = old_height
            nbr_cols += 1
        else:  # Bottom
            new_row_y = max_y + layout_spacing
            col_positions = sorted(set(cell['minX'] for cell in cells))
            
            for i, col_x in enumerate(col_positions):
                cell_row = nbr_rows + 1
                cell_col = i + 1
                new_cell = {
                    'index': len(cells) + i + 1,
                    'topLeft': (col_x, new_row_y),
                    'bottomLeft': (col_x, new_row_y + cell_height),
                    'bottomRight': (col_x + cell_width, new_row_y + cell_height),
                    'topRight': (col_x + cell_width, new_row_y),
                    'minX': col_x,
                    'maxX': col_x + cell_width,
                    'minY': new_row_y,
                    'maxY': new_row_y + cell_height,
                    'row': cell_row,
                    'col': cell_col
                }
                new_cells.append(new_cell)
            
            new_width = old_width
            new_height = int(old_height + cell_height + layout_spacing)
            nbr_rows += 1
        
        write_log("New dimensions: {0}x{1}".format(new_width, new_height))
        
        # Resize canvas
        pdb.gimp_image_resize(img, new_width, new_height, 0, 0)
        
        # Find existing layers to update
        write_log("Finding existing layers to update...")
        board_elements_group = None
        mask_layer = None
        borders_layer = None
        gutters_layer = None
        simple_page_group = None
        background_layer = None
        overlay_group = None
        structure_layers_to_resize = []
        
        # Find Board Elements group and its sub-layers + Background
        for layer in img.layers:
            layer_name = pdb.gimp_item_get_name(layer)
            
            # Find Background layer
            if layer_name == "Background":
                background_layer = layer
                structure_layers_to_resize.append(layer)
                write_log("Found Background layer")
            
            # Find Board Elements group
            if pdb.gimp_item_is_group(layer):
                if layer_name == "Board Elements":
                    board_elements_group = layer
                    write_log("Found Board Elements group")
                    
                    # Find sub-layers
                    for child in layer.children:
                        child_name = pdb.gimp_item_get_name(child)
                        if child_name == "Mask":
                            mask_layer = child
                            structure_layers_to_resize.append(child)
                            write_log("Found Mask layer")
                        elif child_name == "Borders":
                            borders_layer = child
                            structure_layers_to_resize.append(child)
                            write_log("Found Borders layer")
                        elif child_name == "Gutters":
                            gutters_layer = child
                            structure_layers_to_resize.append(child)
                            write_log("Found Gutters layer")
                        elif pdb.gimp_item_is_group(child) and child_name == "Simple page Mask":
                            simple_page_group = child
                            write_log("Found Simple page Mask group")
                            # Add all individual masks
                            for mask_child in child.children:
                                if not pdb.gimp_item_is_group(mask_child):
                                    structure_layers_to_resize.append(mask_child)
                        elif pdb.gimp_item_is_group(child) and child_name == "Overlay":
                            overlay_group = child
                            write_log("Found Overlay group")
        
        # Resize ONLY structure layers
        write_log("Resizing {0} structure layers...".format(len(structure_layers_to_resize)))
        for layer in structure_layers_to_resize:
            try:
                layer_name = pdb.gimp_item_get_name(layer)
                old_layer_width = pdb.gimp_drawable_width(layer)
                old_layer_height = pdb.gimp_drawable_height(layer)
                
                if old_layer_width != new_width or old_layer_height != new_height:
                    pdb.gimp_layer_resize(layer, new_width, new_height, 0, 0)
                    write_log("Resized '{0}' from {1}x{2} to {3}x{4}".format(
                        layer_name, old_layer_width, old_layer_height, new_width, new_height))
            except Exception as e:
                write_log("WARNING: Could not resize layer: {0}".format(e))
        
        # Get margin from metadata
        margin_size = safe_float(metadata.get('adjustedMargin', 0))
        write_log("Using margin: {0}px".format(margin_size))
        
        # FILL newly created canvas areas
        write_log("Filling newly created canvas areas...")
        
        if effective_direction == 1:  # Right
            new_area_x = old_width
            new_area_y = 0
            new_area_width = new_width - old_width
            new_area_height = old_height
        else:  # Bottom
            new_area_x = 0
            new_area_y = old_height
            new_area_width = old_width
            new_area_height = new_height - old_height
        
        write_log("New area: ({0},{1}) size {2}x{3}".format(
            new_area_x, new_area_y, new_area_width, new_area_height))
        
        # Fill Mask layer with black
        if mask_layer and new_area_width > 0 and new_area_height > 0:
            try:
                pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                               int(new_area_x), int(new_area_y),
                                               int(new_area_width), int(new_area_height))
                pdb.gimp_context_set_foreground((0, 0, 0))
                pdb.gimp_edit_fill(mask_layer, FILL_FOREGROUND)
                pdb.gimp_selection_none(img)
                write_log("Mask layer filled")
            except Exception as e:
                write_log("WARNING: Could not fill Mask: {0}".format(e))
        
        # Fill Borders layer with gray
        if borders_layer and new_area_width > 0 and new_area_height > 0:
            try:
                pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                               int(new_area_x), int(new_area_y),
                                               int(new_area_width), int(new_area_height))
                pdb.gimp_context_set_foreground((200, 200, 200))
                pdb.gimp_edit_fill(borders_layer, FILL_FOREGROUND)
                pdb.gimp_selection_none(img)
                write_log("Borders layer filled")
            except Exception as e:
                write_log("WARNING: Could not fill Borders: {0}".format(e))
        
        # Fill Background layer with white
        if background_layer and new_area_width > 0 and new_area_height > 0:
            try:
                pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                               int(new_area_x), int(new_area_y),
                                               int(new_area_width), int(new_area_height))
                pdb.gimp_context_set_foreground((255, 255, 255))
                pdb.gimp_edit_fill(background_layer, FILL_FOREGROUND)
                pdb.gimp_selection_none(img)
                write_log("Background layer filled")
            except Exception as e:
                write_log("WARNING: Could not fill Background: {0}".format(e))
        
        # UPDATE LAYERS for each new cell
        for new_cell in new_cells:
            cell_lx = int(new_cell['minX'])
            cell_rx = int(new_cell['maxX'])
            cell_ty = int(new_cell['minY'])
            cell_by = int(new_cell['maxY'])
            cell_width_calc = cell_rx - cell_lx
            cell_height_calc = cell_by - cell_ty
            
            write_log("Updating layers for cell {0}".format(new_cell['index']))
            
            # 1. Update Mask layer - Create hole for cell
            if mask_layer:
                try:
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE, 
                                                   cell_lx, cell_ty, cell_width_calc, cell_height_calc)
                    pdb.gimp_edit_clear(mask_layer)
                    pdb.gimp_selection_none(img)
                except Exception as e:
                    write_log("WARNING: Could not update Mask: {0}".format(e))
            
            # 2. Update Borders layer - Create hole with margins
            if borders_layer and margin_size > 0:
                try:
                    inner_x = cell_lx + int(margin_size)
                    inner_y = cell_ty + int(margin_size)
                    inner_width = cell_width_calc - int(2 * margin_size)
                    inner_height = cell_height_calc - int(2 * margin_size)
                    
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                                   inner_x, inner_y, inner_width, inner_height)
                    pdb.gimp_edit_clear(borders_layer)
                    pdb.gimp_selection_none(img)
                except Exception as e:
                    write_log("WARNING: Could not update Borders: {0}".format(e))
            
            # 3. Create Simple page Mask for new cell (spread mode only)
            if cell_type.lower() == "spread" and simple_page_group:
                try:
                    row = new_cell.get('row')
                    col = new_cell.get('col')
                    
                    if row is None or col is None:
                        cell_index = new_cell['index']
                        row = ((cell_index - 1) // nbr_cols) + 1
                        col = ((cell_index - 1) % nbr_cols) + 1
                    
                    mask_name = "R{0}C{1}".format(row, col)
                    
                    # Create mask layer using GIMP Python API style
                    mask_layer_spm = pdb.gimp_layer_new(img, new_width, new_height,
                                                        RGBA_IMAGE, mask_name, 100, NORMAL_MODE)
                    pdb.gimp_image_insert_layer(img, mask_layer_spm, simple_page_group, 0)
                    
                    # Fill mask with rectangle at center
                    middle_x = cell_lx + (cell_width_calc / 2)
                    rect_x = int(middle_x - margin_size)
                    rect_y = cell_ty
                    rect_width = int(2 * margin_size)
                    rect_height = cell_height_calc
                    
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                                   rect_x, rect_y, rect_width, rect_height)
                    pdb.gimp_context_set_foreground(border_color)
                    pdb.gimp_edit_fill(mask_layer_spm, FILL_FOREGROUND)
                    pdb.gimp_selection_none(img)
                    
                    pdb.gimp_item_set_visible(mask_layer_spm, False)
                    write_log("Simple page mask {0} created".format(mask_name))
                except Exception as e:
                    write_log("WARNING: Could not create Simple page mask: {0}".format(e))
            
            # 4. Create gutter for new cell (spread mode only)
            if cell_type.lower() == "spread" and gutters_layer:
                try:
                    middle_x = cell_lx + (cell_width_calc / 2)
                    gutter_width = max(2, int(round(cell_width_calc / 500.0)))
                    gutter_height = int(cell_height_calc * 0.9)
                    gutter_y_offset = int((cell_height_calc - gutter_height) / 2)
                    
                    gutter_x = int(middle_x - gutter_width / 2)
                    gutter_y = cell_ty + gutter_y_offset
                    
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                                   gutter_x, gutter_y, gutter_width, gutter_height)
                    pdb.gimp_context_set_foreground((34, 34, 34))
                    pdb.gimp_edit_fill(gutters_layer, FILL_FOREGROUND)
                    pdb.gimp_selection_none(img)
                    write_log("Gutter created")
                except Exception as e:
                    write_log("WARNING: Could not create gutter: {0}".format(e))
            
            # 5. Place overlay for new cell (if overlays are enabled)
            # Logique identique a la V1 (importGimpBoard.py lignes 1589-1660)
            if overlay_group and overlay_files and len(overlay_files) > 0:
                try:
                    row = new_cell.get('row')
                    col = new_cell.get('col')
                    
                    # Fallback si row/col ne sont pas dans new_cell
                    if row is None or col is None:
                        cell_index = new_cell['index']
                        row = ((cell_index - 1) // nbr_cols) + 1
                        col = ((cell_index - 1) % nbr_cols) + 1
                        write_log("WARNING: Using fallback row/col calculation for overlay")
                    
                    write_log("Placing overlay for cell R{0}C{1}".format(row, col))
                    
                    # Calculer l'index de l'overlay (meme logique que createOpenBoard.py)
                    overlay_index = get_overlay_index_for_cell(row, col, nbr_cols, len(overlay_files), cell_type)
                    if overlay_index >= len(overlay_files):
                        overlay_index = overlay_index % len(overlay_files)
                    
                    overlay_path = overlay_files[overlay_index]
                    write_log("Using overlay file: {0} (index {1})".format(overlay_path, overlay_index))
                    
                    # Determiner l'orientation de l'overlay
                    orientation = get_image_orientation(overlay_path)
                    write_log("Overlay orientation: {0}".format(orientation))
                    
                    # Calculer les dimensions et positions
                    position_info = calculate_overlay_dimensions(
                        cell_width_calc, cell_height_calc, cell_type, orientation, margin_size
                    )
                    
                    # Placer l'overlay selon le type (exactement comme dans V1)
                    if position_info['position'] == 'center':
                        # Placement centre (Single ou Landscape en Spread)
                        place_overlay_in_cell(
                            img, overlay_path, cell_lx, cell_ty, 
                            cell_width_calc, cell_height_calc,
                            cell_type, overlay_group, position_info
                        )
                    elif position_info['position'] == 'split':
                        # Placement separe (Portrait en Spread)
                        # Placer l'overlay gauche
                        left_info = {
                            'position': 'center',
                            'dimensions': position_info['dimensions']['left']
                        }
                        place_overlay_in_cell(
                            img, overlay_path,
                            cell_lx, cell_ty,
                            int(position_info['dimensions']['left']['width']),
                            int(position_info['dimensions']['left']['height']),
                            cell_type, overlay_group, left_info
                        )
                        
                        # Placer l'overlay droit (même fichier si un seul overlay, sinon fichier suivant)
                        if len(overlay_files) > 1:
                            next_index = (overlay_index + 1) % len(overlay_files)
                            next_overlay_path = overlay_files[next_index]
                        else:
                            # Un seul overlay : utiliser le même fichier pour les deux côtés
                            next_overlay_path = overlay_path
                        
                        right_info = {
                            'position': 'center',
                            'dimensions': position_info['dimensions']['right']
                        }
                        place_overlay_in_cell(
                            img, next_overlay_path,
                            int(cell_lx + position_info['dimensions']['right']['x']), cell_ty,
                            int(position_info['dimensions']['right']['width']),
                            int(position_info['dimensions']['right']['height']),
                            cell_type, overlay_group, right_info
                        )
                    
                    write_log("Overlay placed successfully for cell R{0}C{1}".format(row, col))
                    
                except Exception as e:
                    write_log("WARNING: Could not place overlay on new cell: {0}".format(e))
                    import traceback
                    write_log("Traceback: {0}".format(traceback.format_exc()))
        
        write_log("All visual elements updated")
        
        # REPOSITION LEGEND
        try:
            write_log("Searching for Legend layer...")
            legend_layer = None
            
            if board_elements_group:
                for child in board_elements_group.children:
                    if pdb.gimp_item_get_name(child) == "Legend":
                        legend_layer = child
                        break
            
            if not legend_layer:
                for layer in img.layers:
                    if not pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Legend":
                        legend_layer = layer
                        break
            
            if legend_layer:
                current_x, current_y = pdb.gimp_drawable_offsets(legend_layer)
                write_log("Legend at: ({0}, {1})".format(current_x, current_y))
                
                if effective_direction == 1:  # Right
                    horizontal_offset = cell_width + layout_spacing
                    new_x = int(current_x + horizontal_offset)
                    new_y = current_y
                    write_log("Moving legend RIGHT by {0}px".format(horizontal_offset))
                else:  # Bottom
                    vertical_offset = cell_height + layout_spacing
                    new_x = current_x
                    new_y = int(current_y + vertical_offset)
                    write_log("Moving legend DOWN by {0}px".format(vertical_offset))
                
                pdb.gimp_layer_set_offsets(legend_layer, new_x, new_y)
                write_log("Legend repositioned to: ({0}, {1})".format(new_x, new_y))
        except Exception as e:
            write_log("WARNING: Could not reposition Legend: {0}".format(e))
        
        # Update .board file
        try:
            with open(dit_path, 'r') as f:
                lines = f.readlines()
            
            metadata_lines = []
            cell_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    metadata_lines.append(line)
                elif line[0].isdigit():
                    cell_lines.append(line)
            
            new_metadata = []
            for line in metadata_lines:
                if line.startswith('#nbrCols='):
                    new_metadata.append('#nbrCols={0}'.format(nbr_cols))
                elif line.startswith('#nbrRows='):
                    new_metadata.append('#nbrRows={0}'.format(nbr_rows))
                else:
                    new_metadata.append(line)
            
            for new_cell in new_cells:
                cell_line = "{0},{1},{2},{3},{4},{5},{6},{7},{8}".format(
                    new_cell['index'],
                    int(new_cell['minX']), int(new_cell['minY']),
                    int(new_cell['minX']), int(new_cell['maxY']),
                    int(new_cell['maxX']), int(new_cell['maxY']),
                    int(new_cell['maxX']), int(new_cell['minY'])
                )
                cell_lines.append(cell_line)
            
            with open(dit_path, 'w') as f:
                for line in new_metadata:
                    f.write(line + '\n')
                for line in cell_lines:
                    f.write(line + '\n')
            
            write_log("Updated .board file with {0} new cells".format(len(new_cells)))
        except Exception as e:
            write_log("ERROR updating .board file: {0}".format(e))
            return False
        
        pdb.gimp_displays_flush()
        
        # Save direction for alternate mode
        if alternate_pref_file is not None:
            try:
                direction_to_save = ["Bottom", "Right"][effective_direction]
                with open(alternate_pref_file, 'w') as f:
                    f.write(direction_to_save)
                write_log("Saved direction: {0}".format(direction_to_save))
            except:
                pass
        
        write_log("====== Board extension completed ======")
        return True
    except Exception as e:
        write_log("ERROR in extend_board: {0}".format(e))
        return False

# ============================================================================
# MAIN IMPORT FUNCTION
# ============================================================================

def import_images_to_board(img, image_files, cell_type, resize_mode, start_cell, 
                          auto_extend=False, extension_direction=0, user_overlay_files=None, should_create_guides=False):
    """Main import function - AVEC CACHE DE SESSION pour performance optimale"""
    global log_file_path
    
    board_path = pdb.gimp_image_get_filename(img)
    if board_path:
        board_dir = os.path.dirname(board_path)
        board_name = os.path.splitext(os.path.basename(board_path))[0]
        log_file_path = os.path.join(board_dir, "{0}_import.log".format(board_name))
        
        # Fichier de préférence pour mode Alternate (à nettoyer à la fin)
        alternate_pref_file = os.path.join(board_dir, "extension_direction.txt")
        
        write_log("====== GIMP Board Import Started ======", log_file_path)
        write_log("Board: {0}".format(board_path), log_file_path)
    else:
        write_log("====== GIMP Board Import Started ======")
        pdb.gimp_message("Please save the board file first")
        return
    
    total_images = len(image_files)
    write_log("Images to import: {0}".format(total_images), log_file_path)
    write_log("Cell type: {0}, Resize: {1}".format(cell_type, resize_mode), log_file_path)
    write_log("Auto extend: {0}, Direction: {1}".format(auto_extend, extension_direction), log_file_path)
    write_log("Create guides: {0}".format(should_create_guides), log_file_path)
    
    # Find .board file
    dit_path = os.path.join(board_dir, "{0}.board".format(board_name))
    if not os.path.exists(dit_path):
        write_log("ERROR: BOARD file not found", log_file_path)
        pdb.gimp_message("BOARD file not found. Please open a valid board XCF file.")
        return
    
    # Read board data
    board_data = read_dit_file(dit_path)
    if not board_data:
        write_log("ERROR: Failed to read BOARD file", log_file_path)
        return
    
    cells = board_data['cells']
    metadata = board_data['metadata']
    board_overlay_files = board_data.get('overlay_files', [])
    
    overlay_files = user_overlay_files if user_overlay_files else board_overlay_files
    
    write_log("Board has {0} cells".format(len(cells)), log_file_path)
    
    # 🔥 CONSTRUIRE LE CACHE DE SESSION (UNE SEULE FOIS)
    write_log("====== BUILDING SESSION CACHE ======", log_file_path)
    cache_start_time = time.time()
    layer_bounds_cache = build_layer_bounds_cache(img)
    cache_time = time.time() - cache_start_time
    write_log("Cache built in {0:.3f}s - {1} layers indexed".format(
        cache_time, len(layer_bounds_cache)), log_file_path)
    
    # Start import
    undo_started = False
    images_placed = 0
    images_failed = 0
    
    try:
        pdb.gimp_image_undo_group_start(img)
        undo_started = True
        
        import_start_time = time.time()
        
        for i, image_file in enumerate(image_files):
            write_log("====== Processing {0}/{1}: {2} ======".format(
                i + 1, total_images, os.path.basename(image_file)), log_file_path)
            
            pdb.gimp_progress_update(float(i) / float(total_images))
            
            orientation = get_image_orientation(image_file)
            
            # 🔥 UTILISER LE CACHE pour trouver une cellule vide (10-15x plus rapide)
            empty_cell, use_side = find_empty_cell_cached(
                cells, cell_type, orientation, layer_bounds_cache)
            
            if empty_cell is None and auto_extend:
                write_log("No empty cell, extending board...", log_file_path)
                extension_success = extend_board(img, dit_path, cells, metadata, 
                                                extension_direction, cell_type, overlay_files)
                
                if extension_success:
                    board_data = read_dit_file(dit_path)
                    if board_data:
                        cells = board_data['cells']
                        metadata = board_data['metadata']
                        if not user_overlay_files:
                            overlay_files = board_data.get('overlay_files', [])
                        write_log("New cell count: {0}".format(len(cells)), log_file_path)
                        
                        # 🔥 RECONSTRUIRE LE CACHE après extension du board
                        write_log("Rebuilding cache after board extension...", log_file_path)
                        rebuild_start = time.time()
                        layer_bounds_cache = build_layer_bounds_cache(img)
                        rebuild_time = time.time() - rebuild_start
                        write_log("Cache rebuilt in {0:.3f}s".format(rebuild_time), log_file_path)
                        
                        # Nouvelle recherche avec cache mis à jour
                        empty_cell, use_side = find_empty_cell_cached(
                            cells, cell_type, orientation, layer_bounds_cache)
                
                if not extension_success or empty_cell is None:
                    write_log("Extension failed, stopping", log_file_path)
                    images_failed = total_images - i
                    break
            
            if empty_cell is None:
                write_log("No more empty cells, stopping", log_file_path)
                images_failed = total_images - i
                break
            
            success = place_image_in_cell(img, image_file, empty_cell, cell_type, 
                                         resize_mode, metadata, cells, use_side, should_create_guides)
            
            if success:
                images_placed += 1
                
                # 🔥 CRITIQUE : Reconstruire le cache après chaque placement
                # Cela garantit que les cellules occupées sont détectées correctement
                # Le coût est minime (<0.1s) comparé au gain global
                cache_rebuild_start = time.time()
                layer_bounds_cache = build_layer_bounds_cache(img)
                cache_rebuild_time = time.time() - cache_rebuild_start
                write_log("Cache updated after placement in {0:.3f}s".format(cache_rebuild_time), log_file_path)
            else:
                images_failed += 1
        
        pdb.gimp_progress_update(1.0)
        
        total_import_time = time.time() - import_start_time
        
        write_log("====== Import completed ======", log_file_path)
        write_log("Placed: {0}, Failed: {1}".format(images_placed, images_failed), log_file_path)
        write_log("Total import time: {0:.2f}s ({1:.3f}s per image)".format(
            total_import_time, 
            total_import_time / max(1, len(image_files))), log_file_path)
        
        # 🔥 Le cache est automatiquement détruit ici (fin de scope)
        write_log("Session cache destroyed (end of import)", log_file_path)
        
        # Auto-save
        if images_placed > 0 and board_path:
            try:
                write_log("Auto-saving XCF file", log_file_path)
                pdb.gimp_xcf_save(0, img, img.layers[0], board_path, board_path)
                pdb.gimp_image_clean_all(img)
                write_log("XCF file saved", log_file_path)
                write_log("Import completed: {0} image(s) placed and saved.".format(images_placed), log_file_path)
                # pdb.gimp_message("Import completed: {0} image(s) placed and saved.".format(images_placed))
            except Exception as e:
                write_log("ERROR saving: {0}".format(e), log_file_path)
                write_log("Import completed: {0} image(s) placed but save failed.".format(images_placed), log_file_path)
                # pdb.gimp_message("Import completed: {0} image(s) placed but save failed.".format(images_placed))
        elif images_placed > 0:
            write_log("Import completed: {0} image(s) placed.".format(images_placed), log_file_path)
            # pdb.gimp_message("Import completed: {0} image(s) placed.".format(images_placed))
        
    except Exception as e:
        write_log("ERROR during import: {0}".format(e), log_file_path)
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()), log_file_path)
    finally:
        if undo_started:
            try:
                pdb.gimp_image_undo_group_end(img)
            except:
                pass
        
        # 🧹 Nettoyage : Supprimer le fichier de préférence du mode Alternate
        try:
            if 'alternate_pref_file' in locals() and os.path.exists(alternate_pref_file):
                os.remove(alternate_pref_file)
                write_log("Cleaned up extension_direction.txt", log_file_path)
        except Exception as cleanup_error:
            write_log("Warning: Could not remove extension_direction.txt: {0}".format(cleanup_error), log_file_path)
        
        pdb.gimp_displays_flush()

# ============================================================================
# UI FUNCTION
# ============================================================================

def import_board_ui(img, drawable, import_mode, image_folder, image_file, image_pattern, 
                   cell_type, resize_mode, start_cell, overlay_enabled, overlay_file, 
                   overlay_folder, auto_extend, extension_direction, should_create_guides):
    """User interface for import"""
    
    image_files = []
    
    # Convert parameters
    import_mode_list = ["Folder (All Images)", "Single Image", "Folder (Pattern)"]
    cell_type_list = ["single", "spread"]
    resize_mode_list = ["fit", "cover", "noResize"]
    
    mode_name = import_mode_list[import_mode] if isinstance(import_mode, int) else import_mode
    cell_type_str = cell_type_list[cell_type] if isinstance(cell_type, int) else cell_type
    resize_mode_str = resize_mode_list[resize_mode] if isinstance(resize_mode, int) else resize_mode
    
    write_log("====== OPEN BOARD IMPORT ======")
    write_log("Mode: {0}".format(mode_name))
    
    # Get image files
    if mode_name == "Folder (All Images)":
        if not image_folder or not os.path.isdir(image_folder):
            pdb.gimp_message("Please select a valid folder")
            return
        
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff', '*.psd', '*.bmp',
                     '*.JPG', '*.JPEG', '*.PNG', '*.TIF', '*.TIFF', '*.PSD', '*.BMP']
        
        for ext in extensions:
            pattern = os.path.join(image_folder, ext)
            image_files.extend(glob.glob(pattern))
    
    elif mode_name == "Single Image":
        if not image_file or not os.path.isfile(image_file):
            pdb.gimp_message("Please select a valid image file")
            return
        image_files = [image_file]
    
    elif mode_name == "Folder (Pattern)":
        if not image_folder or not os.path.isdir(image_folder):
            pdb.gimp_message("Please select a valid folder")
            return
        
        if not image_pattern or image_pattern.strip() == "":
            image_pattern = "*.jpg"
        
        pattern_path = os.path.join(image_folder, image_pattern)
        image_files = glob.glob(pattern_path)
    
    if not image_files:
        pdb.gimp_message("No images found")
        return
    
    image_files.sort()
    write_log("Found {0} images".format(len(image_files)))
    
    # Handle overlays
    user_overlay_files = []
    if overlay_enabled:
        if overlay_file and os.path.exists(overlay_file):
            user_overlay_files = find_overlay_files(overlay_file)
        elif overlay_folder and os.path.exists(overlay_folder):
            user_overlay_files = find_overlay_files(overlay_folder)
    
    pdb.gimp_progress_init("Importing {0} image(s)...".format(len(image_files)), None)
    
    import_images_to_board(img, image_files, cell_type_str, resize_mode_str, start_cell, 
                          auto_extend, extension_direction, user_overlay_files, should_create_guides)

# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

register(
    "python_fu_board_import",
    "Open Board - Import images into board",
    "Import images into cells with automatic placement and optional board extension",
    "Yan Senez",
    "Yan Senez",
    "2025",
    "<Image>/File/Open Board/2.Import Images...",
    "RGB*, GRAY*",
    [
        (PF_OPTION, "import_mode", "─────────── 📥 IMPORT ───────────\nType", 0, 
         ["Folder (All Images)", "Single Image", "Folder (Pattern)"]),
        (PF_DIRNAME, "image_folder", "─────────── 📁 SOURCE ───────────\nFolder", ""),
        (PF_FILE, "image_file", "Image File", ""),
        (PF_STRING, "image_pattern", "Pattern (e.g. *.jpg)", "*.jpg"),
        (PF_OPTION, "cell_type", "─────────── 🔲 PLACEMENT ───────────\nCell Type", 1, ["single", "spread"]),
        (PF_OPTION, "resize_mode", "Resize Mode", 1, ["fit", "cover", "noResize"]),
        (PF_INT, "start_cell", "Start Cell", 1),
        (PF_TOGGLE, "overlay_enabled", "─────────── 🎭 OVERLAY ───────────\nEnable", False),
        (PF_FILE, "overlay_file", "Overlay File", ""),
        (PF_DIRNAME, "overlay_folder", "Overlay Folder", ""),
        (PF_TOGGLE, "auto_extend", "─────────── ⚙️  EXTENSION ───────────\nAuto-extend", True),
        (PF_OPTION, "extension_direction", "Direction", 2, ["Bottom", "Right", "Alternate"]),
        (PF_TOGGLE, "should_create_guides", "─────────── 📏 GUIDES ───────────\nCreate Guides", False)
    ],
    [],
    import_board_ui
)

main()
