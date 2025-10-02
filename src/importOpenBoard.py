#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GIMP Board Import Script
Imports images into an existing board layout created with createGimpBoard.py
Compatible with GIMP 2.10 (Python 2.7)

Script d'import de planches GIMP
Importe des images dans une planche existante créée avec createGimpBoard.py
Compatible avec GIMP 2.10 (Python 2.7)
"""

from gimpfu import *
import os
import math
import time

# Global variables for logging
# Variables globales pour les logs
log_messages = []
log_file_path = None

def write_log(message):
    """Ecrire un message dans le log
    Write a message to the log"""
    global log_messages, log_file_path
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    full_message = "{0} - {1}".format(timestamp, message)
    log_messages.append(full_message)
    
    # Ecrire dans le fichier log si le chemin est defini
    # Write to log file if path is defined
    if log_file_path:
        try:
            with open(log_file_path, 'a') as f:
                f.write(full_message + '\n')
        except Exception as e:
            pdb.gimp_message("Error writing log: {0}".format(e))

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
    """Placer un overlay dans une cellule
    Place an overlay in a cell
    
    Parameters:
    - img: L'image GIMP active / Active GIMP image
    - overlay_path: Chemin du fichier overlay / Overlay file path
    - cell_x, cell_y: Position de la cellule / Cell position
    - cell_width, cell_height: Dimensions de la cellule / Cell dimensions
    - cell_type: "single" ou "spread" / "single" or "spread"
    - overlay_group: Groupe de calques pour les overlays / Layer group for overlays
    - position_info: Informations de placement calculees / Calculated placement information
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
        # In spread mode, pairs stay together
        pair_index = ((cell_number % 2) * 2) % overlay_files_count
        return pair_index
    else:
        # En mode single, sequence simple
        # In single mode, simple sequence
        return cell_number % overlay_files_count

def save_last_cell_index(board_path, cell_index):
    """Sauvegarder l'index de la derniere cellule utilisee
    Save the index of the last used cell
    """
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
    """Charger l'index de la derniere cellule utilisee
    Load the index of the last used cell
    """
    try:
        board_dir = os.path.dirname(board_path)
        board_name = os.path.splitext(os.path.basename(board_path))[0]
        index_file = os.path.join(board_dir, "{0}_last_cell.txt".format(board_name))
        
        if os.path.exists(index_file):
            with open(index_file, "r") as f:
                index = int(f.read().strip())
            write_log("Loaded last cell index: {0}".format(index))
            return index
        else:
            write_log("No last cell index found, starting from 0")
            return 0
    except Exception as e:
        write_log("ERROR loading last cell index: {0}".format(e))
        return 0

def read_dit_file(dit_path):
    """Lire le fichier .board et extraire les coordonnees des cellules
    Read the .board file and extract cell coordinates
    
    Format: index,topLeftX,topLeftY,bottomLeftX,bottomLeftY,bottomRightX,bottomRightY,topRightX,topRightY
    """
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
                
                # Ignorer les lignes vides
                if not line:
                    continue
                
                # Traiter les metadonnees (lignes commencant par #)
                if line.startswith('#'):
                    parts = line[1:].split('=', 1)  # Limite à 2 parts pour les valeurs JSON
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        
                        # Traiter spécialement overlayFiles qui est en JSON
                        if key == 'overlayFiles':
                            try:
                                import json
                                overlay_files = json.loads(value)
                                write_log("Found overlay files in .board: {0} files".format(len(overlay_files)))
                            except Exception as e:
                                write_log("ERROR parsing overlayFiles JSON: {0}".format(e))
                        else:
                            metadata[key] = value
                            write_log("Metadata: {0} = {1}".format(key, value))
                else:
                    # Traiter les coordonnees des cellules
                    # Format: index,topLeftX,topLeftY,bottomLeftX,bottomLeftY,bottomRightX,bottomRightY,topRightX,topRightY
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
                            # Ajouter minX, minY, maxX, maxY pour la compatibilite
                            'minX': top_left_x,
                            'minY': top_left_y,
                            'maxX': bottom_right_x,
                            'maxY': bottom_right_y
                        }
                        cells.append(cell)
        
        write_log("Successfully read {0} cells from BOARD file".format(len(cells)))
        return {
            'cells': cells,
            'metadata': metadata,
            'overlay_files': overlay_files
        }
    except Exception as e:
        write_log("ERROR reading BOARD file: {0}".format(e))
        return None

def find_empty_cells(img, board_content_group):
    """Trouver les cellules vides dans le board
    Find empty cells in the board
    
    Une cellule est vide si elle n'a pas de calque d'image a l'interieur du groupe Board Content
    A cell is empty if it has no image layer inside the Board Content group
    """
    write_log("Searching for empty cells in Board Content group")
    
    if not board_content_group:
        write_log("ERROR: Board Content group not found")
        return []
    
    # Obtenir tous les calques du groupe Board Content
    try:
        num_children = pdb.gimp_item_get_children(board_content_group)[0]
        write_log("Found {0} layers in Board Content group".format(num_children))
        
        # Pour simplifier, retourner toutes les cellules comme vides
        # L'utilisateur choisira ou placer les images
        return []
    except Exception as e:
        write_log("ERROR finding empty cells: {0}".format(e))
        return []

def get_image_orientation(image_path):
    """Determiner l'orientation d'une image (Portrait ou Landscape)
    Determine image orientation (Portrait or Landscape)"""
    try:
        # Charger l'image temporairement pour obtenir ses dimensions
        temp_img = pdb.gimp_file_load(image_path, image_path)
        width = temp_img.width
        height = temp_img.height
        pdb.gimp_image_delete(temp_img)
        
        if width > height:
            return "Landscape"
        else:
            return "Portrait"
    except Exception as e:
        write_log("ERROR getting image orientation: {0}".format(e))
        return "Portrait"

