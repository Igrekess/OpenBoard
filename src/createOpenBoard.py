#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Open Board - Layout Creator for GIMP
# Converted from Photoshop script with the help of Claude
# By Yan Senez
# Version 1.0

from gimpfu import *
import os
import time
import json
import math

# Global variables to store configuration
# Variables globales pour stocker la configuration
global_dest_folder = None
log_file_cleared = False

def write_log(message, log_folder_path=None):
    """Write log messages to a file
    Ecrire des messages de log dans un fichier"""
    try:
        if log_folder_path is None:
            # Use temp directory if no folder is specified
            import tempfile
            log_folder_path = tempfile.gettempdir()
        
        log_file_name = "board_gimp_log.txt"
        log_file_path = os.path.join(log_folder_path, log_file_name)
        
        # Format date and time
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        full_message = "{0} - {1}".format(timestamp, message)
        
        # Write to log file
        with open(log_file_path, 'a') as log_file:
            log_file.write(full_message + "\n")
        
        # Also print to console for debugging
        print(full_message)
        return True
    except Exception as e:
        print("Error writing to log: {0}".format(e))
        return False

def ensure_folder_exists(folder_path):
    """Ensure a folder exists (create if needed)
    S'assurer qu'un dossier existe (creer si necessaire)"""
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            write_log("Created folder at: {0}".format(folder_path))
        return folder_path
    except Exception as e:
        write_log("Error creating folder: {0}".format(e))
        return None

def write_cell_coordinates(rectangle, dit_path, cell_number):
    """Write cell coordinates to a .board file
    Ecrire les coordonnees d'une cellule dans un fichier .board"""
    try:
        with open(dit_path, 'a') as dit_file:
            # Format: CellNumber,topLeftX,topLeftY,bottomLeftX,bottomLeftY,bottomRightX,bottomRightY,topRightX,topRightY
            line = "{0},{1},{2},{3},{4},{5},{6},{7},{8}".format(
                cell_number, rectangle[0][0], rectangle[0][1], rectangle[1][0], rectangle[1][1],
                rectangle[2][0], rectangle[2][1], rectangle[3][0], rectangle[3][1])
            dit_file.write(line + "\n")
        
        write_log("Cell {0} written: topLeft({1},{2}), bottomLeft({3},{4}), bottomRight({5},{6}), topRight({7},{8})".format(
            cell_number, rectangle[0][0], rectangle[0][1], rectangle[1][0], rectangle[1][1],
            rectangle[2][0], rectangle[2][1], rectangle[3][0], rectangle[3][1]))
    except Exception as e:
        write_log("Error writing cell coordinates: {0}".format(e))

def remove_dit_file(file_path):
    """Remove a .board file if it exists
    Supprimer un fichier .board s'il existe"""
    try:
        if not file_path:
            write_log("No .board file path provided to remove")
            return False
        
        write_log("Attempting to remove .board file: {0}".format(file_path))
        
        if os.path.exists(file_path):
            os.remove(file_path)
            write_log(".board file successfully removed: {0}".format(file_path))
            return True
        else:
            write_log(".board file does not exist at: {0}".format(file_path))
            return False
    except Exception as e:
        write_log("Error removing .board file: {0}".format(e))
        return False

def create_guide(img, position, orientation):
    """Create a guide in the image
    Creer un guide dans l'image"""
    if orientation == "horizontal":
        pdb.gimp_image_add_hguide(img, position)
    else:  # vertical
        pdb.gimp_image_add_vguide(img, position)

def find_overlay_files(path):
    """Trouver les fichiers overlay compatibles
    Find compatible overlay files
    
    Si path est un fichier, retourner [path]
    Si path est un dossier, retourner tous les fichiers compatibles tries
    
    If path is a file, return [path]
    If path is a folder, return all compatible files sorted
    """
    try:
        if not path or not os.path.exists(path):
            write_log("Overlay path does not exist: {0}".format(path))
            return []
        
        # Si c'est un fichier unique
        if os.path.isfile(path):
            write_log("Using single overlay file: {0}".format(path))
            return [path]
        
        # Si c'est un dossier
        if os.path.isdir(path):
            extensions = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.xcf', '.psd', '.bmp', '.gif']
            overlay_files = []
            
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in extensions:
                        overlay_files.append(file_path)
            
            # Trier les fichiers par nom pour un ordre coherent
            overlay_files.sort()
            write_log("Found {0} overlay files in directory: {1}".format(len(overlay_files), path))
            return overlay_files
        
        return []
    except Exception as e:
        write_log("Error finding overlay files: {0}".format(e))
        return []

def get_image_orientation(image_path):
    """Determiner l'orientation d'une image (Portrait, Landscape, ou Square)
    Determine image orientation (Portrait, Landscape, or Square)"""
    try:
        # Charger l'image temporairement pour obtenir ses dimensions
        temp_img = pdb.gimp_file_load(image_path, image_path)
        width = temp_img.width
        height = temp_img.height
        pdb.gimp_image_delete(temp_img)
        
        if width > height:
            return "Landscape"
        elif height > width:
            return "Portrait"
        else:
            return "Square"
    except Exception as e:
        write_log("Error getting image orientation: {0}".format(e))
        return "Landscape"  # Valeur par defaut

def calculate_overlay_dimensions(cell_width, cell_height, cell_type, orientation, margin):
    """Calculer les dimensions et positions pour les overlays
    Calculate overlay dimensions and positions
    
    Retourne un dict avec les informations de placement
    Returns a dict with placement information
    """
    result = {
        'position': 'center',
        'dimensions': {
            'width': cell_width,
            'height': cell_height,
            'x': 0,
            'y': 0
        }
    }
    
    # En mode spread avec image portrait, diviser la cellule en deux
    if cell_type.lower() == "spread" and orientation == "Portrait":
        result['position'] = 'split'
        half_width = cell_width / 2
        result['dimensions'] = {
            'left': {
                'width': half_width,
                'height': cell_height,
                'x': 0,
                'y': 0
            },
            'right': {
                'width': half_width,
                'height': cell_height,
                'x': half_width,
                'y': 0
            }
        }
    
    return result

