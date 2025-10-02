#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Add Image Names - GIMP Script
# Add image names under each cell in the board layout
# By Yan Senez
# Version 1.0

from gimpfu import *
import os
import time

# Variables globales pour les logs
# Global variables for logs
log_file_path = None

def write_log(message):
    """Ecrire un message dans le log
    Write a message to the log"""
    global log_file_path
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    full_message = "{0} - {1}".format(timestamp, message)
    
    # Toujours afficher dans la console
    # Always display in console
    print(full_message)
    
    # Ecrire dans le fichier log si le chemin est defini
    # Write to log file if path is defined
    if log_file_path:
        try:
            with open(log_file_path, 'a') as f:
                f.write(full_message + '\n')
        except Exception as e:
            print("Error writing log: {0}".format(e))

def read_dit_file(dit_path):
    """Lire le fichier .board et extraire les coordonnees des cellules
    Read the .board file and extract cell coordinates"""
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
        return {
            'cells': cells,
            'metadata': metadata
        }
    except Exception as e:
        write_log("ERROR reading BOARD file: {0}".format(e))
        return None

def remove_file_extension(filename):
    """Supprimer l'extension d'un nom de fichier
    Remove file extension from filename"""
    last_dot = filename.rfind('.')
    if last_dot == -1:
        return filename
    return filename[:last_dot]

def convert_color_to_rgb(color_param):
    """Convertir un parametre de couleur GIMP en tuple RGB (0-255)
    Convert a GIMP color parameter to RGB tuple (0-255)"""
    try:
        # Si c'est un objet gimpcolor.RGB (valeurs entre 0.0 et 1.0)
        # If it's a gimpcolor.RGB object (values between 0.0 and 1.0)
        if hasattr(color_param, 'r') and hasattr(color_param, 'g') and hasattr(color_param, 'b'):
            r = int(color_param.r * 255)
            g = int(color_param.g * 255)
            b = int(color_param.b * 255)
            return (r, g, b)
        # Si c'est deja un tuple RGB
        # If it's already an RGB tuple
        elif isinstance(color_param, (tuple, list)) and len(color_param) >= 3:
            return (int(color_param[0]), int(color_param[1]), int(color_param[2]))
        else:
            # Valeur par defaut: noir
            # Default value: black
            return (0, 0, 0)
    except Exception as e:
        write_log("Error converting color: {0}".format(e))
        return (0, 0, 0)