def place_image_in_cell(img, image_path, cell, cell_type, resize_mode, board_metadata, all_cells, use_side="left"):
    """Placer une image dans une cellule - Logique exacte du script Photoshop
    Place an image in a cell - Exact logic from Photoshop script
    
    Parameters:
    - img: L'image GIMP active / Active GIMP image
    - image_path: Chemin de l'image a placer / Image path to place
    - cell: Dict avec les coordonnees de la cellule / Dict with cell coordinates
    - all_cells: Liste de toutes les cellules (pour calculer row/col) / List of all cells (to calculate row/col)
    - cell_type: "single" ou "spread" / "single" or "spread"
    - resize_mode: "fit", "cover" ou "noResize" / "fit", "cover" or "noResize"
    - board_metadata: Metadonnees du board (pour les marges) / Board metadata (for margins)
    """
    write_log("====== Placing image in cell {0} ======".format(cell['index']))
    write_log("Image: {0}".format(image_path))
    write_log("Cell type: {0}, Resize mode: {1}".format(cell_type, resize_mode))
    
    try:
        # Calculer les dimensions de la cellule
        cell_left = cell['topLeft'][0]
        cell_top = cell['topLeft'][1]
        cell_right = cell['topRight'][0]
        cell_bottom = cell['bottomLeft'][1]
        
        cell_width = int(cell_right - cell_left)
        cell_height = int(cell_bottom - cell_top)
        
        write_log("Cell dimensions: {0}x{1} at position ({2},{3})".format(
            cell_width, cell_height, cell_left, cell_top))
        
        # Charger l'image
        write_log("Loading image: {0}".format(image_path))
        loaded_image = pdb.gimp_file_load(image_path, image_path)
        
        # Obtenir le calque de l'image chargee
        source_layer = loaded_image.active_layer
        if not source_layer:
            source_layer = loaded_image.layers[0]
        
        img_width = source_layer.width
        img_height = source_layer.height
        
        write_log("Image dimensions: {0}x{1}".format(img_width, img_height))
        
        # Determiner l'orientation
        orientation = "Landscape" if img_width > img_height else "Portrait"
        write_log("Image orientation: {0}".format(orientation))
        
        # ETAPE 1: Determiner l'espace cible (cellule entiere ou demi-cellule)
        use_full_cell = False
        
        if cell_type.lower() == "single":
            # Pour une cellule Single, on utilise toujours la cellule entiere
            use_full_cell = True
            write_log("Single cell: using full cell")
        elif cell_type.lower() == "spread":
            if orientation == "Landscape":
                # Image paysage en mode spread: utiliser la cellule entiere
                use_full_cell = True
                write_log("Spread cell with landscape image: using full cell")
            else:
                # Image portrait en mode spread: utiliser une demi-cellule
                use_full_cell = False
                write_log("Spread cell with portrait image: using half cell")
        
        # ETAPE 2: Calculer les dimensions cibles en fonction de l'espace
        # Lire la marge depuis les metadonnees du board
        margin_size = 0
        if board_metadata and 'adjustedMargin' in board_metadata:
            margin_size = float(board_metadata['adjustedMargin'])
            write_log("Using margin from board metadata: {0}px".format(margin_size))
        else:
            write_log("No margin found in board metadata, using zero margin")
        
        if use_full_cell:
            # Pour une cellule complete (Single ou Spread), on soustrait 2 * marginSize
            target_width = cell_width - (2 * margin_size)
            target_height = cell_height - (2 * margin_size)
            write_log("Using FULL cell with dimensions: {0}x{1} (with margins)".format(target_width, target_height))
        else:
            # Pour une demi-cellule (Spread avec image portrait)
            target_width = (cell_width / 2) - (2 * margin_size)
            target_height = cell_height - (2 * margin_size)
            write_log("Using HALF cell with dimensions: {0}x{1} (with margins)".format(target_width, target_height))
        
        # ETAPE 3: Appliquer la logique de redimensionnement selon le mode et l'orientation
        if resize_mode == "noResize":
            # Garder la taille originale
            final_width = img_width
            final_height = img_height
            write_log("No resize mode: keeping original size")
        else:
            # Calculer les ratios
            width_ratio = float(target_width) / float(img_width)
            height_ratio = float(target_height) / float(img_height)
            
            write_log("Width ratio: {0}, Height ratio: {1}".format(width_ratio, height_ratio))
            
            if resize_mode == "cover":
                # En mode cover, on utilise le ratio maximum pour s'assurer que l'image couvre toute la zone
                ratio = max(width_ratio, height_ratio)
                write_log("Cover mode: using maximum ratio: {0}".format(ratio))
            elif resize_mode == "fit":
                # En mode fit, on utilise le ratio minimum pour s'assurer que l'image tient dans la zone
                ratio = min(width_ratio, height_ratio)
                write_log("Fit mode: using minimum ratio: {0}".format(ratio))
            else:
                # Par defaut, utiliser le mode cover
                ratio = max(width_ratio, height_ratio)
                write_log("Default mode: using maximum ratio: {0}".format(ratio))
            
            # Calculer les nouvelles dimensions
            final_width = int(img_width * ratio)
            final_height = int(img_height * ratio)
            
            write_log("Final dimensions after resize: {0}x{1}".format(final_width, final_height))
            
            # Redimensionner le calque
            pdb.gimp_layer_scale(source_layer, final_width, final_height, True)
        
        # ETAPE 4: Calculer la position cible basée sur l'orientation et le type de cellule
        if cell_type.lower() == "single":
            # Pour une cellule Single, centrer l'image
            target_x = cell_left + (cell_width - final_width) / 2
            target_y = cell_top + (cell_height - final_height) / 2
            write_log("Image centered in a Single cell")
        elif cell_type.lower() == "spread":
            if orientation == "Landscape":
                # Image paysage en mode spread: centrer sur toute la largeur
                target_x = cell_left + (cell_width - final_width) / 2
                target_y = cell_top + (cell_height - final_height) / 2
                write_log("Landscape image centered in a Spread cell (spread mode)")
            else:
                # Image portrait: centrer dans la moitie gauche ou droite selon use_side
                half_width = cell_width / 2
                if use_side == "left":
                    target_x = cell_left + (half_width - final_width) / 2
                    write_log("Portrait image centered in the LEFT half of a Spread cell")
                else:  # right
                    target_x = cell_left + half_width + (half_width - final_width) / 2
                    write_log("Portrait image centered in the RIGHT half of a Spread cell")
                target_y = cell_top + (cell_height - final_height) / 2
        
        write_log("Final position: ({0},{1})".format(target_x, target_y))
        
        # Copier le calque dans l'image de destination
        write_log("Copying layer to destination image")
        new_layer = pdb.gimp_layer_new_from_drawable(source_layer, img)
        pdb.gimp_image_insert_layer(img, new_layer, None, 0)
        
        # Renommer le calque
        layer_name = os.path.splitext(os.path.basename(image_path))[0]
        pdb.gimp_item_set_name(new_layer, layer_name)
        
        # Positionner le calque
        pdb.gimp_layer_set_offsets(new_layer, int(target_x), int(target_y))
        
        # ETAPE 5: Creer le masque selon la logique exacte du script Photoshop
        try:
            write_log("Creating mask for image layer")
            
            # Determiner les dimensions du masque selon le type de cellule
            if cell_type.lower() == "single":
                # Masque pour toute la cellule
                mask_left = cell_left
                mask_top = cell_top
                mask_right = cell_right
                mask_bottom = cell_bottom
                write_log("Single cell mask: full cell dimensions")
            elif cell_type.lower() == "spread":
                if orientation == "Landscape":
                    # Masque pour toute la cellule sans marges en mode spread
                    mask_left = cell_left
                    mask_top = cell_top
                    mask_right = cell_right
                    mask_bottom = cell_bottom
                    write_log("Spread cell mask (landscape): full cell dimensions")
                else:
                    # Portrait: masque sur la moitie gauche ou droite selon use_side
                    half_width = cell_width / 2
                    if use_side == "left":
                        mask_left = cell_left
                        mask_right = cell_left + half_width
                        write_log("Spread cell mask (portrait): left half dimensions")
                    else:  # right
                        mask_left = cell_left + half_width
                        mask_right = cell_right
                        write_log("Spread cell mask (portrait): right half dimensions")
                    mask_top = cell_top
                    mask_bottom = cell_bottom
            
            # Creer un masque de calque
            mask = pdb.gimp_layer_create_mask(new_layer, ADD_ALPHA_MASK)
            pdb.gimp_layer_add_mask(new_layer, mask)
            
            # Creer une selection rectangulaire pour le masque
            pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE, 
                                          int(mask_left), int(mask_top), 
                                          int(mask_right - mask_left), int(mask_bottom - mask_top))
            
            # Remplir la selection avec du blanc (visible)
            pdb.gimp_context_set_foreground((255, 255, 255))
            pdb.gimp_edit_fill(mask, FILL_FOREGROUND)
            pdb.gimp_selection_none(img)
            
            write_log("Mask created successfully with bounds: ({0},{1}) to ({2},{3})".format(
                mask_left, mask_top, mask_right, mask_bottom))
        except Exception as e:
            write_log("WARNING: Could not create mask: {0}".format(e))
        
        # ETAPE 6: Gérer la visibilité du groupe "Simple page Mask" selon l'orientation et le mode
        if cell_type.lower() == "spread":
            try:
                write_log("Managing Simple page Mask visibility for {0} image in spread mode".format(orientation))
                
                # Trouver le groupe Board Elements
                board_elements_group = None
                for layer in img.layers:
                    if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Elements":
                        board_elements_group = layer
                        break
                
                if board_elements_group:
                    # S'assurer que le groupe Board Elements est visible
                    if not pdb.gimp_item_get_visible(board_elements_group):
                        write_log("Board Elements group was invisible, making it visible")
                        pdb.gimp_item_set_visible(board_elements_group, True)
                    
                    # Trouver le groupe Simple page Mask
                    simple_page_group = None
                    for child in board_elements_group.children:
                        if pdb.gimp_item_is_group(child) and pdb.gimp_item_get_name(child) == "Simple page Mask":
                            simple_page_group = child
                            break
                    
                    if simple_page_group:
                        # S'assurer que le groupe Simple page Mask est visible
                        # Sinon, meme si on active les calques a l'interieur, ils ne seront pas visibles
                        if not pdb.gimp_item_get_visible(simple_page_group):
                            write_log("Simple page Mask group was invisible, making it visible")
                            pdb.gimp_item_set_visible(simple_page_group, True)
                        
                        # Construire le nom du masque basé sur la position dans la grille (R{row}C{col})
                        # IMPORTANT: Après une extension de board, les cellules ne sont plus
                        # numérotées en row-major order. Il faut donc calculer row/col
                        # à partir des coordonnées réelles de TOUTES les cellules.
                        
                        cell_index = cell['index']
                        
                        # Analyser toutes les cellules pour créer un mapping position -> row/col
                        # 1. Récupérer toutes les positions Y uniques (triées) pour déterminer les rows
                        unique_y_positions = sorted(set(c['minY'] for c in all_cells))
                        # 2. Récupérer toutes les positions X uniques (triées) pour déterminer les cols
                        unique_x_positions = sorted(set(c['minX'] for c in all_cells))
                        
                        write_log("Position mapping: {0} unique Y positions (rows), {1} unique X positions (cols)".format(
                            len(unique_y_positions), len(unique_x_positions)))
                        write_log("Y positions: {0}".format(unique_y_positions))
                        write_log("X positions: {0}".format(unique_x_positions))
                        
                        # 3. Créer des mappings position -> numéro (1-based)
                        y_to_row = {y: idx + 1 for idx, y in enumerate(unique_y_positions)}
                        x_to_col = {x: idx + 1 for idx, x in enumerate(unique_x_positions)}
                        
                        # 4. Déterminer le row et col de notre cellule
                        current_y = cell['minY']
                        current_x = cell['minX']
                        
                        write_log("Current cell position: Y={0}, X={1}".format(current_y, current_x))
                        
                        row = y_to_row.get(current_y)
                        col = x_to_col.get(current_x)
                        
                        if row is None or col is None:
                            # Fallback: chercher la position la plus proche (avec tolérance)
                            write_log("WARNING: Exact position not found, searching with tolerance")
                            for y_pos in unique_y_positions:
                                if abs(y_pos - current_y) < 10:  # 10px de tolérance
                                    row = y_to_row[y_pos]
                                    break
                            for x_pos in unique_x_positions:
                                if abs(x_pos - current_x) < 10:
                                    col = x_to_col[x_pos]
                                    break
                        
                        # Si toujours pas trouvé, utiliser l'ancienne méthode comme fallback final
                        if row is None or col is None:
                            nbr_cols = int(board_metadata.get('nbrCols', 3))
                            row = ((cell_index - 1) // nbr_cols) + 1
                            col = ((cell_index - 1) % nbr_cols) + 1
                            write_log("WARNING: Could not determine row/col from position, using index-based fallback")
                        
                        mask_id = "R{0}C{1}".format(row, col)
                        write_log("Looking for simple page mask: {0} (cell {1} = row {2}, col {3})".format(
                            mask_id, cell_index, row, col))
                        
                        # Lister tous les calques disponibles dans le groupe pour debug
                        available_masks = []
                        for child in simple_page_group.children:
                            if not pdb.gimp_item_is_group(child):
                                available_masks.append(pdb.gimp_item_get_name(child))
                        write_log("Available masks in Simple page Mask group: {0}".format(available_masks))
                        
                        # Parcourir tous les calques du groupe Simple page Mask
                        found_mask = False
                        write_log("Searching for mask '{0}' in {1} children...".format(mask_id, len(simple_page_group.children)))
                        
                        for child in simple_page_group.children:
                            child_name = pdb.gimp_item_get_name(child)
                            is_group = pdb.gimp_item_is_group(child)
                            write_log("  - Child: '{0}' (is_group={1})".format(child_name, is_group))
                            
                            if not is_group and child_name == mask_id:
                                found_mask = True
                                write_log("  ✓ FOUND matching mask: {0}".format(mask_id))
                                
                                # Vérifier l'état actuel avant modification
                                current_visibility = pdb.gimp_item_get_visible(child)
                                write_log("  Current visibility: {0}".format(current_visibility))
                                
                                # Logique identique au script Photoshop:
                                # - Portrait: activer le masque simple page
                                # - Landscape en mode spread: désactiver le masque
                                should_enable = (orientation == "Portrait")
                                write_log("  Setting visibility to: {0} (orientation={1})".format(should_enable, orientation))
                                
                                pdb.gimp_item_set_visible(child, should_enable)
                                
                                # Vérifier que ça a bien été appliqué
                                new_visibility = pdb.gimp_item_get_visible(child)
                                write_log("  New visibility after set: {0}".format(new_visibility))
                                
                                if orientation == "Portrait":
                                    write_log("Simple page mask {0} enabled for portrait image".format(mask_id))
                                else:
                                    write_log("Simple page mask {0} disabled for landscape image in spread mode".format(mask_id))
                                break
                        
                        if not found_mask:
                            write_log("WARNING: Simple page mask {0} not found in group".format(mask_id))
                            write_log("Available masks were: {0}".format(available_masks))
                    else:
                        write_log("WARNING: Simple page Mask group not found in Board Elements")
                else:
                    write_log("WARNING: Board Elements group not found")
                    
            except Exception as e:
                write_log("WARNING: Could not manage Simple page Mask visibility: {0}".format(e))
        
        # Trouver le groupe Board Content
        try:
            board_content_group = None
            for layer in img.layers:
                if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Content":
                    board_content_group = layer
                    break
            
            if board_content_group:
                write_log("Moving layer to Board Content group")
                pdb.gimp_image_reorder_item(img, new_layer, board_content_group, 0)
            else:
                write_log("WARNING: Board Content group not found, layer stays at top level")
        except Exception as e:
            write_log("WARNING: Could not move layer to Board Content group: {0}".format(e))
        
        # Supprimer l'image temporaire
        pdb.gimp_image_delete(loaded_image)
        
        write_log("====== Image placed successfully ======")
        return True
        
    except Exception as e:
        write_log("ERROR placing image: {0}".format(e))
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()))
        return False