def place_overlay_in_cell(img, overlay_path, cell_x, cell_y, cell_width, cell_height, 
                          cell_type, overlay_group, position_info):
    """
    Placer un overlay dans une cellule
    
    Parameters:
    - img: L'image GIMP active
    - overlay_path: Chemin du fichier overlay
    - cell_x, cell_y: Position de la cellule
    - cell_width, cell_height: Dimensions de la cellule
    - cell_type: "single" ou "spread"
    - overlay_group: Groupe de calques pour les overlays
    - position_info: Informations de placement calculees
    """
    try:
        write_log("Placing overlay: {0}".format(overlay_path))
        
        # Charger l'overlay
        overlay_img = pdb.gimp_file_load(overlay_path, overlay_path)
        overlay_layer = overlay_img.active_layer
        if not overlay_layer:
            overlay_layer = overlay_img.layers[0]
        
        # Copier le calque dans l'image de destination
        new_layer = pdb.gimp_layer_new_from_drawable(overlay_layer, img)
        pdb.gimp_image_insert_layer(img, new_layer, overlay_group, 0)
        
        # Renommer le calque
        overlay_name = os.path.splitext(os.path.basename(overlay_path))[0]
        pdb.gimp_item_set_name(new_layer, "Overlay_{0}".format(overlay_name))
        
        # Redimensionner pour correspondre aux dimensions de la cellule
        if position_info['position'] == 'center':
            dims = position_info['dimensions']
            pdb.gimp_layer_scale(new_layer, int(dims['width']), int(dims['height']), True)
            
            # Positionner au centre de la cellule
            pdb.gimp_layer_set_offsets(new_layer, int(cell_x), int(cell_y))
        
        # Supprimer l'image temporaire
        pdb.gimp_image_delete(overlay_img)
        
        write_log("Overlay placed successfully")
        return new_layer
        
    except Exception as e:
        write_log("Error placing overlay: {0}".format(e))
        return None

def get_overlay_index_for_cell(row, col, nbr_cols, overlay_files_count, cell_type):
    """Calculer l'index de l'overlay a utiliser pour une cellule donnee
    Calculate the overlay index to use for a given cell
    
    Logique identique a Photoshop
    Same logic as Photoshop
    """
    cell_number = (row - 1) * nbr_cols + (col - 1)
    
    if cell_type.lower() == "spread":
        # En mode spread, les paires restent ensemble
        pair_index = ((cell_number % 2) * 2) % overlay_files_count
        return pair_index
    else:
        # En mode single, sequence simple
        return cell_number % overlay_files_count

def write_overlay_metadata_to_dit(dit_path, overlay_files, overlay_indexes):
    """Ecrire les metadonnees des overlays dans le fichier .board
    Write overlay metadata to the .board file
    """
    try:
        # Lire le contenu existant
        existing_content = ""
        if os.path.exists(dit_path):
            with open(dit_path, 'r') as f:
                existing_content = f.read()
        
        # Preparer les metadonnees overlay
        overlay_metadata = []
        
        # Ajouter la liste des fichiers overlay (en JSON)
        if overlay_files:
            import json
            files_json = json.dumps(overlay_files)
            overlay_metadata.append("#overlayFiles={0}".format(files_json))
        
        # Ajouter les index pour chaque cellule
        for cell_key, index in overlay_indexes.items():
            overlay_metadata.append("#{0}={1}".format(cell_key, index))
        
        # Reecrire le fichier avec les nouvelles metadonnees
        with open(dit_path, 'w') as f:
            # Ecrire d'abord les metadonnees overlay
            for meta_line in overlay_metadata:
                f.write(meta_line + "\n")
            
            # Puis ecrire le contenu existant (en sautant les anciennes metadonnees overlay)
            for line in existing_content.split('\n'):
                if not line.startswith('#overlayFiles=') and not line.startswith('#overlay_index_cell_'):
                    if line.strip():  # Ignorer les lignes vides
                        f.write(line + "\n")
        
        write_log("Overlay metadata written to .board file")
        return True
    except Exception as e:
        write_log("Error writing overlay metadata: {0}".format(e))
        return False

def convert_hex_to_rgb(hex_color):
    """Convert a hex color to RGB values (0-255)
    Convertir une couleur hexa en valeurs RGB (0-255)
    
    Accepts either:
    - A hex string like "#FFFFFF" or "FFFFFF"
    - A gimpcolor.RGB object (from GIMP UI)
    - A tuple/list of RGB values (0-255)
    
    Accepte:
    - Une chaine hexa comme "#FFFFFF" ou "FFFFFF"
    - Un objet gimpcolor.RGB (depuis l'interface GIMP)
    - Un tuple/liste de valeurs RGB (0-255)
    """
    # Si c'est deja un objet gimpcolor.RGB ou un tuple/liste
    if hasattr(hex_color, 'r') and hasattr(hex_color, 'g') and hasattr(hex_color, 'b'):
        # C'est un objet gimpcolor.RGB (valeurs entre 0.0 et 1.0)
        r = int(hex_color.r * 255)
        g = int(hex_color.g * 255)
        b = int(hex_color.b * 255)
        return (r, g, b)
    elif isinstance(hex_color, (tuple, list)) and len(hex_color) >= 3:
        # C'est deja un tuple RGB
        return (int(hex_color[0]), int(hex_color[1]), int(hex_color[2]))
    
    # Sinon, c'est une chaine hexadecimale
    try:
        hex_color = str(hex_color).lstrip('#')
        if len(hex_color) != 6:
            write_log("Invalid hex color: {0}, defaulting to white".format(hex_color))
            return (255, 255, 255)
        
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except Exception as e:
        write_log("Error converting color {0}: {1}, defaulting to white".format(hex_color, e))
        return (255, 255, 255)