def add_image_names_to_board(img, drawable, text_font, text_size, text_color, text_offset):
    """Fonction principale pour ajouter les noms des images sous les cellules
    Main function to add image names under cells
    
    Parameters:
    - img: L'image GIMP active / Active GIMP image
    - drawable: Le calque actif / Active layer
    - text_font: Police de caracteres a utiliser / Font to use
    - text_size: Taille du texte en pixels / Text size in pixels
    - text_color: Couleur du texte (objet gimpcolor.RGB ou tuple) / Text color (gimpcolor.RGB object or tuple)
    - text_offset: Distance entre le bas de la cellule et le texte en pixels / Distance between cell bottom and text in pixels
    """
    global log_file_path
    
    try:
        write_log("====== Starting Add Image Names for GIMP ======")
        
        # Convertir la couleur en RGB (0-255)
        # Convert color to RGB (0-255)
        rgb_color = convert_color_to_rgb(text_color)
        write_log("Text settings - Font: {0}, Size: {1}, Color: RGB{2}, Offset: {3}px".format(
            text_font, text_size, rgb_color, text_offset))
        
        # Obtenir le chemin du fichier XCF
        # Get the XCF file path
        xcf_path = pdb.gimp_image_get_filename(img)
        if not xcf_path:
            pdb.gimp_message("Please save the document first")
            write_log("ERROR: Document not saved")
            return
        
        write_log("Document path: {0}".format(xcf_path))
        
        # Construire le chemin du fichier .board
        # Build the .board file path
        board_dir = os.path.dirname(xcf_path)
        board_name = os.path.splitext(os.path.basename(xcf_path))[0]
        dit_path = os.path.join(board_dir, "{0}.board".format(board_name))
        
        # Initialiser le log
        # Initialize log
        log_file_path = os.path.join(board_dir, "{0}_add_names.log".format(board_name))
        
        write_log("BOARD file path: {0}".format(dit_path))
        
        # Verifier si le fichier .board existe
        # Check if .board file exists
        if not os.path.exists(dit_path):
            pdb.gimp_message("Board file not found. Please open a valid board XCF file.")
            write_log("ERROR: BOARD file not found")
            return
        
        # Lire le fichier .board
        # Read the .board file
        board_data = read_dit_file(dit_path)
        if not board_data:
            pdb.gimp_message("Error reading board file")
            return
        
        # Recuperer les metadonnees
        # Get metadata
        adjusted_margin = float(board_data['metadata'].get('adjustedMargin', 0))
        adjusted_spacing = float(board_data['metadata'].get('adjustedSpacing', 40))
        img_max_height = float(board_data['metadata'].get('imgMaxHeight', 0))
        
        write_log("Using adjustedMargin: {0}, adjustedSpacing: {1}, imgMaxHeight: {2}".format(
            adjusted_margin, adjusted_spacing, img_max_height))
        
        # Trouver le groupe Board Elements
        # Find the Board Elements group
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
        
        # Supprimer le groupe Image Names s'il existe deja (TOUJOURS au demarrage)
        # Remove Image Names group if it already exists (ALWAYS at startup)
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
            write_log("No existing 'Image Names' group found (first run or already clean)")
        
        # Creer un nouveau groupe pour les noms d'images
        # Create a new group for image names
        write_log("Creating new 'Image Names' group...")
        image_names_group = pdb.gimp_layer_group_new(img)
        pdb.gimp_item_set_name(image_names_group, "Image Names")
        pdb.gimp_image_insert_layer(img, image_names_group, board_elements_group, 0)
        write_log("New 'Image Names' group created successfully")
        
        # Collecter tous les calques d'images dans Board Content avec leurs positions
        # Collect all image layers in Board Content with their positions
        content_layers = []
        
        if hasattr(board_content_group, 'children') and board_content_group.children:
            for child in board_content_group.children:
                if not pdb.gimp_item_is_group(child):
                    # Obtenir les offsets et dimensions du calque
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
        
        # Trier les calques par position Y puis X
        # Sort layers by Y then X position
        content_layers.sort(key=lambda x: (x['top'], x['left']))
        
        # Recuperer les cellules depuis le fichier .board
        # Get cells from .board file
        cells = board_data.get('cells', [])
        write_log("Found {0} cells in board data".format(len(cells)))
        
        # Recuperer le type de cellule depuis les metadonnees
        # Get cell type from metadata
        cell_type = board_data['metadata'].get('cellType', 'single')
        write_log("Board cell type: {0}".format(cell_type))
        
        # Commencer le groupe undo
        # Start undo group
        pdb.gimp_image_undo_group_start(img)
        
        write_log("Starting to process {0} image layers...".format(len(content_layers)))
        
        # Parcourir tous les calques tries
        # Loop through all sorted layers
        for i, layer_info in enumerate(content_layers):
            write_log("Processing layer {0}/{1}: {2}".format(
                i + 1, len(content_layers), layer_info['name']))
            
            # Extraire le nom du fichier (sans extension)
            # Extract file name (without extension)
            file_name = remove_file_extension(layer_info['name'])
            
            # Trouver la cellule correspondante a cette image
            # On utilise le centre de l'image pour determiner dans quelle cellule elle se trouve
            # Find the matching cell for this image
            # We use the image center to determine which cell it belongs to
            matching_cell = None
            for cell in cells:
                cell_left = cell['topLeft'][0]
                cell_top = cell['topLeft'][1]
                cell_right = cell['topRight'][0]
                cell_bottom = cell['bottomLeft'][1]
                
                # Verifier si le centre de l'image est dans cette cellule
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
            
            # Calculer la position du texte SOUS l'image
            # Calculate text position UNDER the image
            cell_left = matching_cell['topLeft'][0]
            cell_right = matching_cell['topRight'][0]
            cell_bottom = matching_cell['bottomLeft'][1]
            cell_width = cell_right - cell_left
            
            # Position Y = sous le bas de la cellule + offset defini par l'utilisateur
            # Position Y = below cell bottom + user-defined offset
            pos_y = cell_bottom + text_offset
            
            # Position X depend du type de cellule et de la position de l'image
            # Position X depends on cell type and image position
            if cell_type.lower() == "spread":
                # En mode spread, determiner si l'image est a gauche ou a droite
                # In spread mode, determine if image is on left or right
                cell_center_x = cell_left + (cell_width / 2)
                
                if layer_info['center_x'] < cell_center_x:
                    # Image a gauche
                    # Image on left
                    center_x = cell_left + (cell_width / 4)
                    write_log("Spread mode: image on LEFT side of cell {0}".format(matching_cell['index']))
                else:
                    # Image a droite
                    # Image on right
                    center_x = cell_left + (3 * cell_width / 4)
                    write_log("Spread mode: image on RIGHT side of cell {0}".format(matching_cell['index']))
            else:
                # En mode single, centrer sur toute la cellule
                # In single mode, center over entire cell
                center_x = (cell_left + cell_right) / 2
                write_log("Single mode: centering text under cell {0}".format(matching_cell['index']))
            
            write_log("Creating text '{0}' at position ({1}, {2})".format(
                file_name, int(center_x), int(pos_y)))
            
            # Creer le calque de texte
            # Create text layer
            text_layer = pdb.gimp_text_fontname(
                img, None, 
                center_x, pos_y,
                file_name,
                0,  # border
                True,  # antialias
                text_size,  # Taille specifiee par l'utilisateur / User-specified size
                PIXELS,
                text_font  # Police specifiee par l'utilisateur / User-specified font
            )
            
            # Definir la couleur du texte
            # Set text color
            pdb.gimp_text_layer_set_color(text_layer, rgb_color)
            
            # Centrer le texte horizontalement
            # Center text horizontally
            text_width = pdb.gimp_drawable_width(text_layer)
            new_x = int(center_x - (text_width / 2))
            pdb.gimp_layer_set_offsets(text_layer, new_x, int(pos_y))
            
            # Deplacer le calque dans le groupe Image Names
            # Move layer into Image Names group
            pdb.gimp_image_reorder_item(img, text_layer, image_names_group, 0)
        
        # Terminer le groupe undo
        # End undo group
        pdb.gimp_image_undo_group_end(img)
        
        # Rafraichir l'affichage
        # Refresh display
        pdb.gimp_displays_flush()
        
        write_log("====== Add Image Names completed successfully ======")
        write_log("Total images processed: {0}".format(len(content_layers)))
        pdb.gimp_message("Image names added successfully! ({0} images)".format(len(content_layers)))
        
    except Exception as e:
        write_log("ERROR in add_image_names_to_board: {0}".format(e))
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()))
        pdb.gimp_message("Error adding image names: {0}".format(e))
        
        # Terminer le groupe undo en cas d'erreur
        # End undo group in case of error
        try:
            pdb.gimp_image_undo_group_end(img)
        except:
            pass

# Enregistrement du plugin
# Plugin registration
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
        # ┌─────────────────────────────────────────────────────────────┐
        # │  ✏️  TEXT SETTINGS                                          │
        # └─────────────────────────────────────────────────────────────┘
        (PF_FONT, "text_font", "─────────── ✏️  TEXT SETTINGS ───────────\nFont", "Sans"),
        (PF_FLOAT, "text_size", "Text Size (px)", 12.0),
        (PF_COLOR, "text_color", "Text Color", (0, 0, 0)),
        (PF_FLOAT, "text_offset", "Distance from Cell (px)", 10.0)
    ],
    [],
    add_image_names_to_board
)

main()