def get_layer_actual_bounds(layer):
    """
    Obtenir les bounds REELS du contenu d'un calque
    Comme on ne redimensionne PLUS les calques d'images, on peut utiliser leur position + taille
    
    Returns:
    - (x1, y1, x2, y2): Bounds absolus du contenu, ou None si erreur
    """
    try:
        # Obtenir les offsets (position) et dimensions du calque
        layer_offset_x, layer_offset_y = pdb.gimp_drawable_offsets(layer)
        layer_width = pdb.gimp_drawable_width(layer)
        layer_height = pdb.gimp_drawable_height(layer)
        
        # Les bounds absolus sont: position + dimensions
        return (
            layer_offset_x,
            layer_offset_y,
            layer_offset_x + layer_width,
            layer_offset_y + layer_height
        )
        
    except Exception as e:
        return None

def rectangle_intersects(x1, y1, x2, y2, zone):
    """
    Verifier si un rectangle intersecte avec une zone
    
    Parameters:
    - x1, y1, x2, y2: Coordonnees du rectangle
    - zone: Dict avec minX, minY, maxX, maxY
    
    Returns:
    - bool: True si intersection, False sinon
    """
    return not (x2 <= zone['minX'] or x1 >= zone['maxX'] or y2 <= zone['minY'] or y1 >= zone['maxY'])

def check_cell_occupancy(img, cell, cell_type):
    """
    Verifier si une cellule est vide en analysant les bounds des calques existants
    Methode identique au script Photoshop
    
    Parameters:
    - img: L'image GIMP active
    - cell: Dict avec les coordonnees de la cellule
    - cell_type: "single" ou "spread"
    
    Returns:
    - (left_empty, right_empty): Tuple indiquant si les cotes gauche et droit sont vides
    """
    try:
        write_log("Checking occupancy for cell {0}".format(cell['index']))
        
        # Calculer les dimensions de la cellule
        cell_left = int(cell['topLeft'][0])
        cell_top = int(cell['topLeft'][1])
        cell_right = int(cell['topRight'][0])
        cell_bottom = int(cell['bottomLeft'][1])
        
        cell_width = cell_right - cell_left
        cell_height = cell_bottom - cell_top
        
        write_log("Cell bounds: ({0},{1}) to ({2},{3})".format(cell_left, cell_top, cell_right, cell_bottom))
        
        # Obtenir tous les calques du groupe Board Content
        board_content_layers = []
        try:
            for layer in img.layers:
                if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Content":
                    board_content_layers = layer.children
                    write_log("Found Board Content group with {0} layers".format(len(board_content_layers)))
                    break
        except:
            write_log("Could not access Board Content group")
        
        if cell_type.lower() == "single":
            # Pour une cellule Single, verifier si le centre d'un calque est dans la cellule
            cell_occupied = False
            
            write_log("Single cell zone: ({0},{1}) to ({2},{3})".format(cell_left, cell_top, cell_right, cell_bottom))
            
            for layer in board_content_layers:
                # Ignorer les calques invisibles
                if not pdb.gimp_item_get_visible(layer):
                    write_log("Skipping invisible layer: {0}".format(pdb.gimp_item_get_name(layer)))
                    continue
                
                # CRITIQUE: Obtenir les bounds du CONTENU reel, pas les dimensions du calque
                # Apres redimensionnement, le calque a la taille du canvas mais le contenu est ailleurs
                bounds = get_layer_actual_bounds(layer)
                if bounds is None:
                    write_log("Skipping layer with no content: {0}".format(pdb.gimp_item_get_name(layer)))
                    continue
                
                layer_x1, layer_y1, layer_x2, layer_y2 = bounds
                
                write_log("Layer {0} CONTENT bounds: ({1},{2}) to ({3},{4})".format(
                    pdb.gimp_item_get_name(layer), layer_x1, layer_y1, layer_x2, layer_y2))
                
                # Utiliser le centre du calque pour determiner l'occupation
                layer_center_x = (layer_x1 + layer_x2) / 2
                layer_center_y = (layer_y1 + layer_y2) / 2
                
                write_log("Layer {0} center: ({1},{2})".format(
                    pdb.gimp_item_get_name(layer), int(layer_center_x), int(layer_center_y)))
                
                # Verifier si le centre du calque est dans la cellule
                if (layer_center_x >= cell_left and layer_center_x < cell_right and
                    layer_center_y >= cell_top and layer_center_y < cell_bottom):
                    cell_occupied = True
                    write_log("Single cell occupied by layer: {0} (center-based)".format(pdb.gimp_item_get_name(layer)))
                    break
            
            write_log("Single cell analysis: empty={0}".format(not cell_occupied))
            return (not cell_occupied, not cell_occupied)  # Pour Single, les deux cotes sont identiques
            
        elif cell_type.lower() == "spread":
            # Pour une cellule Spread, analyser les cotes gauche et droit separement
            half_width = cell_width // 2
            cell_center_x = cell_left + half_width
            
            # Definir les zones gauche et droite
            left_zone = {
                'minX': cell_left,
                'minY': cell_top,
                'maxX': cell_left + half_width,
                'maxY': cell_bottom
            }
            right_zone = {
                'minX': cell_left + half_width,
                'minY': cell_top,
                'maxX': cell_right,
                'maxY': cell_bottom
            }
            
            write_log("Left zone: ({0},{1}) to ({2},{3})".format(
                left_zone['minX'], left_zone['minY'], left_zone['maxX'], left_zone['maxY']))
            write_log("Right zone: ({0},{1}) to ({2},{3})".format(
                right_zone['minX'], right_zone['minY'], right_zone['maxX'], right_zone['maxY']))
            
            left_occupied = False
            right_occupied = False
            
            for layer in board_content_layers:
                # Ignorer les calques invisibles
                if not pdb.gimp_item_get_visible(layer):
                    write_log("Skipping invisible layer: {0}".format(pdb.gimp_item_get_name(layer)))
                    continue
                
                # CRITIQUE: Obtenir les bounds du CONTENU reel, pas les dimensions du calque
                bounds = get_layer_actual_bounds(layer)
                if bounds is None:
                    write_log("Skipping layer with no content: {0}".format(pdb.gimp_item_get_name(layer)))
                    continue
                
                layer_x1, layer_y1, layer_x2, layer_y2 = bounds
                layer_height = layer_y2 - layer_y1
                
                write_log("Layer {0} CONTENT bounds: ({1},{2}) to ({3},{4})".format(
                    pdb.gimp_item_get_name(layer), layer_x1, layer_y1, layer_x2, layer_y2))
                
                # Calculer le centre et la largeur du calque
                layer_center_x = (layer_x1 + layer_x2) / 2
                layer_width_actual = layer_x2 - layer_x1
                width_ratio = float(layer_width_actual) / float(cell_width)
                
                write_log("Layer center X: {0}, width: {1} ({2}% of cell)".format(
                    int(layer_center_x), int(layer_width_actual), int(width_ratio * 100)))
                write_log("DEBUG: layer_x1={0}, layer_x2={1}, cell_width={2}, width_ratio={3}".format(
                    int(layer_x1), int(layer_x2), int(cell_width), width_ratio))
                
                # Ignorer les calques trop petits ou mal positionnes (probablement des calques de test)
                if layer_width_actual < 100 or layer_height < 100:
                    write_log("Skipping small layer (likely test layer): {0}".format(pdb.gimp_item_get_name(layer)))
                    continue
                
                # Calculer le centre Y pour la verification de zone
                layer_center_y = (layer_y1 + layer_y2) / 2
                
                # Ignorer les calques qui ne sont pas dans la zone de la cellule
                if (layer_center_x < cell_left - 100 or layer_center_x > cell_right + 100 or
                    layer_center_y < cell_top - 100 or layer_center_y > cell_bottom + 100):
                    write_log("Skipping layer outside cell zone: {0}".format(pdb.gimp_item_get_name(layer)))
                    continue
                
                # Si l'image occupe plus de 60% de la largeur de la cellule, elle occupe les deux cotes
                if width_ratio > 0.6:
                    # Image large (landscape) - occupe les deux cotes si elle intersecte avec les zones
                    left_intersects = rectangle_intersects(layer_x1, layer_y1, layer_x2, layer_y2, left_zone)
                    right_intersects = rectangle_intersects(layer_x1, layer_y1, layer_x2, layer_y2, right_zone)
                    
                    write_log("Wide layer analysis: width_ratio={0}%, left_intersects={1}, right_intersects={2}".format(
                        int(width_ratio * 100), left_intersects, right_intersects))
                    
                    if left_intersects:
                        left_occupied = True
                        write_log("Left side occupied by wide layer: {0}".format(pdb.gimp_item_get_name(layer)))
                    if right_intersects:
                        right_occupied = True
                        write_log("Right side occupied by wide layer: {0}".format(pdb.gimp_item_get_name(layer)))
                    
                    # Si l'image est tres large (plus de 80% de la cellule), elle occupe forcement les deux cotes
                    if width_ratio > 0.8:
                        left_occupied = True
                        right_occupied = True
                        write_log("Very wide layer ({0}% of cell) occupies both sides: {1}".format(
                            int(width_ratio * 100), pdb.gimp_item_get_name(layer)))
                    
                    # Logique supplementaire: si l'image est centree dans la cellule et large, elle occupe les deux cotes
                    image_center_x = (layer_x1 + layer_x2) / 2
                    cell_center_x = cell_left + (cell_width / 2)
                    center_distance = abs(image_center_x - cell_center_x)
                    
                    write_log("Center analysis: image_center={0}, cell_center={1}, distance={2}, threshold={3}".format(
                        int(image_center_x), int(cell_center_x), int(center_distance), int(cell_width * 0.1)))
                    
                    # Si l'image est centree (distance < 10% de la largeur de cellule) et large (>70%), elle occupe les deux cotes
                    if center_distance < (cell_width * 0.1) and width_ratio > 0.7:
                        left_occupied = True
                        right_occupied = True
                        write_log("Centered wide layer ({0}% of cell, center distance: {1}px) occupies both sides: {2}".format(
                            int(width_ratio * 100), int(center_distance), pdb.gimp_item_get_name(layer)))
                else:
                    # Image etroite (portrait) - utiliser le centre pour determiner le cote
                    if not left_occupied and layer_center_x < cell_center_x:
                        left_occupied = True
                        write_log("Left side occupied by narrow layer (center-based): {0}".format(pdb.gimp_item_get_name(layer)))
                    if not right_occupied and layer_center_x >= cell_center_x:
                        right_occupied = True
                        write_log("Right side occupied by narrow layer (center-based): {0}".format(pdb.gimp_item_get_name(layer)))
                
                # Early exit: si les deux cotes sont occupes, pas besoin de continuer
                if left_occupied and right_occupied:
                    write_log("Both sides occupied, early exit")
                    break
            
            write_log("Spread cell analysis: left={0}, right={1}".format(not left_occupied, not right_occupied))
            return (not left_occupied, not right_occupied)
        
        else:
            write_log("WARNING: Unknown cell type: {0}".format(cell_type))
            return (True, True)  # Considerer vide par defaut
            
    except Exception as e:
        write_log("ERROR checking cell occupancy: {0}".format(e))
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()))
        return (True, True)  # En cas d'erreur, considerer vide