def convert_rgb_to_gimp_color(rgb):
    """Convert RGB values (0-255) to GIMP color values (0.0-1.0)
    Convertir des valeurs RGB (0-255) en valeurs de couleur GIMP (0.0-1.0)"""
    r, g, b = rgb
    return (r / 255.0, g / 255.0, b / 255.0)

def convert_to_pixels(value, unit, resolution):
    """Convert dimensions to pixels based on specified units
    Convertir des dimensions en pixels selon l'unite specifiee"""
    try:
        # Assurer que les valeurs sont des nombres
        value = float(value)
        resolution = float(resolution)
        
        if math.isnan(value):
            write_log("Warning: Invalid value for conversion: {0}".format(value))
            return 0.0
        
        if math.isnan(resolution):
            write_log("Warning: Invalid resolution for conversion: {0}".format(resolution))
            resolution = 72.0  # Default value
        
        # Convert based on unit
        if unit.lower() == "mm":
            return float((value / 25.4) * resolution)
        elif unit.lower() == "cm":
            return float((value / 2.54) * resolution)
        elif unit.lower() == "in":
            return float(value * resolution)
        elif unit.lower() == "pt":
            return float((value / 72) * resolution)
        else:  # px or default
            return float(value)
    except Exception as e:
        write_log("Error in convertToPixels: {0}".format(e))
        # Retourner 0.0 en cas d'erreur au lieu de la valeur originale
        return 0.0

def fill_selection_with_color(img, drawable, rgb_color):
    """Fill the current selection with a solid color"""
    r, g, b = rgb_color
    old_fg = pdb.gimp_context_get_foreground()
    
    # Set foreground color and fill
    pdb.gimp_context_set_foreground((r, g, b))
    pdb.gimp_edit_fill(drawable, FILL_FOREGROUND)
    
    # Restore old foreground color
    pdb.gimp_context_set_foreground(old_fg)

def create_rectangular_selection(img, rectangle):
    """Create a rectangular selection from coordinates"""
    # Convert rectangle coordinates to x, y, width, height
    x1, y1 = rectangle[0]
    x2, y2 = rectangle[1]
    x3, y3 = rectangle[2]
    x4, y4 = rectangle[3]
    
    # Calculate selection bounds
    x = min(x1, x2, x3, x4)
    y = min(y1, y2, y3, y4)
    width = max(x1, x2, x3, x4) - x
    height = max(y1, y2, y3, y4) - y
    
    # Create selection
    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE, x, y, width, height)
    return True


def create_board_layout(board_name, dest_folder,
                       layout_units, layout_resolution, layout_width, layout_height,
                       nbr_col, nbr_row, cell_type, cell_units, cell_width, cell_height, margin_mask,
                       spacing_units, layout_spacing,
                       bg_color_hex, border_color_hex, layout_color_hex,
                       baseline_text, selected_font, baseline_text_size, baseline_text_color_hex,
                       logo_folder_path,
                       overlay_mask_on, overlay_file_path, overlay_folder_path,
                       should_create_guides, drop_zone):
    """Main function to create the board layout - Reorganized for optimal UI flow
    Fonction principale pour creer la planche - Reorganisee pour un flux UI optimal"""
    
    # Start log
    write_log("Script started")
    write_log("Open Board - Layout Creator for GIMP started")
    
    # Convertir les index des PF_OPTION en valeurs string
    units_list = ["px", "mm", "cm", "in", "pt"]
    cell_type_list = ["single", "spread"]
    
    # Convertir layout_units (index -> string)
    if isinstance(layout_units, int):
        layout_units = units_list[layout_units]
    
    # Convertir cell_units (index -> string)
    if isinstance(cell_units, int):
        cell_units = units_list[cell_units]
    
    # Convertir spacing_units (index -> string)
    if isinstance(spacing_units, int):
        spacing_units = units_list[spacing_units]
    
    # Convertir cell_type (index -> string)
    if isinstance(cell_type, int):
        cell_type = cell_type_list[cell_type]
    
    # Convertir should_create_guides (boolean -> string pour compatibilité)
    if isinstance(should_create_guides, bool):
        should_create_guides = "true" if should_create_guides else "false"
    
    write_log("Units after conversion - Layout: {0}, Cell: {1}, Spacing: {2}".format(
        layout_units, cell_units, spacing_units))
    write_log("Cell Type: {0}, Create Guides: {1}".format(cell_type, should_create_guides))
    
    # Set global destination folder
    global global_dest_folder
    global_dest_folder = dest_folder
    
    # Convert colors from hex to RGB
    bg_color = convert_hex_to_rgb(bg_color_hex)
    border_color = convert_hex_to_rgb(border_color_hex)
    layout_color = convert_hex_to_rgb(layout_color_hex)
    baseline_text_color = convert_hex_to_rgb(baseline_text_color_hex)
    
    # Convert dimensions to pixels (ensure integers for GIMP)
    # Les fonctions convert_to_pixels retournent maintenant des float
    px_layout_width = int(convert_to_pixels(layout_width, layout_units, layout_resolution))
    px_layout_height = int(convert_to_pixels(layout_height, layout_units, layout_resolution))
    px_cell_width = int(convert_to_pixels(cell_width, cell_units, layout_resolution))
    px_cell_height = int(convert_to_pixels(cell_height, cell_units, layout_resolution))
    px_layout_spacing = int(convert_to_pixels(layout_spacing, spacing_units, layout_resolution))
    px_margin = int(convert_to_pixels(margin_mask, cell_units, layout_resolution))
    
    write_log("Raw dimensions - Layout: {0}x{1} {2}, Cell: {3}x{4} {5}, Spacing: {6} {7}".format(
        layout_width, layout_height, layout_units, cell_width, cell_height, cell_units, layout_spacing, spacing_units))
    
    write_log("Converted to pixels - Layout: {0}x{1}, Cell: {2}x{3}, Spacing: {4}, Margin: {5}".format(
        px_layout_width, px_layout_height, px_cell_width, px_cell_height, px_layout_spacing, px_margin))
    
    # Calculate total cells dimensions
    total_cells_width = (nbr_col * px_cell_width) + ((nbr_col - 1) * px_layout_spacing)
    total_cells_height = (nbr_row * px_cell_height) + ((nbr_row - 1) * px_layout_spacing)
    
    write_log("Total cells dimensions: {0}x{1}".format(total_cells_width, total_cells_height))
    
    # Calculer maxWidth et maxHeight initiaux
    maxWidth = int(round(px_cell_width - (2 * px_margin)))
    maxHeight = int(round(px_cell_height - (2 * px_margin)))
    write_log("Initial maxWidth: {0}, maxHeight: {1} (cell dimensions minus margins)".format(maxWidth, maxHeight))
    
    # Auto-ajustement si les cellules dépassent le layout (comme Photoshop)
    if total_cells_width > px_layout_width or total_cells_height > px_layout_height:
        write_log("═══════════════════════════════════════════════════════════════")
        write_log("OPEN BOARD: AUTO-SCALING OPTIMIZATION")
        write_log("Desired cells dimensions exceed canvas - applying optimization...")
        write_log("═══════════════════════════════════════════════════════════════")
        
        # Calculer le facteur d'échelle pour ajuster les cellules au layout
        scale_factor_width = float(px_layout_width) / float(total_cells_width)
        scale_factor_height = float(px_layout_height) / float(total_cells_height)
        scale_factor = min(scale_factor_width, scale_factor_height) * 0.95  # 5% de marge
        
        write_log("Scale factors - Width: {0:.4f}, Height: {1:.4f}, Final: {2:.4f}".format(
            scale_factor_width, scale_factor_height, scale_factor))
        
        # Ajuster toutes les dimensions avec le facteur d'échelle
        px_cell_width = int(math.floor(px_cell_width * scale_factor))
        px_cell_height = int(math.floor(px_cell_height * scale_factor))
        px_layout_spacing = int(math.floor(px_layout_spacing * scale_factor))
        px_margin = int(math.floor(px_margin * scale_factor))
        
        write_log("✅ OPTIMIZED dimensions:")
        write_log("   • Final Cell: {0} × {1} px".format(px_cell_width, px_cell_height))
        write_log("   • Final Spacing: {0} px".format(px_layout_spacing))
        write_log("   • Final Margin: {0} px".format(px_margin))
        
        # Recalculer les dimensions totales
        total_cells_width = (nbr_col * px_cell_width) + ((nbr_col - 1) * px_layout_spacing)
        total_cells_height = (nbr_row * px_cell_height) + ((nbr_row - 1) * px_layout_spacing)
        
        write_log("   • Total grid: {0} × {1} px (fits in canvas)".format(total_cells_width, total_cells_height))
        
        # Recalculer maxWidth et maxHeight après l'ajustement
        maxWidth = int(round(px_cell_width - (2 * px_margin)))
        maxHeight = int(round(px_cell_height - (2 * px_margin)))
        write_log("   • 📏 Max Image (drop zone): {0} × {1} px".format(maxWidth, maxHeight))
        write_log("═══════════════════════════════════════════════════════════════")
    
    # Définir les variables globales pour les dimensions max des images
    global max_width, max_height
    max_width = maxWidth
    max_height = maxHeight
    
    # Create the XCF file path
    xcf_path = os.path.join(dest_folder, "{0}.xcf".format(board_name))
    
    # Create the .board file path (same folder as XCF)
    dit_path = os.path.join(dest_folder, "{0}.board".format(board_name))
    
    write_log("XCF file path: {0}".format(xcf_path))
    write_log("BOARD file path: {0}".format(dit_path))
    
    # Remove old .board file if it exists
    remove_dit_file(dit_path)
    
    # Create new empty .board file
    try:
        with open(dit_path, 'w') as dit_file:
            # Write metadata header
            dit_file.write("# Board Layout File\n")
            dit_file.write("#boardName={0}\n".format(board_name))
            dit_file.write("#nbrCols={0}\n".format(nbr_col))
            dit_file.write("#nbrRows={0}\n".format(nbr_row))
            dit_file.write("#cellWidth={0}\n".format(px_cell_width))
            dit_file.write("#cellHeight={0}\n".format(px_cell_height))
            dit_file.write("#cellType={0}\n".format(cell_type))
            dit_file.write("#adjustedMargin={0}\n".format(px_margin))
        write_log("DIT file created successfully: {0}".format(dit_path))
    except Exception as e:
        write_log("ERROR creating DIT file: {0}".format(e))
        pdb.gimp_message("Error creating DIT file: {0}".format(e))
    
    # Create new image
    img = gimp.Image(px_layout_width, px_layout_height, RGB)
    img.resolution = (layout_resolution, layout_resolution)
    write_log("Image created")
    
    # Create background layer
    bg_layer = gimp.Layer(img, "Background", px_layout_width, px_layout_height,
                          RGB_IMAGE, 100, NORMAL_MODE)
    img.add_layer(bg_layer, 0)
    
    # Fill background with color
    gimp_bg_color = convert_rgb_to_gimp_color(bg_color)
    pdb.gimp_context_set_foreground(gimp_bg_color)
    pdb.gimp_edit_fill(bg_layer, FILL_FOREGROUND)
    write_log("Background layer created and filled")
    
    # Create layer groups (use layer groups if GIMP version supports them)
    # For GIMP 2.8+ we can use layer groups, for older versions we'll just use layers
    try:
        # Try to create layer groups (GIMP 2.8+)
        board_content_group = pdb.gimp_layer_group_new(img)
        img.add_layer(board_content_group, 0)
        pdb.gimp_item_set_name(board_content_group, "Board Content")
        
        layout_masks_group = pdb.gimp_layer_group_new(img)
        img.add_layer(layout_masks_group, 0)
        pdb.gimp_item_set_name(layout_masks_group, "Board Elements")
        
        write_log("Layer groups created")
        has_layer_groups = True
    except:
        # Fallback for older GIMP versions
        write_log("Layer groups not supported, using regular layers instead")
        has_layer_groups = False
        
        # Create layers directly
        layout_masks_layer = gimp.Layer(img, "Board Elements", px_layout_width, px_layout_height,
                                       RGBA_IMAGE, 100, NORMAL_MODE)
        img.add_layer(layout_masks_layer, 0)
        
        board_content_layer = gimp.Layer(img, "Board Content", px_layout_width, px_layout_height,
                                        RGBA_IMAGE, 100, NORMAL_MODE)
        img.add_layer(board_content_layer, 0)
    
    # Create necessary layers for masks and borders
    if has_layer_groups:
        parent_layer = layout_masks_group
    else:
        parent_layer = layout_masks_layer
    
    # Create simple page group/layer if cell type is spread
    if cell_type.lower() == "spread":
        if has_layer_groups:
            single_page_group = pdb.gimp_layer_group_new(img)
            img.add_layer(single_page_group, 0)
            pdb.gimp_image_reorder_item(img, single_page_group, parent_layer, 0)
            pdb.gimp_item_set_name(single_page_group, "Simple page Mask")
            
            # Create individual mask layers for each cell (R{row}C{col} naming)
            write_log("Creating individual mask layers for {0} cells".format(nbr_row * nbr_col))
            for row in range(1, nbr_row + 1):
                for col in range(1, nbr_col + 1):
                    mask_name = "R{0}C{1}".format(row, col)
                    mask_layer = gimp.Layer(img, mask_name, px_layout_width, px_layout_height,
                                          RGBA_IMAGE, 100, NORMAL_MODE)
                    img.add_layer(mask_layer, 0)
                    pdb.gimp_image_reorder_item(img, mask_layer, single_page_group, 0)
                    
                    # Set layer invisible by default
                    pdb.gimp_item_set_visible(mask_layer, False)
                    
                    write_log("Created mask layer: {0} (invisible by default)".format(mask_name))
        
        # Create gutters layer
        gutters_layer = gimp.Layer(img, "Gutters", px_layout_width, px_layout_height,
                                  RGBA_IMAGE, 100, NORMAL_MODE)
        img.add_layer(gutters_layer, 0)
        if has_layer_groups:
            pdb.gimp_image_reorder_item(img, gutters_layer, parent_layer, 0)
    
    # Create borders layer
    borders_layer = gimp.Layer(img, "Borders", px_layout_width, px_layout_height,
                              RGBA_IMAGE, 100, NORMAL_MODE)
    img.add_layer(borders_layer, 0)
    if has_layer_groups:
        pdb.gimp_image_reorder_item(img, borders_layer, parent_layer, 0)
    
    # Create mask layer
    mask_layer = gimp.Layer(img, "Mask", px_layout_width, px_layout_height,
                           RGBA_IMAGE, 100, NORMAL_MODE)
    img.add_layer(mask_layer, 0)
    if has_layer_groups:
        pdb.gimp_image_reorder_item(img, mask_layer, parent_layer, 0)
    
    write_log("Layers created")
    
    # Fill borders layer with border color
    pdb.gimp_selection_all(img)
    img.active_layer = borders_layer
    fill_selection_with_color(img, borders_layer, border_color)
    pdb.gimp_selection_none(img)
    
    # Fill mask layer with layout color
    pdb.gimp_selection_all(img)
    img.active_layer = mask_layer
    fill_selection_with_color(img, mask_layer, layout_color)
    pdb.gimp_selection_none(img)
    
    write_log("Layers filled with colors")
    
    # Calculate offset to center cells (ensure integers)
    decal_to_center_x = int(math.floor((px_layout_width - total_cells_width) / 2))
    decal_to_center_y = int(math.floor((px_layout_height - total_cells_height) / 2))
    
    write_log("Centering offset: {0},{1}".format(decal_to_center_x, decal_to_center_y))
    
    # Define first cell position
    first_cell_x = int(math.floor(decal_to_center_x))
    first_cell_y = int(math.floor(decal_to_center_y))
    write_log("First cell position: {0},{1}".format(first_cell_x, first_cell_y))
    
    # ══════════════════════════════════════════════════════════════════
    # GESTION DES OVERLAYS
    # ══════════════════════════════════════════════════════════════════
    overlay_files = []
    overlay_indexes = {}
    overlay_group = None
    
    # Convertir overlay_mask_on en boolean si necessaire
    if isinstance(overlay_mask_on, str):
        overlay_mask_on = overlay_mask_on.lower() == "true"
    
    if overlay_mask_on:
        write_log("Overlay mask is enabled")
        
        # Trouver les fichiers overlay (fichier unique ou dossier)
        if overlay_file_path and os.path.exists(overlay_file_path):
            overlay_files = find_overlay_files(overlay_file_path)
            write_log("Found {0} overlay file(s)".format(len(overlay_files)))
        elif overlay_folder_path and os.path.exists(overlay_folder_path):
            overlay_files = find_overlay_files(overlay_folder_path)
            write_log("Found {0} overlay file(s) from folder".format(len(overlay_files)))
        
        if overlay_files:
            # Creer le groupe Overlay
            try:
                overlay_group = pdb.gimp_layer_group_new(img)
                pdb.gimp_item_set_name(overlay_group, "Overlay")
                # Utiliser parent_layer au lieu de board_elements_group qui n'existe pas
                pdb.gimp_image_insert_layer(img, overlay_group, parent_layer, 0)
                write_log("Overlay group created")
                
                # Calculer les index pour chaque cellule
                for r in range(1, nbr_row + 1):
                    for c in range(1, nbr_col + 1):
                        cell_key = "overlay_index_cell_{0}_{1}".format(r, c)
                        overlay_index = get_overlay_index_for_cell(r, c, nbr_col, len(overlay_files), cell_type)
                        overlay_indexes[cell_key] = overlay_index
                        write_log("Cell R{0}C{1}: overlay index {2}".format(r, c, overlay_index))
            except Exception as e:
                write_log("Error creating overlay group: {0}".format(e))
                overlay_group = None
        else:
            write_log("No overlay files found, overlay placement will be skipped")
    else:
        write_log("Overlay mask is disabled")
    
    # Create cells
    write_log("Starting cell creation loop")
    
    for r in range(1, nbr_row + 1):
        for c in range(1, nbr_col + 1):
            x = int(math.floor(decal_to_center_x + (c - 1) * (px_cell_width + px_layout_spacing)))
            y = int(math.floor(decal_to_center_y + (r - 1) * (px_cell_height + px_layout_spacing)))
            
            cell_number = (r - 1) * nbr_col + c
            
            write_log("Creating cell {0} at position {1},{2} with size {3}x{4}".format(
                cell_number, x, y, px_cell_width, px_cell_height))
            
            # Define rectangle for the cell
            rectangle_ref = [
                [x, y],  # top left
                [x, y + px_cell_height],  # bottom left
                [x + px_cell_width, y + px_cell_height],  # bottom right
                [x + px_cell_width, y]  # top right
            ]
            
            # Write coordinates to .dit file
            write_cell_coordinates(rectangle_ref, dit_path, cell_number)
            
            # Create inner rectangle for border mask
            inner_rectangle = [
                [x + px_margin, y + px_margin],  # top left
                [x + px_margin, y + px_cell_height - px_margin],  # bottom left
                [x + px_cell_width - px_margin, y + px_cell_height - px_margin],  # bottom right
                [x + px_cell_width - px_margin, y + px_margin]  # top right
            ]
            
            # Clear inner area in borders layer
            img.active_layer = borders_layer
            create_rectangular_selection(img, inner_rectangle)
            pdb.gimp_edit_clear(borders_layer)
            pdb.gimp_selection_none(img)
            
            # Clear area in mask layer
            img.active_layer = mask_layer
            create_rectangular_selection(img, rectangle_ref)
            pdb.gimp_edit_clear(mask_layer)
            pdb.gimp_selection_none(img)
            
            # If cell type is spread, create a gutter and single page mask
            if cell_type.lower() == "spread" and 'gutters_layer' in locals():
                # Calculate gutter width (ensure integer, minimum 2px for visibility)
                gutter_width = int(max(2, round(px_cell_width / 500)))  # Plus visible: 2px minimum, diviseur réduit
                
                # Calculate middle position
                middle_x = int(x + (px_cell_width / 2))
                
                write_log("Creating gutter for cell {0}: width={1}px, middle_x={2}".format(cell_number, gutter_width, middle_x))
                
                # Create vertical gutter
                img.active_layer = gutters_layer
                
                # Define rectangle for gutter (ensure integers)
                gutter_height = int(px_cell_height * 0.9)
                gutter_y_offset = int((px_cell_height - gutter_height) / 2)
                
                gutter_rect = [
                    [int(middle_x - gutter_width/2), int(y + gutter_y_offset)],
                    [int(middle_x - gutter_width/2), int(y + gutter_y_offset + gutter_height)],
                    [int(middle_x + gutter_width/2), int(y + gutter_y_offset + gutter_height)],
                    [int(middle_x + gutter_width/2), int(y + gutter_y_offset)]
                ]
                
                write_log("Gutter rect: {0}".format(gutter_rect))
                
                # Fill gutter with color
                create_rectangular_selection(img, gutter_rect)
                fill_selection_with_color(img, gutters_layer, (34, 34, 34))  # #222222
                pdb.gimp_selection_none(img)
                
                write_log("Gutter created successfully for cell {0}".format(cell_number))
                
                # Fill the single page mask that was created above
                if has_layer_groups:
                    single_page_id = "R{0}C{1}".format(r, c)
                    
                    # Find the existing mask layer
                    for child in single_page_group.children:
                        if not pdb.gimp_item_is_group(child) and pdb.gimp_item_get_name(child) == single_page_id:
                            # Define rectangle for single page mask
                            single_page_rect = [
                                [middle_x - px_margin, y],
                                [middle_x - px_margin, y + px_cell_height],
                                [middle_x + px_margin, y + px_cell_height],
                                [middle_x + px_margin, y]
                            ]
                            
                            img.active_layer = child
                            
                            # Fill single page mask with color
                            create_rectangular_selection(img, single_page_rect)
                            fill_selection_with_color(img, child, border_color)
                            pdb.gimp_selection_none(img)
                            
                            write_log("Filled single page mask: {0}".format(single_page_id))
                            break
            
            # ══════════════════════════════════════════════════════════════════
            # PLACEMENT DES OVERLAYS
            # ══════════════════════════════════════════════════════════════════
            if overlay_mask_on and overlay_group and overlay_files:
                try:
                    write_log("Placing overlay for cell R{0}C{1}".format(r, c))
                    
                    # Recuperer l'index de l'overlay pour cette cellule
                    cell_key = "overlay_index_cell_{0}_{1}".format(r, c)
                    overlay_index = overlay_indexes.get(cell_key, 0)
                    
                    # S'assurer que l'index est valide
                    if overlay_index >= len(overlay_files):
                        overlay_index = overlay_index % len(overlay_files)
                    
                    overlay_path = overlay_files[overlay_index]
                    write_log("Using overlay file: {0} (index {1})".format(overlay_path, overlay_index))
                    
                    # Determiner l'orientation de l'overlay
                    orientation = get_image_orientation(overlay_path)
                    write_log("Overlay orientation: {0}".format(orientation))
                    
                    # Calculer les dimensions et positions
                    position_info = calculate_overlay_dimensions(
                        px_cell_width, px_cell_height, cell_type, orientation, px_margin
                    )
                    
                    # Placer l'overlay
                    if position_info['position'] == 'center':
                        # Placement centre (Single ou Landscape en Spread)
                        place_overlay_in_cell(
                            img, overlay_path, x, y, px_cell_width, px_cell_height,
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
                            x, y,
                            int(position_info['dimensions']['left']['width']),
                            int(position_info['dimensions']['left']['height']),
                            cell_type, overlay_group, left_info
                        )
                        
                        # Placer l'overlay droit (fichier suivant si disponible)
                        if len(overlay_files) > 1:
                            next_index = (overlay_index + 1) % len(overlay_files)
                            next_overlay_path = overlay_files[next_index]
                            
                            right_info = {
                                'position': 'center',
                                'dimensions': position_info['dimensions']['right']
                            }
                            place_overlay_in_cell(
                                img, next_overlay_path,
                                int(x + position_info['dimensions']['right']['x']), y,
                                int(position_info['dimensions']['right']['width']),
                                int(position_info['dimensions']['right']['height']),
                                cell_type, overlay_group, right_info
                            )
                    
                    write_log("Overlay placed successfully for cell R{0}C{1}".format(r, c))
                except Exception as e:
                    write_log("Error placing overlay for cell R{0}C{1}: {2}".format(r, c, e))
            
            # Create guides if requested (ensure integer positions)
            if should_create_guides == "true":
                if r == 1:
                    create_guide(img, int(x), "vertical")
                    create_guide(img, int(x + px_cell_width), "vertical")
                    create_guide(img, int(x + px_margin), "vertical")
                    create_guide(img, int(x + px_cell_width - px_margin), "vertical")
                    
                    if cell_type.lower() == "spread":
                        create_guide(img, int(x + px_cell_width/2), "vertical")
                
                if c == 1:
                    create_guide(img, int(y), "horizontal")
                    create_guide(img, int(y + px_cell_height), "horizontal")
                    create_guide(img, int(y + px_margin), "horizontal")
                    create_guide(img, int(y + px_cell_height - px_margin), "horizontal")
    
    write_log("Cell creation completed")
    
    # Add legend text if provided
    # Protection contre les types incorrects
    if baseline_text and isinstance(baseline_text, str) and len(baseline_text) > 0:
        try:
            write_log("Adding legend text")
            
            # Create text layer
            text_layer = pdb.gimp_text_fontname(
                img, None, 0, 0, baseline_text, 0,
                True, baseline_text_size, PIXELS, selected_font
            )
            
            pdb.gimp_item_set_name(text_layer, "Legend")
            
            # Set text color
            pdb.gimp_text_layer_set_color(text_layer, baseline_text_color)
            
            # Calculate position for right-aligned text at bottom of layout (ensure integers)
            last_cell_right_edge = int(first_cell_x + (nbr_col * px_cell_width) + ((nbr_col - 1) * px_layout_spacing))
            last_row_bottom_edge = int(first_cell_y + (nbr_row * px_cell_height) + ((nbr_row - 1) * px_layout_spacing))
            vertical_middle = int(last_row_bottom_edge + ((px_layout_height - last_row_bottom_edge) / 2))
            
            # Set text position
            pdb.gimp_layer_set_offsets(text_layer, int(last_cell_right_edge - pdb.gimp_drawable_width(text_layer)), int(vertical_middle))
            
            # Move text layer to board elements group
            if has_layer_groups:
                pdb.gimp_image_reorder_item(img, text_layer, parent_layer, 0)
            
            write_log("Legend text added successfully")
        except Exception as e:
            write_log("Error adding legend text: {0}".format(e))
    
    # Add logo if provided
    if logo_folder_path and isinstance(logo_folder_path, str) and len(logo_folder_path) > 0:
        try:
            write_log("Attempting to use logo from path: {0}".format(logo_folder_path))
            
            # Check if file exists
            if os.path.exists(logo_folder_path):
                # Load logo file
                logo_layer = pdb.gimp_file_load_layer(img, logo_folder_path)
                img.add_layer(logo_layer, 0)
                pdb.gimp_item_set_name(logo_layer, "Logo")
                
                # Move to board elements group
                if has_layer_groups:
                    pdb.gimp_image_reorder_item(img, logo_layer, parent_layer, 0)
                
                # Resize logo
                current_width = logo_layer.width
                current_height = logo_layer.height
                
                # Calculate target height (50% of space between top of document and top of first row)
                top_margin_height = first_cell_y
                target_height = int(top_margin_height * 0.5)
                
                write_log("Logo current height: {0}, target height: {1}".format(current_height, target_height))
                write_log("Top margin height: {0}".format(top_margin_height))
                
                # Calculate resize percentage
                resize_percent = (target_height / float(current_height))
                
                # Apply resize (ensure integers)
                pdb.gimp_layer_scale(logo_layer,
                                     int(current_width * resize_percent),
                                     int(current_height * resize_percent),
                                     True)
                
                write_log("Logo resized to {0}% to match 50% of top margin height".format(resize_percent * 100))
                
                # Position logo (ensure integers)
                # Move to align with first cell
                new_x = int(first_cell_x)
                new_y = int((top_margin_height / 2) - (logo_layer.height / 2))
                
                pdb.gimp_layer_set_offsets(logo_layer, new_x, new_y)
                write_log("Logo positioned at {0}, {1}".format(new_x, new_y))
            else:
                write_log("Logo file does not exist at: {0}".format(logo_folder_path))
        except Exception as e:
            write_log("Error during logo process: {0}".format(e))
    
    # Create a layer with size information in Board Content group
    try:
        # Round dimensions for clarity (ensure integers)
        max_cell_width_without_margin = int(round(px_cell_width))
        max_cell_height_without_margin = int(round(px_cell_height))
        
        # Create text for display
        size_info_text = "Img max size w x h : {0} x {1} px".format(max_width, max_height)
        
        # Create text layer in Board Content group
        if has_layer_groups:
            parent_for_info = board_content_group
        else:
            parent_for_info = board_content_layer
        
        # Create text layer
        size_info_layer = pdb.gimp_text_fontname(
            img, None, 10, 10, size_info_text, 0,
            True, 12, PIXELS, "Sans"
        )
        
        pdb.gimp_item_set_name(size_info_layer, size_info_text)
        
        # Move to board content group
        if has_layer_groups:
            pdb.gimp_image_reorder_item(img, size_info_layer, parent_for_info, 0)
        
        write_log("Size info layer created with text: {0}".format(size_info_text))
    except Exception as e:
        write_log("Error creating size info layer: {0}".format(e))
    
    # Ecrire les metadonnees overlay dans le fichier .board
    if overlay_files and overlay_indexes:
        try:
            write_log("Writing overlay metadata to .board file")
            write_overlay_metadata_to_dit(dit_path, overlay_files, overlay_indexes)
        except Exception as e:
            write_log("Error writing overlay metadata: {0}".format(e))
    
    # Save the file FIRST (before display)
    try:
        write_log("Saving to XCF file: {0}".format(xcf_path))
        pdb.gimp_xcf_save(0, img, img.layers[0], xcf_path, xcf_path)
        write_log("File saved successfully")
        
        # Mark the image as clean (no unsaved changes)
        pdb.gimp_image_clean_all(img)
        
        # Set the filename for the image
        pdb.gimp_image_set_filename(img, xcf_path)
    except Exception as e:
        write_log("Error saving file: {0}".format(e))
    
    # NOW create the display - GIMP will show the saved file
    display = pdb.gimp_display_new(img)
    
    # Return the image for GIMP to display
    return img