def find_empty_cell(img, cells, cell_type, orientation, start_index=0):
    """
    Trouver la prochaine cellule vide disponible en analysant TOUTES les cellules
    L'utilisateur peut reorganiser manuellement le board, le script doit s'adapter
    
    Parameters:
    - img: L'image GIMP active
    - cells: Liste des cellules
    - cell_type: "single" ou "spread"
    - orientation: "Portrait" ou "Landscape"
    - start_index: Index de depart pour la recherche (ignore pour l'instant)
    
    Returns:
    - (cell, use_side): Tuple avec la cellule et le cote a utiliser, ou (None, None) si aucune trouvee
    """
    try:
        write_log("====== Finding empty cell ======")
        write_log("Cell type: {0}, Orientation: {1}".format(cell_type, orientation))
        write_log("Analyzing ALL cells to find the first truly empty one")
        
        # Analyser TOUTES les cellules pour trouver la premiere vraiment vide
        for i in range(len(cells)):
            cell = cells[i]
            write_log("Checking cell {0} (index {1})".format(cell['index'], i))
            
            # Verifier l'occupation de la cellule
            left_empty, right_empty = check_cell_occupancy(img, cell, cell_type)
            
            if cell_type.lower() == "single":
                # Pour une cellule Single, elle est utilisable si elle est vide
                if left_empty:
                    write_log("Single cell {0} is available".format(cell['index']))
                    return (cell, "left")
                else:
                    write_log("Single cell {0} is occupied".format(cell['index']))
                    
            elif cell_type.lower() == "spread":
                if orientation == "Landscape":
                    # Image paysage: besoin des deux cotes vides
                    if left_empty and right_empty:
                        write_log("Spread cell {0} is available for landscape image".format(cell['index']))
                        return (cell, "left")  # Utiliser le cote gauche par defaut
                    else:
                        write_log("Spread cell {0} is not available for landscape image (left={1}, right={2})".format(
                            cell['index'], left_empty, right_empty))
                else:
                    # Image portrait: besoin d'un seul cote vide
                    # PRIORITE: Toujours commencer par le cote gauche
                    if left_empty:
                        write_log("Spread cell {0} is available for portrait image (left side free - PRIORITY)".format(cell['index']))
                        return (cell, "left")
                    elif right_empty:
                        write_log("Spread cell {0} is available for portrait image (right side free - fallback)".format(cell['index']))
                        return (cell, "right")
                    else:
                        write_log("Spread cell {0} is fully occupied (left={1}, right={2})".format(
                            cell['index'], left_empty, right_empty))
        
        write_log("No empty cell found in any cell")
        return (None, None)
        
    except Exception as e:
        write_log("ERROR in find_empty_cell: {0}".format(e))
        return (None, None)

def extend_board(img, dit_path, cells, metadata, extension_direction, cell_type, overlay_files=None):
    """Etendre le board en ajoutant une nouvelle ligne ou colonne
    Extend the board by adding a new row or column
    
    Utilise la meme logique que Photoshop: analyse les positions reelles des cellules existantes
    Uses the same logic as Photoshop: analyzes actual positions of existing cells
    
    Parameters:
    - img: L'image GIMP active / Active GIMP image
    - dit_path: Chemin vers le fichier .board / Path to .board file
    - cells: Liste des cellules existantes / List of existing cells
    - metadata: Metadonnees du board / Board metadata
    - extension_direction: 0=Bottom, 1=Right, 2=Alternate
    - cell_type: "single" ou "spread" / "single" or "spread"
    - overlay_files: Liste des fichiers overlay (optionnel) / List of overlay files (optional)
    
    Returns:
    - True si l'extension a reussi, False sinon / True if extension succeeded, False otherwise
    """
    try:
        write_log("====== Extending board ======")
        write_log("Current cells: {0}".format(len(cells)))
        write_log("Extension direction: {0}".format(["Bottom", "Right", "Alternate"][extension_direction]))
        if overlay_files and len(overlay_files) > 0:
            write_log("Overlays will be created for new cells: {0} files".format(len(overlay_files)))
        
        # Extraire les metadonnees
        nbr_cols = int(metadata.get('nbrCols', 3))
        nbr_rows = int(metadata.get('nbrRows', 4))
        
        # IMPORTANT: Calculer le layout_spacing reel a partir des positions des cellules existantes
        # car il n'est pas toujours stocke dans les metadonnees
        layout_spacing = 40.0  # Valeur par defaut de secours
        
        if len(cells) >= 2:
            # Methode 1: Trouver deux cellules adjacentes horizontalement (meme Y, X differents)
            cells_sorted_by_x = sorted(cells, key=lambda c: (c['minY'], c['minX']))
            
            for i in range(len(cells_sorted_by_x) - 1):
                cell1 = cells_sorted_by_x[i]
                cell2 = cells_sorted_by_x[i + 1]
                
                # Si elles sont sur la meme ligne (meme Y) et adjacentes
                if abs(cell1['minY'] - cell2['minY']) < 10:  # Tolerance de 10px
                    spacing_x = cell2['minX'] - cell1['maxX']
                    if spacing_x > 0:
                        layout_spacing = spacing_x
                        write_log("Calculated horizontal spacing from cells: {0}px".format(layout_spacing))
                        break
            
            # Methode 2: Verifier aussi le spacing vertical pour coherence
            cells_sorted_by_y = sorted(cells, key=lambda c: (c['minX'], c['minY']))
            
            for i in range(len(cells_sorted_by_y) - 1):
                cell1 = cells_sorted_by_y[i]
                cell2 = cells_sorted_by_y[i + 1]
                
                # Si elles sont sur la meme colonne (meme X) et adjacentes
                if abs(cell1['minX'] - cell2['minX']) < 10:  # Tolerance de 10px
                    spacing_y = cell2['minY'] - cell1['maxY']
                    if spacing_y > 0:
                        write_log("Calculated vertical spacing from cells: {0}px (should match horizontal)".format(spacing_y))
                        # Le spacing devrait etre identique en X et Y
                        break
        else:
            write_log("WARNING: Not enough cells to calculate spacing, using default: {0}px".format(layout_spacing))
        
        write_log("Using layout_spacing: {0}px for board extension".format(layout_spacing))
        
        # AJOUT: Recuperer la couleur des borders depuis le calque Borders pour les simple page masks
        border_color = (200, 200, 200)  # Valeur par defaut
        try:
            for layer in img.layers:
                if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Elements":
                    for child in layer.children:
                        if pdb.gimp_item_get_name(child) == "Borders":
                            # Lire la couleur predominante du calque Borders (sample au centre)
                            # Pour simplifier, on utilise la valeur par defaut gris clair
                            border_color = (200, 200, 200)
                            write_log("Using border color for simple page masks: RGB{0}".format(border_color))
                            break
                    break
        except Exception as e:
            write_log("Could not read border color, using default: {0}".format(e))
        
        write_log("Current layout: {0}x{1} cells".format(nbr_cols, nbr_rows))
        
        # Determiner la direction effective d'extension
        effective_direction = extension_direction
        
        write_log("Extension direction parameter: {0} (0=Bottom, 1=Right, 2=Alternate)".format(extension_direction))
        
        # Variable pour stocker le fichier de preference (utilisee plus tard pour la sauvegarde)
        alternate_pref_file = None
        
        # Si le mode est Alternate, lire la derniere direction et utiliser l'inverse
        if extension_direction == 2:  # Alternate
            write_log("====== ALTERNATE MODE DETECTED ======")
            
            # Lire la derniere direction depuis le fichier de preferences
            board_dir = os.path.dirname(dit_path)
            alternate_pref_file = os.path.join(board_dir, "extension_direction.txt")
            
            write_log("Preference file path: {0}".format(alternate_pref_file))
            write_log("Preference file exists: {0}".format(os.path.exists(alternate_pref_file)))
            
            last_direction = None
            if os.path.exists(alternate_pref_file):
                try:
                    with open(alternate_pref_file, 'r') as f:
                        last_direction = f.read().strip()
                    write_log("Read last extension direction from file: '{0}'".format(last_direction))
                except Exception as e:
                    write_log("ERROR reading last direction: {0}".format(e))
            else:
                write_log("No preference file found - this is the FIRST extension")
            
            # Alterner la direction selon la logique Photoshop
            # Si la derniere fois c'etait Right, cette fois c'est Bottom
            # Si la derniere fois c'etait Bottom (ou pas de fichier), cette fois c'est Right
            if last_direction == "Right":
                effective_direction = 0  # Bottom
                current_direction_name = "Bottom"
                write_log("Last was RIGHT -> Using BOTTOM this time")
            else:
                # Si last_direction est None, "Bottom", ou autre
                effective_direction = 1  # Right
                current_direction_name = "Right"
                if last_direction is None:
                    write_log("First extension -> Using RIGHT this time")
                else:
                    write_log("Last was BOTTOM -> Using RIGHT this time")
            
            write_log("====== EFFECTIVE DIRECTION: {0} ======".format(current_direction_name))
        else:
            write_log("Using fixed direction: {0}".format(["Bottom", "Right"][extension_direction]))
        
        # Trouver les limites actuelles du layout en analysant les cellules existantes
        # IMPORTANT: maxX et maxY doivent correspondre au bottomRight de la derniere cellule
        max_x = 0.0
        max_y = 0.0
        cell_width = 0.0
        cell_height = 0.0
        
        for cell in cells:
            # bottomRight donne le coin inferieur droit de chaque cellule
            bottom_right_x = cell['bottomRight'][0]
            bottom_right_y = cell['bottomRight'][1]
            
            # Mettre a jour les limites maximales
            if bottom_right_x > max_x:
                max_x = bottom_right_x
            if bottom_right_y > max_y:
                max_y = bottom_right_y
            
            # Calculer la largeur et hauteur de la cellule
            width = cell['bottomRight'][0] - cell['topLeft'][0]
            height = cell['bottomLeft'][1] - cell['topLeft'][1]
            
            if width > 0:
                cell_width = width
            if height > 0:
                cell_height = height
        
        write_log("Layout limits - maxX: {0}, maxY: {1}".format(max_x, max_y))
        write_log("Cell dimensions - width: {0}, height: {1}".format(cell_width, cell_height))
        
        new_cells = []
        
        # Recuperer les dimensions originales du canvas
        old_width = pdb.gimp_image_width(img)
        old_height = pdb.gimp_image_height(img)
        
        write_log("Original canvas size: {0}x{1}".format(old_width, old_height))
        
        if effective_direction == 1:  # Right - Ajouter une colonne a droite
            write_log("Extending RIGHT - Adding new column")
            
            # Calculer la nouvelle position X
            new_col_x = max_x + layout_spacing
            
            # Trouver toutes les positions Y uniques des cellules existantes
            row_positions = []
            for cell in cells:
                cell_min_y = cell['minY']
                if cell_min_y not in row_positions:
                    row_positions.append(cell_min_y)
            
            # Trier les positions Y pour traiter les lignes de haut en bas
            row_positions.sort()
            
            write_log("Found {0} unique row positions to extend".format(len(row_positions)))
            
            # Creer une cellule pour chaque ligne existante
            for i, row_y in enumerate(row_positions):
                # Calculer row/col pour cette nouvelle cellule
                # row = position dans la liste row_positions (1-based)
                # col = nouvelle colonne = nbr_cols + 1 (avant incrementation)
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
                    'row': cell_row,  # Stocker row pour le calcul du masque
                    'col': cell_col   # Stocker col pour le calcul du masque
                }
                new_cells.append(new_cell)
                write_log("New cell {0}: ({1:.0f},{2:.0f}) -> ({3:.0f},{4:.0f}) [R{5}C{6}]".format(
                    new_cell['index'], new_cell['minX'], new_cell['minY'], 
                    new_cell['maxX'], new_cell['maxY'], cell_row, cell_col))
            
            # IMPORTANT: Calculer la nouvelle taille comme Photoshop le fait
            # Ajouter simplement cellWidth + layoutSpacing a la largeur originale
            # Cela preserve automatiquement les marges a droite
            new_layout_width = int(old_width + cell_width + layout_spacing)
            new_layout_height = old_height  # Hauteur inchangee
            nbr_cols += 1
            
        else:  # Bottom (0) - Ajouter une ligne en bas
            write_log("Extending BOTTOM - Adding new row")
            
            # Calculer la nouvelle position Y
            new_row_y = max_y + layout_spacing
            
            # Trouver toutes les positions X uniques des cellules existantes
            col_positions = []
            for cell in cells:
                cell_min_x = cell['minX']
                if cell_min_x not in col_positions:
                    col_positions.append(cell_min_x)
            
            # Trier les positions X pour traiter les colonnes de gauche a droite
            col_positions.sort()
            
            write_log("Found {0} unique column positions to extend".format(len(col_positions)))
            
            # Creer une cellule pour chaque colonne existante
            for i, col_x in enumerate(col_positions):
                # Calculer row/col pour cette nouvelle cellule
                # row = nouvelle ligne = nbr_rows + 1 (avant incrementation)
                # col = position dans la liste col_positions (1-based)
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
                    'row': cell_row,  # Stocker row pour le calcul du masque
                    'col': cell_col   # Stocker col pour le calcul du masque
                }
                new_cells.append(new_cell)
                write_log("New cell {0}: ({1:.0f},{2:.0f}) -> ({3:.0f},{4:.0f}) [R{5}C{6}]".format(
                    new_cell['index'], new_cell['minX'], new_cell['minY'], 
                    new_cell['maxX'], new_cell['maxY'], cell_row, cell_col))
            
            # IMPORTANT: Calculer la nouvelle taille comme Photoshop le fait
            # Ajouter simplement cellHeight + layoutSpacing a la hauteur originale
            # Cela preserve automatiquement les marges en bas
            new_layout_width = old_width  # Largeur inchangee
            new_layout_height = int(old_height + cell_height + layout_spacing)
            nbr_rows += 1
        
        write_log("New layout dimensions: {0}x{1}".format(new_layout_width, new_layout_height))
        write_log("New grid: {0}x{1} cells".format(nbr_cols, nbr_rows))
        
        # Etendre le canvas GIMP
        # old_width et old_height sont deja definis au debut de la fonction
        new_width = int(round(new_layout_width))
        new_height = int(round(new_layout_height))
        
        write_log("Resizing canvas from {0}x{1} to {2}x{3}".format(
            old_width, old_height, new_width, new_height))
        
        # Redimensionner le canvas
        pdb.gimp_image_resize(img, new_width, new_height, 0, 0)
        
        # NOTE: Ne PAS redimensionner les calques d'images dans "Board Content"
        # Ils doivent garder leur taille d'origine pour que la detection d'occupation fonctionne
        # On redimensionne SEULEMENT les calques de structure (Mask, Borders, Background, etc.)
        write_log("Note: Image layers in Board Content will NOT be resized (by design)")
        
        # Trouver les calques existants a mettre a jour
        write_log("Finding existing layers to update...")
        board_elements_group = None
        mask_layer = None
        borders_layer = None
        gutters_layer = None
        simple_page_group = None
        background_layer = None
        structure_layers_to_resize = []  # Liste des calques de structure a redimensionner
        
        # Trouver le groupe Board Elements et ses sous-calques + Background
        for layer in img.layers:
            layer_name = pdb.gimp_item_get_name(layer)
            
            # Chercher le calque Background
            if layer_name == "Background":
                background_layer = layer
                structure_layers_to_resize.append(layer)
                write_log("Found Background layer")
            
            # Chercher le groupe Board Elements
            if pdb.gimp_item_is_group(layer):
                if layer_name == "Board Elements":
                    board_elements_group = layer
                    write_log("Found Board Elements group")
                    
                    # Chercher les sous-calques
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
                            # Ajouter tous les masques individuels
                            for mask_child in child.children:
                                if not pdb.gimp_item_is_group(mask_child):
                                    structure_layers_to_resize.append(mask_child)
        
        # Redimensionner UNIQUEMENT les calques de structure
        write_log("Resizing {0} structure layers to match new canvas...".format(len(structure_layers_to_resize)))
        for layer in structure_layers_to_resize:
            try:
                layer_name = pdb.gimp_item_get_name(layer)
                old_layer_width = pdb.gimp_drawable_width(layer)
                old_layer_height = pdb.gimp_drawable_height(layer)
                
                if old_layer_width != new_width or old_layer_height != new_height:
                    pdb.gimp_layer_resize(layer, new_width, new_height, 0, 0)
                    write_log("Resized structure layer '{0}' from {1}x{2} to {3}x{4}".format(
                        layer_name, old_layer_width, old_layer_height, new_width, new_height))
            except Exception as e:
                write_log("WARNING: Could not resize structure layer: {0}".format(e))
        
        write_log("Structure layers resized successfully")
        
        # Recuperer la marge depuis les metadonnees
        margin_size = 0
        if metadata and 'adjustedMargin' in metadata:
            margin_size = float(metadata['adjustedMargin'])
            write_log("Using margin from metadata: {0}px".format(margin_size))
        
        # REMPLIR LES NOUVELLES ZONES du canvas avec les couleurs appropriees
        # Comme Photoshop le fait apres l'extension
        write_log("Filling newly created canvas areas with appropriate colors...")
        
        if effective_direction == 1:  # Right - Zone verticale a droite
            new_area_x = old_width
            new_area_y = 0
            new_area_width = new_width - old_width
            new_area_height = old_height
        else:  # Bottom (0) - Zone horizontale en bas
            new_area_x = 0
            new_area_y = old_height
            new_area_width = old_width
            new_area_height = new_height - old_height
        
        write_log("New area to fill: ({0},{1}) size {2}x{3}".format(
            new_area_x, new_area_y, new_area_width, new_area_height))
        
        # Remplir le calque Mask avec la couleur noire (layout color)
        if mask_layer and new_area_width > 0 and new_area_height > 0:
            try:
                write_log("Filling new area in Mask layer")
                pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                               int(new_area_x), int(new_area_y),
                                               int(new_area_width), int(new_area_height))
                pdb.gimp_context_set_foreground((0, 0, 0))  # Noir
                pdb.gimp_edit_fill(mask_layer, FILL_FOREGROUND)
                pdb.gimp_selection_none(img)
                write_log("Mask layer filled in new area")
            except Exception as e:
                write_log("WARNING: Could not fill Mask layer new area: {0}".format(e))
        
        # Remplir le calque Borders avec la couleur grise (border color)
        if borders_layer and new_area_width > 0 and new_area_height > 0:
            try:
                write_log("Filling new area in Borders layer")
                pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                               int(new_area_x), int(new_area_y),
                                               int(new_area_width), int(new_area_height))
                pdb.gimp_context_set_foreground((200, 200, 200))  # Gris clair
                pdb.gimp_edit_fill(borders_layer, FILL_FOREGROUND)
                pdb.gimp_selection_none(img)
                write_log("Borders layer filled in new area")
            except Exception as e:
                write_log("WARNING: Could not fill Borders layer new area: {0}".format(e))
        
        # Remplir le calque Background avec la couleur blanche
        if background_layer and new_area_width > 0 and new_area_height > 0:
            try:
                write_log("Filling new area in Background layer")
                pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                               int(new_area_x), int(new_area_y),
                                               int(new_area_width), int(new_area_height))
                pdb.gimp_context_set_foreground((255, 255, 255))  # Blanc
                pdb.gimp_edit_fill(background_layer, FILL_FOREGROUND)
                pdb.gimp_selection_none(img)
                write_log("Background layer filled in new area")
            except Exception as e:
                write_log("WARNING: Could not fill Background layer new area: {0}".format(e))
        
        # MISE A JOUR DES CALQUES POUR CHAQUE NOUVELLE CELLULE
        for new_cell in new_cells:
            cell_lx = int(new_cell['minX'])
            cell_rx = int(new_cell['maxX'])
            cell_ty = int(new_cell['minY'])
            cell_by = int(new_cell['maxY'])
            cell_width = cell_rx - cell_lx
            cell_height = cell_by - cell_ty
            
            write_log("Updating layers for new cell {0}: ({1},{2}) -> ({3},{4})".format(
                new_cell['index'], cell_lx, cell_ty, cell_rx, cell_by))
            
            # 1. Mise a jour du calque Mask - Creer un "trou" pour la cellule
            if mask_layer:
                try:
                    write_log("Creating hole in Mask layer")
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE, 
                                                   cell_lx, cell_ty, cell_width, cell_height)
                    pdb.gimp_edit_clear(mask_layer)
                    pdb.gimp_selection_none(img)
                    write_log("Hole created in Mask layer")
                except Exception as e:
                    write_log("WARNING: Could not update Mask layer: {0}".format(e))
            
            # 2. Mise a jour du calque Borders - Creer un "trou" avec marges
            if borders_layer and margin_size > 0:
                try:
                    write_log("Creating hole in Borders layer with margin: {0}px".format(margin_size))
                    inner_x = cell_lx + int(margin_size)
                    inner_y = cell_ty + int(margin_size)
                    inner_width = cell_width - int(2 * margin_size)
                    inner_height = cell_height - int(2 * margin_size)
                    
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                                   inner_x, inner_y, inner_width, inner_height)
                    pdb.gimp_edit_clear(borders_layer)
                    pdb.gimp_selection_none(img)
                    write_log("Hole created in Borders layer")
                except Exception as e:
                    write_log("WARNING: Could not update Borders layer: {0}".format(e))
            
            # 3. Creation du masque Simple page Mask pour la nouvelle cellule (mode spread uniquement)
            if cell_type.lower() == "spread" and simple_page_group:
                try:
                    # Utiliser row/col stockes dans new_cell (calcules lors de la creation)
                    # Ces valeurs sont correctes quelle que soit la direction d'extension
                    row = new_cell.get('row', None)
                    col = new_cell.get('col', None)
                    
                    # Fallback: si row/col ne sont pas dans new_cell, calculer a partir de l'index
                    # (pour compatibilite avec d'anciennes versions ou cas non geres)
                    if row is None or col is None:
                        cell_index = new_cell['index']
                        row = ((cell_index - 1) // nbr_cols) + 1
                        col = ((cell_index - 1) % nbr_cols) + 1
                        write_log("WARNING: Using fallback row/col calculation for cell {0}".format(cell_index))
                    
                    mask_name = "R{0}C{1}".format(row, col)
                    write_log("Creating Simple page mask layer: {0} (row={1}, col={2})".format(mask_name, row, col))
                    
                    # Creer le calque de masque
                    mask_layer_spm = gimp.Layer(img, mask_name, new_width, new_height,
                                          RGBA_IMAGE, 100, NORMAL_MODE)
                    img.add_layer(mask_layer_spm, 0)
                    pdb.gimp_image_reorder_item(img, mask_layer_spm, simple_page_group, 0)
                    
                    # Remplir le masque avec un rectangle au centre de la cellule
                    middle_x = cell_lx + (cell_width / 2)
                    rect_x = int(middle_x - margin_size)
                    rect_y = cell_ty
                    rect_width = int(2 * margin_size)
                    rect_height = cell_height
                    
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                                   rect_x, rect_y, rect_width, rect_height)
                    # Utiliser la couleur des borders (meme couleur que dans le board d'origine)
                    pdb.gimp_context_set_foreground(border_color)
                    pdb.gimp_edit_fill(mask_layer_spm, FILL_FOREGROUND)
                    pdb.gimp_selection_none(img)
                    
                    # Rendre invisible par defaut
                    pdb.gimp_item_set_visible(mask_layer_spm, False)
                    
                    write_log("Simple page mask {0} created and filled".format(mask_name))
                except Exception as e:
                    write_log("WARNING: Could not create Simple page mask: {0}".format(e))
            
            # 4. Creation de la gouttiere pour la nouvelle cellule (mode spread uniquement)
            if cell_type.lower() == "spread" and gutters_layer:
                try:
                    write_log("Creating gutter for new cell")
                    middle_x = cell_lx + (cell_width / 2)
                    gutter_width = max(2, int(round(cell_width / 500.0)))  # Au moins 2 pixels
                    gutter_height = int(cell_height * 0.9)
                    gutter_y_offset = int((cell_height - gutter_height) / 2)
                    
                    gutter_x = int(middle_x - gutter_width / 2)
                    gutter_y = cell_ty + gutter_y_offset
                    
                    write_log("Gutter dimensions: {0}x{1} at ({2},{3})".format(
                        gutter_width, gutter_height, gutter_x, gutter_y))
                    
                    pdb.gimp_image_select_rectangle(img, CHANNEL_OP_REPLACE,
                                                   gutter_x, gutter_y, gutter_width, gutter_height)
                    pdb.gimp_context_set_foreground((34, 34, 34))  # Couleur 222222
                    pdb.gimp_edit_fill(gutters_layer, FILL_FOREGROUND)
                    pdb.gimp_selection_none(img)
                    
                    write_log("Gutter created successfully")
                except Exception as e:
                    write_log("WARNING: Could not create gutter: {0}".format(e))
        
        # 5. Creation des overlays pour les nouvelles cellules (si activé)
        if overlay_files and len(overlay_files) > 0:
            write_log("Creating overlays for {0} new cells".format(len(new_cells)))
            
            # Trouver ou créer le groupe Overlay (comme dans createGimpBoard.py)
            overlay_group = None
            board_elements_group = None
            
            try:
                # Trouver le groupe Board Elements
                for layer in img.layers:
                    if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Elements":
                        board_elements_group = layer
                        # Chercher le groupe Overlay existant
                        for child in layer.children:
                            if pdb.gimp_item_is_group(child) and pdb.gimp_item_get_name(child) == "Overlay":
                                overlay_group = child
                                write_log("Found existing Overlay group")
                                break
                        break
                
                # Si le groupe Overlay n'existe pas, le créer
                if board_elements_group and not overlay_group:
                    overlay_group = pdb.gimp_layer_group_new(img)
                    pdb.gimp_item_set_name(overlay_group, "Overlay")
                    pdb.gimp_image_insert_layer(img, overlay_group, board_elements_group, 0)
                    write_log("Overlay group created")
                
                # Placer les overlays pour chaque nouvelle cellule (logique exacte de createGimpBoard.py)
                if overlay_group:
                    margin_size = 0
                    if metadata and 'adjustedMargin' in metadata:
                        margin_size = float(metadata['adjustedMargin'])
                    
                    for new_cell in new_cells:
                        try:
                            cell_lx = int(new_cell['minX'])
                            cell_ty = int(new_cell['minY'])
                            cell_width = int(new_cell['maxX'] - new_cell['minX'])
                            cell_height = int(new_cell['maxY'] - new_cell['minY'])
                            
                            row = new_cell.get('row', 1)
                            col = new_cell.get('col', 1)
                            
                            write_log("Placing overlay for cell R{0}C{1}".format(row, col))
                            
                            # Calculer l'index de l'overlay (même logique que createGimpBoard.py)
                            overlay_index = get_overlay_index_for_cell(row, col, nbr_cols, len(overlay_files), cell_type)
                            if overlay_index >= len(overlay_files):
                                overlay_index = overlay_index % len(overlay_files)
                            
                            overlay_path = overlay_files[overlay_index]
                            write_log("Using overlay file: {0} (index {1})".format(overlay_path, overlay_index))
                            
                            # Déterminer l'orientation de l'overlay
                            orientation = get_image_orientation(overlay_path)
                            write_log("Overlay orientation: {0}".format(orientation))
                            
                            # Calculer les dimensions et positions
                            position_info = calculate_overlay_dimensions(
                                cell_width, cell_height, cell_type, orientation, margin_size
                            )
                            
                            # Placer l'overlay selon le type (exactement comme dans createGimpBoard.py)
                            if position_info['position'] == 'center':
                                # Placement centre (Single ou Landscape en Spread)
                                place_overlay_in_cell(
                                    img, overlay_path, cell_lx, cell_ty, cell_width, cell_height,
                                    cell_type, overlay_group, position_info
                                )
                            elif position_info['position'] == 'split':
                                # Placement séparé (Portrait en Spread)
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
                                        int(cell_lx + position_info['dimensions']['right']['x']), cell_ty,
                                        int(position_info['dimensions']['right']['width']),
                                        int(position_info['dimensions']['right']['height']),
                                        cell_type, overlay_group, right_info
                                    )
                            
                            write_log("Overlay placed successfully for cell R{0}C{1}".format(row, col))
                            
                        except Exception as e:
                            write_log("ERROR placing overlay for cell R{0}C{1}: {2}".format(row, col, e))
                else:
                    write_log("WARNING: Could not find or create Overlay group")
                    
            except Exception as e:
                write_log("ERROR creating overlays: {0}".format(e))
                import traceback
                write_log("Traceback: {0}".format(traceback.format_exc()))
        
        # REPOSITIONNER LA LEGENDE (comme dans le script Photoshop)
        try:
            write_log("Searching for Legend layer to reposition...")
            legend_layer = None
            
            # Chercher le calque Legend dans le groupe Board Elements
            for layer in img.layers:
                if pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Board Elements":
                    for child in layer.children:
                        if pdb.gimp_item_get_name(child) == "Legend":
                            legend_layer = child
                            write_log("Found Legend layer in Board Elements group")
                            break
                    break
            
            # Si Legend n'est pas dans Board Elements, chercher au niveau racine
            if not legend_layer:
                for layer in img.layers:
                    if not pdb.gimp_item_is_group(layer) and pdb.gimp_item_get_name(layer) == "Legend":
                        legend_layer = layer
                        write_log("Found Legend layer at root level")
                        break
            
            if legend_layer:
                # Obtenir la position actuelle de la legende
                current_x, current_y = pdb.gimp_drawable_offsets(legend_layer)
                write_log("Legend current position: ({0}, {1})".format(current_x, current_y))
                
                # Calculer le deplacement selon la direction d'extension (logique identique a Photoshop)
                if effective_direction == 1:  # Right
                    # Extension vers la droite: deplacer de la largeur d'une cellule + espacement
                    horizontal_offset = cell_width + layout_spacing
                    new_x = int(current_x + horizontal_offset)
                    new_y = current_y
                    write_log("Moving legend RIGHT by {0}px (cell_width + layout_spacing)".format(horizontal_offset))
                else:  # Bottom (0)
                    # Extension vers le bas: deplacer de la hauteur d'une cellule + espacement
                    vertical_offset = cell_height + layout_spacing
                    new_x = current_x
                    new_y = int(current_y + vertical_offset)
                    write_log("Moving legend DOWN by {0}px (cell_height + layout_spacing)".format(vertical_offset))
                
                # Appliquer le deplacement
                pdb.gimp_layer_set_offsets(legend_layer, new_x, new_y)
                write_log("Legend repositioned to: ({0}, {1})".format(new_x, new_y))
            else:
                write_log("Legend layer not found, skipping repositioning")
                
        except Exception as e:
            write_log("WARNING: Could not reposition Legend layer: {0}".format(e))
            import traceback
            write_log("Traceback: {0}".format(traceback.format_exc()))
        
        # Mettre a jour le fichier .board avec les nouvelles cellules
        write_log("Updating .board file with new cells")
        
        try:
            # Lire le fichier .board actuel
            with open(dit_path, 'r') as f:
                lines = f.readlines()
            
            # Separer les metadonnees et les cellules
            metadata_lines = []
            cell_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Les metadonnees commencent par #
                if line.startswith('#'):
                    metadata_lines.append(line)
                # Les cellules sont des lignes avec des chiffres
                elif line[0].isdigit():
                    cell_lines.append(line)
            
            write_log("Found {0} metadata lines and {1} cell lines".format(
                len(metadata_lines), len(cell_lines)))
            
            # Mettre a jour les metadonnees
            new_metadata = []
            for line in metadata_lines:
                if line.startswith('#nbrCols='):
                    new_metadata.append('#nbrCols={0}'.format(nbr_cols))
                    write_log("Updated nbrCols: {0}".format(nbr_cols))
                elif line.startswith('#nbrRows='):
                    new_metadata.append('#nbrRows={0}'.format(nbr_rows))
                    write_log("Updated nbrRows: {0}".format(nbr_rows))
                elif line.startswith('#layoutWidth='):
                    new_metadata.append('#layoutWidth={0}'.format(int(new_layout_width)))
                    write_log("Updated layoutWidth: {0}".format(int(new_layout_width)))
                elif line.startswith('#layoutHeight='):
                    new_metadata.append('#layoutHeight={0}'.format(int(new_layout_height)))
                    write_log("Updated layoutHeight: {0}".format(int(new_layout_height)))
                else:
                    new_metadata.append(line)
            
            # Ajouter les nouvelles cellules au format correct
            # Format: index,topLeftX,topLeftY,bottomLeftX,bottomLeftY,bottomRightX,bottomRightY,topRightX,topRightY
            for new_cell in new_cells:
                cell_line = "{0},{1},{2},{3},{4},{5},{6},{7},{8}".format(
                    new_cell['index'],
                    int(new_cell['minX']), int(new_cell['minY']),  # topLeft
                    int(new_cell['minX']), int(new_cell['maxY']),  # bottomLeft
                    int(new_cell['maxX']), int(new_cell['maxY']),  # bottomRight
                    int(new_cell['maxX']), int(new_cell['minY'])   # topRight
                )
                cell_lines.append(cell_line)
                write_log("Added cell line: {0}".format(cell_line))
            
            # Reecrire le fichier .board
            with open(dit_path, 'w') as f:
                for line in new_metadata:
                    f.write(line + '\n')
                for line in cell_lines:
                    f.write(line + '\n')
            
            write_log("Successfully updated .board file with {0} new cells".format(len(new_cells)))
            
        except Exception as e:
            write_log("ERROR updating .board file: {0}".format(e))
            return False
        
        # Forcer GIMP a mettre a jour l'affichage et l'etat interne
        pdb.gimp_displays_flush()
        
        # SAUVEGARDER LA DIRECTION UTILISEE pour le mode Alternate (apres succes de l'extension)
        if alternate_pref_file is not None:
            try:
                # Sauvegarder la direction qu'on vient d'utiliser
                direction_to_save = ["Bottom", "Right"][effective_direction]
                with open(alternate_pref_file, 'w') as f:
                    f.write(direction_to_save)
                write_log("====== SAVED extension direction '{0}' to {1} ======".format(
                    direction_to_save, alternate_pref_file))
            except Exception as e:
                write_log("WARNING: Could not save extension direction: {0}".format(e))
                import traceback
                write_log("Traceback: {0}".format(traceback.format_exc()))
        
        write_log("====== Board extension completed successfully ======")
        return True
        
    except Exception as e:
        write_log("ERROR in extend_board: {0}".format(e))
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()))
        return False