# Register the function with GIMP
# Enregistrer le plugin GIMP
# Plugin registration
register(
    "Open_Board",
    "Open Board - Create a board layout for organizing images",
    "Creates an optimized layout with cells for placing images. Cells are auto-scaled to fit the board canvas while maintaining aspect ratio.",
    "Yan Senez",
    "Yan Senez",
    "2025",
    "<Toolbox>/File/Open Board/Create Board...",
    "",
    [
        # ════════════════════════════════════════════════════════════════
        # INTERFACE
        # ════════════════════════════════════════════════════════════════
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  📋 PROJECT SETTINGS                                        │
        # └─────────────────────────────────────────────────────────────┘
        (PF_STRING, "board_name", "─────────── 📋 PROJECT ───────────\nBoard Name", "MyBoard"),
        (PF_DIRNAME, "dest_folder", "Destination Folder", ""),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  📐 BOARD CANVAS                                            │
        # └─────────────────────────────────────────────────────────────┘
        (PF_OPTION, "layout_units", "─────────── 📐 BOARD CANVAS ───────────\nCanvas Units", 0, ("px", "mm", "cm", "in", "pt")),
        (PF_FLOAT, "layout_resolution", "Resolution (DPI)", 300),
        (PF_FLOAT, "layout_width", "Canvas Width", 4961),
        (PF_FLOAT, "layout_height", "Canvas Height", 3508),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  🔲 CELL GRID (desired dimensions)                          │
        # └─────────────────────────────────────────────────────────────┘
        (PF_INT, "nbr_col", "─────────── 🔲 CELL GRID ───────────\nColumns", 3),
        (PF_INT, "nbr_row", "Rows", 4),
        (PF_OPTION, "cell_type", "Cell Type", 1, ("single", "spread")),
        (PF_OPTION, "cell_units", "Cell Units", 2, ("px", "mm", "cm", "in", "pt")),  # Default: cm (index 2)
        (PF_FLOAT, "cell_width", "Desired Cell Width", 80),
        (PF_FLOAT, "cell_height", "Desired Cell Height", 50),
        (PF_FLOAT, "margin_mask", "Desired Margin", 2),
        (PF_OPTION, "spacing_units", "Spacing Units", 1, ("px", "mm", "cm", "in", "pt")),  # Default: mm (index 1)
        (PF_FLOAT, "layout_spacing", "Desired Spacing", 40),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  🎨 COLORS                                                  │
        # └─────────────────────────────────────────────────────────────┘
        (PF_COLOR, "bg_color_hex", "─────────── 🎨 COLORS ───────────\nBackground Color", (255, 255, 255)),
        (PF_COLOR, "border_color_hex", "Border Color", (200, 200, 200)),
        (PF_COLOR, "layout_color_hex", "Layout Mask Color", (0, 0, 0)),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  ✏️  BOARD EXTRAS                                           │
        # └─────────────────────────────────────────────────────────────┘
        (PF_STRING, "baseline_text", "─────────── ✏️  LEGEND ───────────\nLegend Text", "My Board"),
        (PF_FONT, "selected_font", "Legend Font", "Sans"),
        (PF_FLOAT, "baseline_text_size", "Legend Text Size", 36),
        (PF_COLOR, "baseline_text_color_hex", "Legend Text Color", (255, 255, 255)),
        (PF_FILE, "logo_folder_path", "Logo File (optional)", ""),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  🎭 OVERLAY MASK                                            │
        # └─────────────────────────────────────────────────────────────┘
        (PF_TOGGLE, "overlay_mask_on", "─────────── 🎭 OVERLAY MASK ───────────\nEnable Overlay Mask", False),
        (PF_FILE, "overlay_file_path", "Overlay File (single file)", ""),
        (PF_DIRNAME, "overlay_folder_path", "Overlay Folder (all files)", ""),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  ⚙️  ADVANCED OPTIONS                                       │
        # └─────────────────────────────────────────────────────────────┘
        (PF_TOGGLE, "should_create_guides", "─────────── ⚙️  OPTIONS ───────────\nCreate Guides", False),
        (PF_TOGGLE, "drop_zone", "Create Drop Zone", False),
    ],
    [],
    create_board_layout
)

main()