def import_images_to_board(img, image_files, cell_type, resize_mode, start_cell, auto_extend=False, extension_direction=0, user_overlay_files=None):
    """Fonction principale pour importer des images dans un board avec support d'extension automatique
    Main function to import images into a board with automatic extension support
    
    Parameters:
    - img: L'image GIMP active (le board) / Active GIMP image (the board)
    - image_files: Liste des chemins d'images a importer / List of image paths to import
    - cell_type: "single" ou "spread" / "single" or "spread"
    - resize_mode: "fit", "cover" ou "noResize" / "fit", "cover" or "noResize"
    - start_cell: Index de la premiere cellule (1-based) / Index of first cell (1-based)
    - auto_extend: Si True, etendre automatiquement le board quand toutes les cellules sont pleines / If True, auto-extend board when all cells are full
    - extension_direction: 0=Bottom, 1=Right, 2=Alternate
    - user_overlay_files: Liste des fichiers overlay fournis par l'utilisateur (optionnel) / List of user-provided overlay files (optional)
    """
    global log_file_path
    
    # Initialiser le log
    board_path = pdb.gimp_image_get_filename(img)
    if board_path:
        board_dir = os.path.dirname(board_path)
        board_name = os.path.splitext(os.path.basename(board_path))[0]
        log_file_path = os.path.join(board_dir, "{0}_import.log".format(board_name))
        write_log("====== GIMP Board Import Started ======")
        write_log("Board: {0}".format(board_path))
    else:
        write_log("====== GIMP Board Import Started ======")
        write_log("WARNING: Board not saved, log will be in memory only")
    
    total_images = len(image_files)
    write_log("Number of images to import: {0}".format(total_images))
    write_log("Cell type: {0}".format(cell_type))
    write_log("Resize mode: {0}".format(resize_mode))
    write_log("Start cell: {0}".format(start_cell))
    write_log("Auto extend: {0}".format(auto_extend))
    write_log("Extension direction: {0}".format(["Bottom", "Right", "Alternate"][extension_direction]))
    
    # Chercher le fichier .board
    dit_path = None
    if board_path:
        board_dir = os.path.dirname(board_path)
        board_name = os.path.splitext(os.path.basename(board_path))[0]
        dit_path = os.path.join(board_dir, "{0}.board".format(board_name))
        
        write_log("Looking for BOARD file: {0}".format(dit_path))
        
        if not os.path.exists(dit_path):
            write_log("ERROR: BOARD file not found: {0}".format(dit_path))
            pdb.gimp_message("BOARD file not found. Please open a valid board XCF file.")
            return
    else:
        write_log("ERROR: Board not saved")
        pdb.gimp_message("Please save the board file first.")
        return
    
    # Lire le fichier .board
    board_data = read_dit_file(dit_path)
    if not board_data:
        write_log("ERROR: Failed to read BOARD file")
        return
    
    cells = board_data['cells']
    metadata = board_data['metadata']
    board_overlay_files = board_data.get('overlay_files', [])
    
    # Décider quels overlays utiliser: priorité aux overlays utilisateur, sinon ceux du board
    if user_overlay_files and len(user_overlay_files) > 0:
        overlay_files = user_overlay_files
        write_log("Using {0} overlay files provided by user".format(len(overlay_files)))
    else:
        overlay_files = board_overlay_files
        if overlay_files:
            write_log("Using {0} overlay files from board configuration".format(len(overlay_files)))
    
    write_log("Board has {0} cells defined initially".format(len(cells)))
    
    # Commencer a placer les images
    undo_started = False
    images_placed = 0
    images_failed = 0
    
    try:
        pdb.gimp_image_undo_group_start(img)
        undo_started = True
        
        for i, image_file in enumerate(image_files):
            write_log("====== Processing image {0}/{1}: {2} ======".format(
                i + 1, total_images, os.path.basename(image_file)))
            
            # Mettre a jour la barre de progression GIMP
            progress = float(i) / float(total_images)
            pdb.gimp_progress_update(progress)
            
            # Determiner l'orientation de l'image
            orientation = get_image_orientation(image_file)
            write_log("Image orientation: {0}".format(orientation))
            
            # Trouver la prochaine cellule vide (analyse toutes les cellules)
            empty_cell, use_side = find_empty_cell(img, cells, cell_type, orientation)
            
            # Si aucune cellule vide et auto-extend active
            if empty_cell is None and auto_extend:
                write_log("No empty cell found, auto-extend is enabled, attempting to extend board...")
                
                # Etendre le board
                extension_success = extend_board(img, dit_path, cells, metadata, 
                                                extension_direction, cell_type, overlay_files)
                
                if extension_success:
                    write_log("Board extended successfully, re-reading .board file")
                    # Relire le fichier .board pour obtenir les nouvelles cellules
                    board_data = read_dit_file(dit_path)
                    if board_data:
                        cells = board_data['cells']
                        metadata = board_data['metadata']
                        # Conserver les overlays utilisateur si fournis, sinon utiliser ceux du board
                        if not (user_overlay_files and len(user_overlay_files) > 0):
                            overlay_files = board_data.get('overlay_files', [])
                        write_log("New cell count: {0}".format(len(cells)))
                        
                        # Reessayer de trouver une cellule vide
                        empty_cell, use_side = find_empty_cell(img, cells, cell_type, orientation)
                    else:
                        write_log("ERROR: Failed to re-read .board file after extension")
                        extension_success = False
                else:
                    write_log("ERROR: Failed to extend board")
                
                if not extension_success or empty_cell is None:
                    write_log("Remaining images: {0}".format(total_images - i))
                    images_failed = total_images - i
                    break
            
            # Si toujours aucune cellule vide
            if empty_cell is None:
                write_log("WARNING: No more empty cells available, stopping import")
                write_log("Remaining images: {0}".format(total_images - i))
                images_failed = total_images - i
                break
            
            write_log("Found empty cell {0}, using side: {1}".format(empty_cell['index'], use_side))
            
            # Placer l'image dans la cellule
            success = place_image_in_cell(img, image_file, empty_cell, cell_type, resize_mode, metadata, cells, use_side)
            
            if success:
                images_placed += 1
                write_log("Image {0}/{1} placed successfully in cell {2}".format(
                    i + 1, total_images, empty_cell['index']))
            else:
                write_log("ERROR: Failed to place image {0}".format(image_file))
                images_failed += 1
        
        # Finaliser la barre de progression
        pdb.gimp_progress_update(1.0)
        
        write_log("====== Import completed ======")
        write_log("Images placed: {0}".format(images_placed))
        write_log("Images failed: {0}".format(images_failed))
        write_log("Total processed: {0}/{1}".format(images_placed + images_failed, total_images))
        
        # Sauvegarde automatique du XCF si l'import a reussi
        if images_placed > 0 and board_path:
            try:
                write_log("Auto-saving XCF file: {0}".format(board_path))
                pdb.gimp_xcf_save(0, img, img.layers[0], board_path, board_path)
                pdb.gimp_image_clean_all(img)
                write_log("XCF file saved successfully")
                pdb.gimp_message("Import completed: {0} image(s) placed and saved.".format(images_placed))
            except Exception as e:
                write_log("ERROR saving XCF file: {0}".format(e))
                pdb.gimp_message("Import completed: {0} image(s) placed but save failed.".format(images_placed))
        elif images_placed > 0:
            pdb.gimp_message("Import completed: {0} image(s) placed.".format(images_placed))
        
    except Exception as e:
        write_log("ERROR during import: {0}".format(e))
        import traceback
        write_log("Traceback: {0}".format(traceback.format_exc()))
    finally:
        # Seulement terminer le groupe undo si on l'a commence
        if undo_started:
            try:
                pdb.gimp_image_undo_group_end(img)
            except Exception as e:
                write_log("WARNING: Error ending undo group: {0}".format(e))
        pdb.gimp_displays_flush()

# Interface utilisateur amelioree
# Improved user interface
def import_board_ui(img, drawable, import_mode, image_folder, image_file, image_pattern, cell_type, 
                   resize_mode, start_cell, overlay_enabled, overlay_file, overlay_folder,
                   auto_extend, extension_direction):
    """Interface utilisateur pour l'import d'images avec support de multiples modes
    User interface for image import with support for multiple modes"""
    
    import glob
    image_files = []
    
    # Convertir les index en valeurs
    import_mode_list = ["Folder (All Images)", "Single Image", "Folder (Pattern)"]
    cell_type_list = ["single", "spread"]
    resize_mode_list = ["fit", "cover", "noResize"]
    extension_dir_list = ["Bottom", "Right", "Alternate"]
    
    mode_name = import_mode_list[import_mode] if isinstance(import_mode, int) else import_mode
    cell_type_str = cell_type_list[cell_type] if isinstance(cell_type, int) else cell_type
    resize_mode_str = resize_mode_list[resize_mode] if isinstance(resize_mode, int) else resize_mode
    ext_dir_name = extension_dir_list[extension_direction] if isinstance(extension_direction, int) else extension_direction
    
    write_log("====== OPEN BOARD IMPORT STARTED ======")
    write_log("Import mode: {0}".format(mode_name))
    write_log("Cell type: {0}".format(cell_type_str))
    write_log("Resize mode: {0}".format(resize_mode_str))
    write_log("Start cell: {0}".format(start_cell))
    write_log("Overlay enabled: {0}".format(overlay_enabled))
    write_log("Auto extend: {0}".format(auto_extend))
    write_log("Extension direction: {0}".format(ext_dir_name))
    
    # Traiter selon le mode d'import
    if mode_name == "Folder (All Images)":
        # Mode 1: Importer toutes les images d'un dossier
        write_log("Mode: Folder - Scanning all images")
        
        if not image_folder or not os.path.isdir(image_folder):
            pdb.gimp_message("Please select a valid folder")
            write_log("ERROR: Invalid folder path")
            return
        
        write_log("Scanning directory: {0}".format(image_folder))
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff', '*.psd', '*.bmp',
                     '*.JPG', '*.JPEG', '*.PNG', '*.TIF', '*.TIFF', '*.PSD', '*.BMP']
        
        for ext in extensions:
            pattern = os.path.join(image_folder, ext)
            found_files = glob.glob(pattern)
            if found_files:
                image_files.extend(found_files)
                write_log("Found {0} files with extension {1}".format(len(found_files), ext))
    
    elif mode_name == "Single Image":
        # Mode 2: Importer une seule image
        write_log("Mode: Single Image")
        
        if not image_file or not os.path.isfile(image_file):
            pdb.gimp_message("Please select a valid image file")
            write_log("ERROR: Invalid image file")
            return
        
        image_files = [image_file]
        write_log("Single image: {0}".format(image_file))
    
    elif mode_name == "Folder (Pattern)":
        # Mode 3: Importer selon un pattern (ex: *.jpg, IMG_*.png, etc.)
        write_log("Mode: Folder with pattern")
        
        if not image_folder or not os.path.isdir(image_folder):
            pdb.gimp_message("Please select a valid folder")
            write_log("ERROR: Invalid folder path")
            return
        
        if not image_pattern or image_pattern.strip() == "":
            image_pattern = "*.jpg"  # Pattern par defaut
            write_log("Using default pattern: *.jpg")
        
        write_log("Pattern: {0}".format(image_pattern))
        pattern_path = os.path.join(image_folder, image_pattern)
        image_files = glob.glob(pattern_path)
        write_log("Found {0} files matching pattern".format(len(image_files)))
    
    write_log("Total image files to import: {0}".format(len(image_files)))
    
    if not image_files:
        pdb.gimp_message("No images found with current settings")
        write_log("ERROR: No images found")
        return
    
    # Trier les fichiers par nom pour un import ordonne
    image_files.sort()
    write_log("Sorted image files: {0}".format([os.path.basename(f) for f in image_files[:5]]))
    if len(image_files) > 5:
        write_log("... and {0} more files".format(len(image_files) - 5))
    
    # Traiter les overlays si activés
    user_overlay_files = []
    if overlay_enabled:
        write_log("Overlay enabled by user")
        
        # Trouver les fichiers overlay depuis les parametres utilisateur
        if overlay_file and os.path.exists(overlay_file):
            user_overlay_files = find_overlay_files(overlay_file)
            write_log("Found {0} overlay file(s) from file parameter".format(len(user_overlay_files)))
        elif overlay_folder and os.path.exists(overlay_folder):
            user_overlay_files = find_overlay_files(overlay_folder)
            write_log("Found {0} overlay file(s) from folder parameter".format(len(user_overlay_files)))
        
        if user_overlay_files:
            write_log("User overlay files will be used for new cells during extension")
        else:
            write_log("WARNING: Overlay enabled but no overlay files found")
    
    # Initialiser la barre de progression GIMP
    pdb.gimp_progress_init("Importing {0} image(s) to board...".format(len(image_files)), None)
    
    # Appeler la fonction d'import
    # Note: user_overlay_files seront utilisés uniquement lors de l'extension
    # Les overlays existants du board seront lus depuis le fichier .board
    import_images_to_board(img, image_files, cell_type_str, resize_mode_str, start_cell, 
                          auto_extend, extension_direction, user_overlay_files)

# Enregistrement du plugin
# Plugin registration
register(
    "python_fu_board_import",
    "Open Board - Import images into an existing board layout",
    "Import images into cells of a board created with Open Board. Supports single image, batch folder import, and pattern-based import. Features automatic board extension and flexible placement options.",
    "Yan Senez",
    "Yan Senez",
    "2025",
    "<Image>/File/Open Board/Import Images...",
    "RGB*, GRAY*",
    [
        # ┌─────────────────────────────────────────────────────────────┐
        # │  📥 IMPORT MODE                                             │
        # └─────────────────────────────────────────────────────────────┘
        (PF_OPTION, "import_mode", "─────────── 📥 IMPORT MODE ───────────\nImport Type", 0, 
         ["Folder (All Images)", "Single Image", "Folder (Pattern)"]),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  📁 IMAGE SOURCE                                            │
        # └─────────────────────────────────────────────────────────────┘
        (PF_DIRNAME, "image_folder", "─────────── 📁 SOURCE ───────────\nFolder (for Folder modes)", ""),
        (PF_FILE, "image_file", "Image File (for Single Image mode)", ""),
        (PF_STRING, "image_pattern", "Pattern (for Pattern mode)\nExamples: *.jpg, IMG_*.png", "*.jpg"),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  🔲 PLACEMENT SETTINGS                                      │
        # └─────────────────────────────────────────────────────────────┘
        (PF_OPTION, "cell_type", "─────────── 🔲 PLACEMENT ───────────\nCell Type", 1, ["single", "spread"]),
        (PF_OPTION, "resize_mode", "Resize Mode", 1, ["fit", "cover", "noResize"]),
        (PF_INT, "start_cell", "Start at Cell Number", 1),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  🎭 OVERLAY MASK                                            │
        # └─────────────────────────────────────────────────────────────┘
        (PF_TOGGLE, "overlay_enabled", "─────────── 🎭 OVERLAY ───────────\nEnable Overlay for new cells", False),
        (PF_FILE, "overlay_file", "Overlay File (single file)", ""),
        (PF_DIRNAME, "overlay_folder", "Overlay Folder (all files)", ""),
        
        # ┌─────────────────────────────────────────────────────────────┐
        # │  ⚙️  AUTO-EXTENSION                                         │
        # └─────────────────────────────────────────────────────────────┘
        (PF_TOGGLE, "auto_extend", "─────────── ⚙️  EXTENSION ───────────\nAuto-extend board when full", False),
        (PF_OPTION, "extension_direction", "Extension Direction", 2, ["Bottom", "Right", "Alternate"])
    ],
    [],
    import_board_ui
)

main()

