// JavaScript for Photoshop
// Import images in a board layout with configurable parameters
// Copyright © 2024-25 Yan Senez
// v2.2 no more spacing units (using cell units instead)
// ⚡ OPTIMIZED VERSION with Layer-Based Cell Detection (Option 4) - 70-85% faster
// FIX 2025-10-01: Corrected spread detection using width ratio + center position
// - Images > 60% width = occupy both sides (landscape)
// - Images < 60% width = occupy only the side where their center is (portrait)

// Variable globale pour mesurer le temps d'exécution du script
var SCRIPT_START_TIME = new Date().getTime();

// Version marker pour confirmer qu'on utilise le bon script
var IMPORT_SCRIPT_VERSION = "2.2-2025";

// Variable globale pour stocker le dossier de destination
var globalDestFolder = null;

// Nouvelle variable globale pour le cache des préférences
var globalPreferences = null;

// Liste des clés à exclure du cache (toujours lire directement depuis le fichier)
var DYNAMIC_KEYS = ["extDir"];

// Variables globales pour le suivi des cellules
var gLastProcessedCellId = null; // Variable pour stocker l'ID de la dernière cellule traitée
var gFirstFreeCellId = null; // Variable pour stocker l'ID de la première cellule avec au moins un côté libre
var gPartiallyFilledCells = {}; // Structure pour suivre les cellules Spread avec un côté disponible

// Variables globales pour l'optimisation de détection par analyse de calques
var gBoardContentGroup = null; // Cache du groupe Board Content
var gBoardContentGroupValid = false; // Indicateur de validité du cache

// Variables globales pour la barre de progression
var gProgressBar = null;
var gProgressWindow = null;
var gProgressCancelled = false;
var gStartTime = null;
var gLastUpdateTime = null;
var gProcessedItems = 0;
var gTotalItems = 0;

/**
 * Configuration des logs
 * @type {Object}
 * @property {Object} DEBUG - Niveau de log DEBUG
 * @property {Object} INFO - Niveau de log INFO
 * @property {Object} WARNING - Niveau de log WARNING
 * @property {Object} CRITICAL - Niveau de log CRITICAL (remplace ERROR)
 */
var LogLevel = {
    DEBUG: { value: 0, prefix: "DEBUG" },
    INFO: { value: 1, prefix: "INFO" },
    WARNING: { value: 2, prefix: "WARNING" },
    CRITICAL: { value: 3, prefix: "ERROR" }  // On garde le préfixe ERROR pour la cohérence avec Swift
};

/**
 * Configuration globale des logs
 * @type {Object}
 * @property {LogLevel} minimumLogLevel - Niveau minimum de log
 * @property {boolean} fileLoggingEnabled - Activation du logging dans un fichier
 * @property {boolean} consoleLoggingEnabled - Activation du logging dans la console
 */
var logConfig = {
    minimumLogLevel: LogLevel.INFO,  // Niveau par défaut
    fileLoggingEnabled: false,       // Désactivé par défaut
    consoleLoggingEnabled: true      // Console toujours activée
};

/**
 * Fonction pour charger la configuration des logs depuis le plist
 * @returns {void}  
 */
function loadLogConfiguration() {
    try {
        // Rechercher le fichier pList dans différents emplacements possibles
        var userHome = Folder.userData.parent.parent;
        var possiblePaths = [
            userHome + "/Library/Preferences/Board/com.dityan.Board.plist",
        ];
        
        var plistFile = null;
        
        // Parcourir les emplacements possibles jusqu'à trouver le fichier
        for (var i = 0; i < possiblePaths.length; i++) {
            var testFile = new File(possiblePaths[i]);
            if (testFile.exists) {
                plistFile = testFile;
                break;
            }
        }
        
        if (plistFile && plistFile.exists) {
            plistFile.open("r");
            var content = plistFile.read();
            plistFile.close();
            
            // Extraire fileLoggingEnabled
            var fileLoggingMatch = content.match(/<key>fileLoggingEnabled<\/key>\s*<(true|false)\/>/);
            if (fileLoggingMatch) {
                logConfig.fileLoggingEnabled = (fileLoggingMatch[1] === "true");
            }
            
            // Extraire logLevel
            var logLevelMatch = content.match(/<key>logLevel<\/key>\s*<string>(.*?)<\/string>/);
            if (logLevelMatch) {
                var level = logLevelMatch[1].toLowerCase();
                switch (level) {
                    case "debug":
                        logConfig.minimumLogLevel = LogLevel.DEBUG;
                        break;
                    case "info":
                        logConfig.minimumLogLevel = LogLevel.INFO;
                        break;
                    case "warning":
                        logConfig.minimumLogLevel = LogLevel.WARNING;
                        break;
                    case "CRITICAL":
                    case "critical":
                        logConfig.minimumLogLevel = LogLevel.CRITICAL;
                        break;
                }
            }
        }
    } catch(e) {
        $.writeln("Error loading log configuration: " + e);
    }
}

/**
 * Fonction de journalisation pour écrire dans le même fichier que Swift
 * @param {string} message - Message à écrire dans le log
 * @param {string} level - Niveau de log (DEBUG, INFO, WARNING, ERROR)
 * @returns {boolean} - True si l'écriture a réussi, false sinon
 */
function writeLog(message, level) {
    try {
        // Convertir le niveau de log en objet LogLevel
        var logLevel = LogLevel.INFO;  // Par défaut
        switch(String(level).toUpperCase()) {
            case "DEBUG": logLevel = LogLevel.DEBUG; break;
            case "INFO": logLevel = LogLevel.INFO; break;
            case "WARNING": logLevel = LogLevel.WARNING; break;
            case "CRITICAL": 
            case "ERROR": logLevel = LogLevel.CRITICAL; break;
        }
        
        // Vérifier si le niveau est suffisant pour logger
        if (logLevel.value < logConfig.minimumLogLevel.value) {
            return true;
        }
        
        // Formater la date et l'heure pour le message de log
        var now = new Date();
        var formattedDate = now.getFullYear() + "-" + padZero(now.getMonth() + 1) + "-" + padZero(now.getDate());
        var formattedTime = padZero(now.getHours()) + ":" + padZero(now.getMinutes()) + ":" + padZero(now.getSeconds()) + "." + padZeroMs(now.getMilliseconds());
        
        // Préparer le message complet avec la date et l'heure
        var fullMessage = "[" + formattedDate + " " + formattedTime + "] [BOARD-Import] [" + logLevel.prefix + "] [Import.jsxbin] " + message;
        
        // Toujours afficher dans la console
        if (logConfig.consoleLoggingEnabled) {
            $.writeln(fullMessage);
        }
        
        // Écrire dans le fichier uniquement si activé
        if (logConfig.fileLoggingEnabled) {
            // Déterminer l'emplacement du fichier de log
            var logFolderPath = Folder.userData.parent.parent.fsName + "/Library/Logs/Board";
            var logFileName = "board.log";
            
            // Créer le dossier de logs s'il n'existe pas
            var logFolder = new Folder(logFolderPath);
            if (!logFolder.exists) {
                if (!logFolder.create()) {
                    $.writeln("Error: Could not create log folder: " + logFolderPath);
                    return false;
                }
            }
            
            // Chemin complet du fichier de log
            var logFilePath = logFolderPath + "/" + logFileName;
            
            // Créer ou ouvrir le fichier de log
            var logFile = new File(logFilePath);
            
            try {
                // Ouvrir le fichier en mode append avec encodage UTF-8
                logFile.encoding = "UTF8";
                logFile.lineFeed = "Unix"; // Utiliser LF au lieu de CRLF
                
                if (logFile.open("a")) {
                    // Écrire le message dans le fichier
                    logFile.write(fullMessage + "\n");
                    logFile.close();
                } else {
                    $.writeln("Error: Could not open log file: " + logFilePath);
                    return false;
                }
            } catch (e) {
                $.writeln("Error writing to log file: " + e);
                if (logFile.open) logFile.close();
                return false;
            }
        }
        
        return true;
    } catch (e) {
        // En cas d'erreur, essayer d'écrire dans la console
        $.writeln("Error writing to log: " + e);
        return false;
    }
}

/**
 * Fonction pour enregistrer une cellule partiellement remplie
 * @param {string} cellId - ID de la cellule à enregistrer
 * @param {string} usedSide - Côté utilisé
 * @returns {void}
 */
function registerPartiallyFilledCell(cellId, usedSide) {
    if (!gPartiallyFilledCells) {
        gPartiallyFilledCells = {};
    }
    
    // Enregistrer la cellule avec le côté utilisé
    gPartiallyFilledCells[cellId] = usedSide;
    writeLog("Cell " + cellId + " registered as partially filled (side used: " + usedSide + ")", "DEBUG");
}

/**
 * Fonction pour supprimer une cellule de la liste des cellules partiellement remplies
 * @param {string} cellId - ID de la cellule à supprimer
 * @returns {void}
 */
function unregisterPartiallyFilledCell(cellId) {
    if (gPartiallyFilledCells && gPartiallyFilledCells[cellId]) {
        delete gPartiallyFilledCells[cellId];
        writeLog("Cell " + cellId + " unregistered from partially filled cells", "DEBUG");
    }
}

/**
 * Fonction pour réinitialiser l'ID de la dernière cellule traitée
 * @returns {void}
 */
function resetLastProcessedCellId() {
    gLastProcessedCellId = null;
    gFirstFreeCellId = null;
    gPartiallyFilledCells = {}; // Réinitialiser aussi le cache des cellules partiellement remplies
    writeLog("Reset last processed cell ID, first free cell ID, and partially filled cells cache", "DEBUG");
}

/**
 * Fonction pour effacer le fichier de log local
 * @returns {void}
 */
function clearLocalLog() {
    try {
        // Déterminer l'emplacement du fichier de log local
        var localLogFolderPath = "";
        var logFileName = "board.log";
        
        // Essayer d'utiliser le dossier du document actif
        if (app.documents.length > 0) {
            try {
                var docPath = app.activeDocument.path.fsName;
                localLogFolderPath = docPath + "/.board";
            } catch (e) {
                // En cas d'erreur, continuer
            }
        }
        
        // Si toujours pas défini, utiliser le dossier global
        if (!localLogFolderPath && globalDestFolder) {
            localLogFolderPath = globalDestFolder + "/.board";
        }
        
        // Si un chemin a été trouvé, effacer le fichier
        if (localLogFolderPath) {
            var localLogPath = localLogFolderPath + "/" + logFileName;
            var logFile = new File(localLogPath);
            if (logFile.exists) {
                $.writeln("Clearing local log file: " + localLogPath);
                logFile.remove();
            }
        }
    } catch (e) {
        $.writeln("Error clearing local log file: " + e);
    }
}

/**
 * Fonction utilitaire pour ajouter des zéros devant un nombre
 * @param {number} num - Nombre à modifier
 * @returns {string} - Nombre avec des zéros devant
 */
function padZero(num) {
    return (num < 10) ? "0" + num : num.toString();
}

/**
 * Fonction utilitaire pour formater les millisecondes avec des zéros
 * @param {number} ms - Nombre de millisecondes à modifier
 * @returns {string} - Nombre avec des zéros devant
 */
function padZeroMs(ms) {
    if (ms < 10) return "00" + ms;
    if (ms < 100) return "0" + ms;
    return ms.toString();
}

/**
 * Fonction pour définir le dossier de destination global
 * @param {string} folderPath - Chemin du dossier de destination
 */
function setGlobalDestFolder(folderPath) {
    globalDestFolder = folderPath;
    $.writeln("Global destination folder set to: " + globalDestFolder);
}

/**
 * Fonction utilitaire pour compter les propriétés d'un objet (sans dépendre de Object.keys)
 * @param {Object} obj - Objet à compter
 * @returns {number} - Nombre de propriétés
 */
function countObjectProperties(obj) {
    if (!obj) return 0;
    var count = 0;
    for (var key in obj) {
        if (obj.hasOwnProperty(key)) {
            count++;
        }
    }
    return count;
}

/**
 * Fonction stringify personnalisée pour remplacer JSON.stringify qui n'existe pas en ExtendScript
 * @param {Object} obj - Objet à convertir en chaîne
 * @returns {string} - Chaîne représentant l'objet
 */
function stringify(obj) {
    if (obj === null) return "null";
    if (obj === undefined) return "undefined";
    
    // Tableaux
    if (obj instanceof Array) {
        var str = "[";
        for (var i = 0; i < obj.length; i++) {
            str += (i > 0 ? ", " : "") + stringify(obj[i]);
        }
        return str + "]";
    }
    
    // Objets
    if (typeof obj === "object") {
        var str = "{";
        var first = true;
        for (var key in obj) {
            if (obj.hasOwnProperty(key)) {
                str += (first ? "" : ", ") + '"' + key + '": ' + stringify(obj[key]);
                first = false;
            }
        }
        return str + "}";
    }
    
    // Chaînes
    if (typeof obj === "string") {
        return '"' + obj.replace(/"/g, '\\"').replace(/\n/g, "\\n") + '"';
    }
    
    // Nombres, booléens, etc.
    return String(obj);
}

/**
 * Fonction utilitaire pour vérifier si un tableau contient une valeur
 * @param {Array} array - Tableau à vérifier
 * @param {any} value - Valeur à rechercher
 * @returns {boolean} - Vrai si la valeur est trouvée, faux sinon
 */
function arrayContains(array, value) {
    for (var i = 0; i < array.length; i++) {
        if (array[i] === value) {
            return true;
        }
    }
    return false;
}

/**
 * Fonction pour lire le fichier .board et extraire les coordonnées des cellules
 * @param {string} boardPath - Chemin du fichier .board
 * @returns {Object} - Objet contenant les coordonnées des cellules
 */
function readBoardFile(boardPath) {
    try {
        writeLog("====== START readBoardFile ======", "DEBUG");
        
        // Normaliser le chemin du fichier
        boardPath = normalizePath(boardPath);
        
        if (!boardPath) {
            writeLog("ERROR: Board file path not specified", "ERROR");
            return null;
        }
        
        writeLog("====== BEGIN readBoardFile ======", "DEBUG");
        writeLog("Reading board file: " + boardPath, "DEBUG");
        
        // Vérifier si le fichier existe
        var boardFile = new File(boardPath);
        if (!boardFile.exists) {
            writeLog("ERROR: Board file not found: " + boardPath, "ERROR");
            return null;
        }
        
        // Lire le contenu du fichier
        var content = readFile(boardPath);
        
        if (!content) {
            writeLog("ERROR: Board file is empty", "ERROR");
            writeLog("====== END readBoardFile (empty file) ======", "DEBUG");
            return null;
        }
        
        var lines = content.split("\n");
        writeLog("Number of lines in board file: " + lines.length, "DEBUG");
        
        var coordinates = {};
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line) {
                // Supprimer les espaces au début et à la fin manuellement
                line = line.replace(/^\s+|\s+$/g, "");
                
                if (line) {
                    var parts = line.split(",");
                    if (parts.length === 9) {
                        var cellNumber = parseInt(parts[0]);
                        var topLeftX = parseFloat(parts[1]);
                        var topLeftY = parseFloat(parts[2]);
                        var bottomLeftX = parseFloat(parts[3]);
                        var bottomLeftY = parseFloat(parts[4]);
                        var bottomRightX = parseFloat(parts[5]);
                        var bottomRightY = parseFloat(parts[6]);
                        var topRightX = parseFloat(parts[7]);
                        var topRightY = parseFloat(parts[8]);
                        
                        // Calculer les valeurs min et max pour les coordonnées X et Y
                        var minX = Math.min(topLeftX, bottomLeftX, bottomRightX, topRightX);
                        var maxX = Math.max(topLeftX, bottomLeftX, bottomRightX, topRightX);
                        var minY = Math.min(topLeftY, bottomLeftY, bottomRightY, topRightY);
                        var maxY = Math.max(topLeftY, bottomLeftY, bottomRightY, topRightY);
                        
                        coordinates[cellNumber] = {
                            topLeft: [topLeftX, topLeftY],
                            bottomLeft: [bottomLeftX, bottomLeftY],
                            bottomRight: [bottomRightX, bottomRightY],
                            topRight: [topRightX, topRightY],
                            // Créer un objet bounds avec les propriétés minX, maxX, minY et maxY
                            bounds: {
                                minX: minX,
                                maxX: maxX,
                                minY: minY,
                                maxY: maxY
                            }
                        };
                        
                        writeLog("Cell " + cellNumber + " loaded successfully", "DEBUG");
                    }
                }
            }
        }
        
        writeLog("====== END readBoardFile ======", "DEBUG");
        return coordinates;
    } catch (e) {
        writeLog("Error reading board file: " + e, "ERROR");
        writeLog("====== END readBoardFile (error) ======", "ERROR");
        return null;
    }
}

/**
 * Fonction pour calculer les informations sur le layout à partir du fichier .board
 * @param {string} boardPath - Chemin du fichier .board
 * @returns {Object} - Objet contenant les informations sur le layout
 */
function getLayoutCoordinates(boardPath) {
    try {
        writeLog("====== START getLayoutCoordinates ======", "DEBUG");
        
        // Normaliser le chemin du fichier
        boardPath = normalizePath(boardPath);
        
        if (!boardPath) {
            writeLog("ERROR: Board file path not specified", "ERROR");
            return null;
        }
        
        writeLog("Getting layout coordinates from board file", "DEBUG");
        
        // Vérifier si le fichier board existe
        if (!fileExists(boardPath)) {
            writeLog("Board file not found: " + boardPath, "ERROR");
            return null;
        }
        
        // Lire le contenu du fichier board
        var boardContent = readBoardFile(boardPath);
        if (!boardContent || countObjectProperties(boardContent) === 0) {
            writeLog("Board file is empty or could not be read", "ERROR");
            return null;
        }
        
        // Utiliser directement les coordonnées lues par readBoardFile
        var coordinates = boardContent;
        var nbrCurrentCells = countObjectProperties(coordinates);
        
        // Calculer le nombre de lignes et colonnes en fonction des positions réelles
        var yPositions = [];
        var xPositions = [];
        
        // Collecter toutes les positions y et x uniques
        for (var cellId in coordinates) {
            if (coordinates.hasOwnProperty(cellId)) {
                var cell = coordinates[cellId];
                var yPos = cell.topLeft[1]; // Position Y du coin supérieur gauche
                var xPos = cell.topLeft[0]; // Position X du coin supérieur gauche
                
                // Ajouter la position y si elle n'est pas déjà dans le tableau (avec une marge de tolérance)
                var yFound = false;
                for (var i = 0; i < yPositions.length; i++) {
                    if (Math.abs(yPositions[i] - yPos) < 10) { // Tolérance de 10px
                        yFound = true;
                        break;
                    }
                }
                if (!yFound) {
                    yPositions.push(yPos);
                }
                
                // Même chose pour les positions x
                var xFound = false;
                for (var i = 0; i < xPositions.length; i++) {
                    if (Math.abs(xPositions[i] - xPos) < 10) {
                        xFound = true;
                        break;
                    }
                }
                if (!xFound) {
                    xPositions.push(xPos);
                }
            }
        }
        
        // Le nombre de positions y uniques correspond au nombre de lignes
        nbrRows = yPositions.length;
        
        // Le nombre de positions x uniques correspond au nombre de colonnes
        nbrCols = xPositions.length;
        
        // Vérification simple: si le nombre de cellules est supérieur au produit nbrRows*nbrCols,
        // revenir à la méthode d'estimation par défaut
        if (nbrCurrentCells > nbrRows * nbrCols) {
            nbrCols = Math.ceil(Math.sqrt(nbrCurrentCells));
            nbrRows = Math.ceil(nbrCurrentCells / nbrCols);
        }
        
        // Trouver la dernière cellule
        var lastCellId = 0;
        for (var cellId in coordinates) {
            var id = parseInt(cellId, 10);
            if (!isNaN(id) && id > lastCellId) {
                lastCellId = id;
            }
        }
        
        // Extraire les données brutes des cellules pour référence
        var cellsData = [];
        for (var cellId in coordinates) {
            if (coordinates.hasOwnProperty(cellId)) {
                var cell = coordinates[cellId];
                var cellData = cellId + "," + 
                    cell.topLeft[0] + "," + cell.topLeft[1] + "," +
                    cell.topRight[0] + "," + cell.topRight[1] + "," +
                    cell.bottomLeft[0] + "," + cell.bottomLeft[1] + "," +
                    cell.bottomRight[0] + "," + cell.bottomRight[1];
                cellsData.push(cellData);
            }
        }
        
        // Retourner l'information complète du layout
        var layoutInfo = {
            coordinates: coordinates,
            nbrCurrentCells: nbrCurrentCells,
            nbrRows: nbrRows,
            nbrCols: nbrCols,
            lastCellId: lastCellId,
            cellsData: cellsData
        };
        
   
        // Ajouter un log plus explicite sur la structure de grille
        writeLog("GRID STRUCTURE DETECTED - Number of columns: " + nbrCols + ", Number of rows: " + nbrRows, "DEBUG");
        return layoutInfo;
    } catch (e) {
        writeLog("Error getting layout coordinates: " + e, "ERROR");
        writeLog("====== END getLayoutCoordinates (error) ======", "ERROR");
        return null;
    }
}

/**
 * Fonction pour lire les préférences depuis le fichier plist
 * @returns {Object} - Objet contenant les préférences
 */
function readPreferencesFromPlist() {
    try {
        // Si les préférences sont déjà en cache, les retourner
        if (globalPreferences !== null) {
            writeLog("Using cached preferences", "DEBUG");
            return globalPreferences;
        }

        var prefs = readPreferencesFromFile();
        if (prefs) {
            // Exclure les clés dynamiques du cache
            for (var i = 0; i < DYNAMIC_KEYS.length; i++) {
                delete prefs[DYNAMIC_KEYS[i]];
            }
            globalPreferences = prefs;
            writeLog("Preferences loaded and cached (excluding dynamic keys)", "INFO");
            return globalPreferences;
        }

        globalPreferences = {};
        return globalPreferences;
    } catch (e) {
        writeLog("ERROR during plist file reading: " + e, "ERROR");
        globalPreferences = {};
        return globalPreferences;
    }
}

/**
 * Nouvelle fonction pour lire directement le fichier sans utiliser le cache
 * @returns {Object} - Objet contenant les préférences
 */
function readPreferencesFromFile() {
    try {
        var userHome = Folder.userData.parent.parent;
        var possiblePaths = [
            userHome + "/Library/Preferences/Board/com.dityan.Board.plist",
        ];
        
        var plistFile = null;
        for (var i = 0; i < possiblePaths.length; i++) {
            var testFile = new File(possiblePaths[i]);
            if (testFile.exists) {
                plistFile = testFile;
                break;
            }
        }
        
        if (plistFile) {
            plistFile.open("r");
            var content = plistFile.read();
            plistFile.close();
            return parsePlistXML(content);
        }
    } catch (e) {
        writeLog("ERROR reading preferences file directly: " + e, "ERROR");
    }
    return null;
}

/**
 * Fonction pour analyser le contenu XML du fichier plist
 * @param {string} xmlContent - Contenu XML du fichier plist
 * @returns {Object} - Objet contenant les préférences
 */
function parsePlistXML(xmlContent) {
    try {
        if (!xmlContent || xmlContent.length === 0) {
            writeLog("XML content is empty, impossible to parse", "ERROR");
            return {};
        }
                
        var preferences = {};
        
        // Chercher tous les éléments <key> et leurs valeurs
        var keyRegex = /<key>(.*?)<\/key>\s*<(string|real|integer|true|false)>(.*?)<\/(string|real|integer)>/g;
        var boolKeyRegex = /<key>(.*?)<\/key>\s*<(true|false)\/>/g;
        
        // Extraire les paires clé-valeur standard
        var match;
        while ((match = keyRegex.exec(xmlContent)) !== null) {
            var key = match[1];
            var type = match[2];
            var value = match[3];
            
            // Convertir la valeur selon son type
            if (type === "real") {
                value = parseFloat(value);
            } else if (type === "integer") {
                value = parseInt(value, 10);
            }
            
            preferences[key] = value;
        }
        
        // Extraire les valeurs booléennes
        while ((match = boolKeyRegex.exec(xmlContent)) !== null) {
            var key = match[1];
            var type = match[2];
            preferences[key] = (type === "true");
        }
        
        // Ne logger que le nombre de préférences trouvées et uniquement psbPath
        // Utiliser notre fonction personnalisée au lieu de Object.keys
        var prefCount = countObjectProperties(preferences);
        writeLog("Number of preferences found: " + prefCount, "DEBUG");
        
        // Logger uniquement psbPath pour le débogage
        if (preferences.hasOwnProperty("psbPath")) {
            writeLog("Important preference: psbPath = " + preferences["psbPath"], "DEBUG");
        }
        
        return preferences;
    } catch (e) {
        writeLog("ERROR during plist file analysis: " + e, "ERROR");
        return {};
    }
}

/**
 * Fonction pour obtenir une valeur avec une valeur par défaut
 * @param {Object} preferences - Objet contenant les préférences
 * @param {string} key - Clé de la valeur à obtenir
 * @param {any} defaultValue - Valeur par défaut à retourner si la clé n'existe pas
 * @returns {any} - Valeur obtenue ou valeur par défaut
 */
function getPreferenceValue(preferences, key, defaultValue) {
    // Si la clé est dynamique, lire directement depuis le fichier
    if (arrayContains(DYNAMIC_KEYS, key)) {
        var dynamicPrefs = readPreferencesFromFile(); // Nouvelle fonction pour lire directement le fichier
        if (dynamicPrefs && dynamicPrefs.hasOwnProperty(key)) {
            return dynamicPrefs[key];
        }
        return defaultValue;
    }

    // Sinon utiliser le cache
    if (preferences && preferences.hasOwnProperty(key)) {
        return preferences[key];
    }
    return defaultValue;
}

/**
 * Fonction pour lire les arguments depuis le fichier
 * @returns {Object} - Objet contenant les arguments
 */
function readArgumentsFromFile() {
    try {
        // Déterminer l'emplacement du fichier d'arguments
        var argsFilePath = "";
        var argsFileFound = false;
        
        // Essayer d'abord le dossier du document actif
        if (app.documents.length > 0) {
            try {
                var docPath = app.activeDocument.path.fsName;
                var boardFolderPath = docPath + "/.board";
                var potentialPath = boardFolderPath + "/board_arguments.txt";
                
                if (fileExists(potentialPath)) {
                    argsFilePath = potentialPath;
                    argsFileFound = true;
                    writeLog("Arguments file found in document folder: " + argsFilePath, "DEBUG");
                }
            } catch(e) {
                writeLog("Error searching in document folder: " + e, "ERROR");
            }
        }
        
        // Si pas trouvé, essayer le dossier global
        if (!argsFileFound && globalDestFolder) {
            var globalBoardFolderPath = globalDestFolder + "/.board";
            var globalPotentialPath = globalBoardFolderPath + "/board_arguments.txt";
            
            if (fileExists(globalPotentialPath)) {
                argsFilePath = globalPotentialPath;
                argsFileFound = true;
                writeLog("Arguments file found in global folder: " + argsFilePath, "DEBUG");
            }
        }
        
        // Si toujours pas trouvé, essayer les emplacements standard
        if (!argsFileFound) {
            var userHome = "";
            // Déterminer le chemin du dossier utilisateur selon le système
            if ($.os.indexOf("Windows") >= 0) {
                userHome = Folder.myDocuments.parent.fsName;
            } else {
                userHome = Folder.userData.parent.parent.fsName;
            }
            
            var standardPaths = [
                userHome + "/Documents/.board/board_arguments.txt",
                userHome + "/Library/Application Support/Board/board_arguments.txt",
                userHome + "/Library/Preferences/Board/board_arguments.txt",
                userHome + "/Library/Caches/Board/board_arguments.txt",
                Folder.temp.fsName + "/board_arguments.txt"
            ];
            
            for (var i = 0; i < standardPaths.length; i++) {
                if (fileExists(standardPaths[i])) {
                    argsFilePath = standardPaths[i];
                    argsFileFound = true;
                    writeLog("Arguments file found in standard location: " + argsFilePath, "DEBUG");
                    break;
                }
            }
        }
        
        // Si le fichier n'est pas trouvé, retourner un objet vide
        if (!argsFileFound) {
            writeLog("No arguments file found, interactive mode activated", "INFO");
            return {};
        }
        
        // Lire le contenu du fichier d'arguments
        var argsFile = new File(argsFilePath);
        argsFile.open("r");
        var content = "";
        
        // Lire le fichier ligne par ligne
        while (!argsFile.eof) {
            content += argsFile.readln() + "\n";
        }
        argsFile.close();
        
        writeLog("Arguments file content read: " + content.length + " characters", "DEBUG");
        
        // Supprimer le fichier après l'avoir lu
        try {
            writeLog("Deleting arguments file: " + argsFilePath, "DEBUG");
            if (argsFile.remove()) {
                writeLog("Arguments file deleted successfully", "DEBUG");
            } else {
                writeLog("ERROR: Unable to delete arguments file", "ERROR");
            }
        } catch (e) {
            writeLog("ERROR deleting arguments file: " + e, "ERROR");
        }
        
        // Analyser le contenu du fichier
        var args = parseArgumentsContent(content);
        
        // Vérifier que le tableau des fichiers est bien initialisé
        if (!args.files) {
            args.files = [];
        }
        
        // Si imgPath existe, s'assurer qu'il est aussi dans le tableau files
        if (args.imgPath && !arrayContains(args.files, args.imgPath)) {
            args.files.push(args.imgPath);
        }
        
        return args;
    } catch (e) {
        writeLog("Error reading arguments: " + e, "ERROR");
        return {};
    }
}

/**
 * Fonction pour analyser le contenu du fichier d'arguments
 * @param {string} content - Contenu du fichier d'arguments
 * @returns {Object} - Objet contenant les arguments
 */
function parseArgumentsContent(content) {
    try {
        writeLog("Analyzing arguments content...", "DEBUG");
        
        // Vérifier si le contenu est vide
        if (!content || content.length === 0) {
            writeLog("Arguments content is empty", "WARNING");
            return {};
        }
        
        // Normaliser les fins de ligne
        content = content.replace(/\r\n|\r|\n/g, "\n");
        
        // Séparer les lignes
        var lines = content.split("\n");
        writeLog("Number of lines after division: " + lines.length, "DEBUG");
        
        // Créer un objet pour stocker les arguments
        var argumentsObj = {
            action: "putInBoard", // Action par défaut
            files: []          // Tableau pour stocker les chemins de fichiers
        };
        
        // Traiter chaque ligne
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].replace(/^\s+|\s+$/g, ""); // Équivalent de trim()
            
            // Ignorer les lignes vides
            if (line.length === 0) continue;
            
            writeLog("Processing line " + (i+1) + ": [" + line + "]", "DEBUG");
            
            // Vérifier si la ligne contient un séparateur clé=valeur
            if (line.indexOf("=") !== -1) {
                var parts = line.split("=");
                var key = parts[0].replace(/^\s+|\s+$/g, "");
                
                // Reconstruire la valeur au cas où elle contiendrait des '='
                var valueArr = [];
                for (var j = 1; j < parts.length; j++) {
                    valueArr.push(parts[j]);
                }
                var value = valueArr.join("=").replace(/^\s+|\s+$/g, "");
                
                // Ignorer les clés vides
                if (key.length > 0) {
                    // Traitement spécial pour imgPath
                    if (key === "imgPath") {
                        // Normaliser le chemin avec toutes les variantes possibles
                        var normalizedPath = normalizePath(value);
                        
                        argumentsObj[key] = normalizedPath;
                        // Ajouter au tableau des fichiers s'il n'y est pas déjà
                        if (!arrayContains(argumentsObj.files, normalizedPath)) {
                            argumentsObj.files.push(normalizedPath);
                        }
                        writeLog("Image path found: " + normalizedPath, "DEBUG");
                    } else {
                        // Autres clés
                        argumentsObj[key] = value;
                        writeLog("Argument found: " + key + " = " + value, "DEBUG");
                    }
                }
            } else {
                // Si pas de séparateur, considérer comme un chemin de fichier
                // Vérifier que le chemin semble valide (contient au moins un slash)
                if (line.indexOf("/") !== -1 || line.indexOf("\\") !== -1) {
                    // Normaliser le chemin avec toutes les variantes possibles
                    var normalizedPath = normalizePath(line);
                    
                    // S'assurer que le chemin n'est pas déjà dans le tableau
                    if (!arrayContains(argumentsObj.files, normalizedPath)) {
                        argumentsObj.files.push(normalizedPath);
                        writeLog("File path found: " + normalizedPath, "DEBUG");
                    }
                } else {
                    writeLog("Unrecognized line ignored: " + line, "WARNING");
                }
            }
        }
        
        // Log détaillé des fichiers trouvés
        if (argumentsObj.files.length > 0) {
            writeLog("===== List of files in the arguments file =====", "DEBUG");
            writeLog("Total number of files: " + argumentsObj.files.length, "INFO");
            for (var k = 0; k < argumentsObj.files.length; k++) {
                writeLog("Fichier " + (k+1) + ": " + argumentsObj.files[k], "DEBUG");
            }
            writeLog("=====================================================", "DEBUG");
        } else {
            writeLog("No files found in the arguments file", "WARNING");
        }
        
        return argumentsObj;
    } catch (e) {
        writeLog("Error parsing arguments: " + e, "ERROR");
        return {};
    }
}

/**
 * Vérifie si un rectangle (défini par bounds) intersecte avec une zone
 * @param {Number} x1 - Coordonnée X minimale du rectangle
 * @param {Number} y1 - Coordonnée Y minimale du rectangle
 * @param {Number} x2 - Coordonnée X maximale du rectangle
 * @param {Number} y2 - Coordonnée Y maximale du rectangle
 * @param {Object} zone - Zone à tester {minX, maxX, minY, maxY}
 * @returns {Boolean} - true si intersection, false sinon
 */
function rectangleIntersects(x1, y1, x2, y2, zone) {
    // Deux rectangles A et B s'intersectent si et seulement si :
    // A.x1 < B.x2 ET A.x2 > B.x1 ET A.y1 < B.y2 ET A.y2 > B.y1
    return (
        x1 < zone.maxX &&
        x2 > zone.minX &&
        y1 < zone.maxY &&
        y2 > zone.minY
    );
}

/**
 * Vérifie si une cellule est occupée en analysant les bounds des calques
 * Méthode OPTIMISÉE beaucoup plus rapide que l'échantillonnage de pixels (70-85% gain)
 * @param {Object} cellBounds - Bounds de la cellule {minX, maxX, minY, maxY}
 * @param {String} cellType - Type de cellule ("Single" ou "Spread")
 * @param {Document} doc - Document Photoshop actif
 * @returns {Array} - [leftEmpty, rightEmpty] ou [cellEmpty] pour Single
 */
function checkCellOccupancyByLayers(cellBounds, cellType, doc) {
    writeLog("====== START checkCellOccupancyByLayers (OPTIMIZED) ======", "DEBUG");
    
    try {
        // Récupérer ou valider le cache du groupe Board Content
        if (!gBoardContentGroupValid || !gBoardContentGroup) {
            try {
                gBoardContentGroup = doc.layerSets.getByName("Board Content");
                gBoardContentGroupValid = true;
                writeLog("Board Content group found and cached (optimized detection enabled)", "INFO");
            } catch (e) {
                gBoardContentGroupValid = false;
                throw new Error("Board Content group not found, will use fallback method");
            }
        }
        
        var layers = gBoardContentGroup.artLayers;
        var layerCount = layers.length;
        
        writeLog("Analyzing " + layerCount + " layers using optimized method", "DEBUG");
        
        // Pour les cellules de type "Spread"
        if (cellType.toLowerCase() === "spread") {
            // Calculer les deux zones (gauche et droite)
            var cellWidth = cellBounds.maxX - cellBounds.minX;
            var cellCenterX = cellBounds.minX + (cellWidth / 2);
            
            var leftZone = {
                minX: cellBounds.minX,
                maxX: cellCenterX,
                minY: cellBounds.minY,
                maxY: cellBounds.maxY
            };
            
            var rightZone = {
                minX: cellCenterX,
                maxX: cellBounds.maxX,
                minY: cellBounds.minY,
                maxY: cellBounds.maxY
            };
            
            writeLog("Left zone: (" + Math.round(leftZone.minX) + "," + Math.round(leftZone.minY) + ") to (" + 
                    Math.round(leftZone.maxX) + "," + Math.round(leftZone.maxY) + ")", "DEBUG");
            writeLog("Right zone: (" + Math.round(rightZone.minX) + "," + Math.round(rightZone.minY) + ") to (" + 
                    Math.round(rightZone.maxX) + "," + Math.round(rightZone.maxY) + ")", "DEBUG");
            
            var leftOccupied = false;
            var rightOccupied = false;
            
            // Parcourir tous les calques
            for (var i = 0; i < layerCount; i++) {
                var layer = layers[i];
                
                // IMPORTANT : Ignorer les calques invisibles ou avec opacité = 0
                if (layer.opacity === 0 || !layer.visible) {
                    writeLog("Skipping layer: " + layer.name + " (opacity=" + layer.opacity + ", visible=" + layer.visible + ")", "DEBUG");
                    continue;
                }
                
                var bounds = layer.bounds;
                
                // Extraire les coordonnées du calque
                var layerX1 = bounds[0].value;
                var layerY1 = bounds[1].value;
                var layerX2 = bounds[2].value;
                var layerY2 = bounds[3].value;
                
                // DEBUG : Log des bounds du calque
                writeLog("Layer " + layer.name + " bounds: (" + Math.round(layerX1) + "," + Math.round(layerY1) + 
                        ") to (" + Math.round(layerX2) + "," + Math.round(layerY2) + ")", "DEBUG");
                
                // FIX 2025-10-01: Utiliser le centre + largeur pour déterminer l'occupation
                // Une image portrait ne doit occuper qu'un seul côté, même si ses bounds débordent légèrement
                var layerCenterX = (layerX1 + layerX2) / 2;
                var layerWidth = layerX2 - layerX1;
                var cellWidth = cellBounds.maxX - cellBounds.minX;
                var widthRatio = layerWidth / cellWidth;
                
                writeLog("Layer center X: " + Math.round(layerCenterX) + ", width: " + Math.round(layerWidth) + 
                        " (" + Math.round(widthRatio * 100) + "% of cell)", "DEBUG");
                
                // Si l'image occupe plus de 60% de la largeur de la cellule, elle occupe les deux côtés
                if (widthRatio > 0.6) {
                    // Image large (landscape) qui occupe toute la spread
                    if (!leftOccupied && rectangleIntersects(layerX1, layerY1, layerX2, layerY2, leftZone)) {
                        leftOccupied = true;
                        writeLog("Left side occupied by wide layer: " + layer.name, "DEBUG");
                    }
                    if (!rightOccupied && rectangleIntersects(layerX1, layerY1, layerX2, layerY2, rightZone)) {
                        rightOccupied = true;
                        writeLog("Right side occupied by wide layer: " + layer.name, "DEBUG");
                    }
                } else {
                    // Image étroite (portrait) - utiliser le centre pour déterminer le côté
                    if (!leftOccupied && layerCenterX < cellCenterX) {
                        leftOccupied = true;
                        writeLog("Left side occupied by narrow layer (center-based): " + layer.name, "DEBUG");
                    }
                    if (!rightOccupied && layerCenterX >= cellCenterX) {
                        rightOccupied = true;
                        writeLog("Right side occupied by narrow layer (center-based): " + layer.name, "DEBUG");
                    }
                }
                
                // Early exit : si les deux côtés sont occupés, pas besoin de continuer
                if (leftOccupied && rightOccupied) {
                    writeLog("Both sides occupied, early exit at layer " + (i+1) + "/" + layerCount, "DEBUG");
                    break;
                }
            }
            
            writeLog("Spread cell analysis (optimized): left=" + !leftOccupied + ", right=" + !rightOccupied, "INFO");
            writeLog("====== END checkCellOccupancyByLayers (SUCCESS) ======", "DEBUG");
            return [!leftOccupied, !rightOccupied];
            
        } else {
            // Pour les cellules de type "Single"
            var cellOccupied = false;
            
            writeLog("Single cell zone: (" + Math.round(cellBounds.minX) + "," + Math.round(cellBounds.minY) + ") to (" + 
                    Math.round(cellBounds.maxX) + "," + Math.round(cellBounds.maxY) + ")", "DEBUG");
            
            // Parcourir tous les calques
            for (var j = 0; j < layerCount; j++) {
                var layer = layers[j];
                
                // IMPORTANT : Ignorer les calques invisibles ou avec opacité = 0
                if (layer.opacity === 0 || !layer.visible) {
                    writeLog("Skipping layer: " + layer.name + " (opacity=" + layer.opacity + ", visible=" + layer.visible + ")", "DEBUG");
                    continue;
                }
                
                var bounds = layer.bounds;
                
                // Extraire les coordonnées du calque
                var layerX1 = bounds[0].value;
                var layerY1 = bounds[1].value;
                var layerX2 = bounds[2].value;
                var layerY2 = bounds[3].value;
                
                // DEBUG : Log des bounds du calque
                writeLog("Layer " + layer.name + " bounds: (" + Math.round(layerX1) + "," + Math.round(layerY1) + 
                        ") to (" + Math.round(layerX2) + "," + Math.round(layerY2) + ")", "DEBUG");
                
                // IMPORTANT : Utiliser le CENTRE du calque plutôt que les bounds complets
                var layerCenterX = (layerX1 + layerX2) / 2;
                var layerCenterY = (layerY1 + layerY2) / 2;
                
                writeLog("Layer " + layer.name + " center: (" + Math.round(layerCenterX) + "," + Math.round(layerCenterY) + ")", "DEBUG");
                
                // Vérifier si le centre du calque est dans la cellule
                if (layerCenterX >= cellBounds.minX && layerCenterX < cellBounds.maxX &&
                    layerCenterY >= cellBounds.minY && layerCenterY < cellBounds.maxY) {
                    cellOccupied = true;
                    writeLog("Single cell occupied by layer: " + layer.name + " (center-based)", "DEBUG");
                    break; // Early exit
                }
            }
            
            writeLog("Single cell analysis (optimized): empty=" + !cellOccupied, "INFO");
            writeLog("====== END checkCellOccupancyByLayers (SUCCESS) ======", "DEBUG");
            return [!cellOccupied, !cellOccupied]; // Format compatible avec checkSamplers
        }
        
    } catch (e) {
        writeLog("ERROR in checkCellOccupancyByLayers: " + e, "ERROR");
        writeLog("====== END checkCellOccupancyByLayers (ERROR) ======", "ERROR");
        throw e; // Propager l'erreur pour le fallback
    }
}

/**
 * Fonction pour effectuer l'échantillonnage de couleur
 * OPTIMISÉ : Tente d'abord la détection par analyse de calques (70-85% plus rapide)
 * puis fallback sur l'échantillonnage de pixels si nécessaire
 * @param {Object} samplingPoints - Objet contenant les points d'échantillonnage
 * @param {string} cellType - Type de cellule (Single ou Spread)
 * @returns {Array} - Tableau contenant les résultats de l'échantillonnage
 */
function checkSamplers(samplingPoints, cellType) {
    writeLog("====== START checkSamplers ======", "DEBUG");
    
    try {
        // Référence au document
        var doc = app.activeDocument;
        
        // OPTIMISATION : Tenter d'abord la détection par analyse de calques
        // Cette méthode est 70-85% plus rapide que l'échantillonnage de pixels
        var useLayerDetection = true; // Peut être désactivé via préférence si besoin
        
        if (useLayerDetection) {
            writeLog("Attempting optimized layer-based detection...", "DEBUG");
            
            try {
                // Extraire les bounds exacts de la cellule depuis samplingPoints
                // L'objet samplingPoints contient maintenant cellBounds directement (OPTIMISATION)
                var cellBounds = null;
                
                if (samplingPoints && samplingPoints.cellBounds) {
                    // Utiliser les bounds exacts fournis par calculateSamplingPoints
                    cellBounds = samplingPoints.cellBounds;
                    writeLog("Using exact cell bounds: " + 
                            Math.round(cellBounds.minX) + "," + Math.round(cellBounds.minY) + " to " + 
                            Math.round(cellBounds.maxX) + "," + Math.round(cellBounds.maxY), "DEBUG");
                } else if (samplingPoints && samplingPoints.leftPoints && samplingPoints.leftPoints.length > 0) {
                    // Fallback : Estimer les bounds depuis les points d'échantillonnage
                    var leftPoint = samplingPoints.leftPoints[0];
                    var rightPoint = samplingPoints.rightPoints ? samplingPoints.rightPoints[0] : leftPoint;
                    
                    var estimatedCellWidth = Math.abs(rightPoint[0] - leftPoint[0]) * 2;
                    var estimatedCellCenterX = (leftPoint[0] + rightPoint[0]) / 2;
                    
                    cellBounds = {
                        minX: estimatedCellCenterX - (estimatedCellWidth / 2),
                        maxX: estimatedCellCenterX + (estimatedCellWidth / 2),
                        minY: Math.min(leftPoint[1], rightPoint[1]) - 200,
                        maxY: Math.max(leftPoint[1], rightPoint[1]) + 200
                    };
                    
                    writeLog("Estimated cell bounds from sampling points: " + 
                            Math.round(cellBounds.minX) + "," + Math.round(cellBounds.minY) + " to " + 
                            Math.round(cellBounds.maxX) + "," + Math.round(cellBounds.maxY), "DEBUG");
                }
                
                // Tenter la détection optimisée
                if (cellBounds) {
                    var optimizedResult = checkCellOccupancyByLayers(cellBounds, cellType, doc);
                    writeLog("Optimized layer-based detection SUCCESSFUL", "INFO");
                    writeLog("====== END checkSamplers (OPTIMIZED PATH) ======", "DEBUG");
                    return optimizedResult;
                }
                
            } catch (e) {
                writeLog("Optimized detection failed: " + e + ", falling back to pixel sampling", "WARNING");
                // Continuer avec la méthode classique ci-dessous
            }
        }
        
        // MÉTHODE CLASSIQUE : Échantillonnage de pixels
        writeLog("Using classic pixel sampling method", "INFO");
        
        // Forcer une actualisation de l'affichage
        app.refresh();
        
        // Ajouter un court délai pour permettre à Photoshop de terminer le rendu
        //$.sleep(50);
        
        // Récupérer la couleur de fond à comparer (blanc par défaut)
        var backgroundColor = "FFFFFF";
        var preferences = readPreferencesFromPlist();
        
        if (preferences) {
            backgroundColor = getPreferenceValue(preferences, "backgroundColor", "FFFFFF");
            writeLog("Background color retrieved from preferences: " + backgroundColor, "INFO");
        } else {
            writeLog("Using default background color: " + backgroundColor, "INFO");
        }
        
        // Convertir la couleur hexadécimale en RGB
        var r = parseInt(backgroundColor.substr(0, 2), 16) || 255;
        var g = parseInt(backgroundColor.substr(2, 2), 16) || 255;
        var b = parseInt(backgroundColor.substr(4, 2), 16) || 255;
        
        writeLog("Background color (RGB): R=" + r + " G=" + g + " B=" + b, "INFO");
        
        // Tolérance fixée à 0 - nous voulons une correspondance exacte
        var tolerance = 0;
        writeLog("Tolerance: " + tolerance, "DEBUG");
        
        // Supprimer les échantillonneurs existants
        try {
            while (doc.colorSamplers.length > 0) {
                doc.colorSamplers[0].remove();
            }
        } catch (e) {
            writeLog("Note: No samplers to remove", "DEBUG");
        }
        
        // Initialiser les résultats (valeurs par défaut)
        var leftEmpty = true;
        var rightEmpty = true;
        var singleEmpty = true;
        
        // Pour les cellules de type "Spread"
        if (cellType.toLowerCase() === "spread") {
            // Vérifier que les points d'échantillonnage sont bien définis
            if (!samplingPoints || !samplingPoints.leftPoints || !samplingPoints.rightPoints) {
                writeLog("ERROR: Sampling points not defined for Spread cell", "ERROR");
                return [false, false];
            }
            
            // Vérifier tous les points du côté gauche
            for (var i = 0; i < samplingPoints.leftPoints.length && leftEmpty; i++) {
                var pointArray = samplingPoints.leftPoints[i];
                var x = pointArray[0];
                var y = pointArray[1];
                
                writeLog("Checking left point " + (i+1) + ": " + x + "," + y, "DEBUG");
                
                // Vérifier que les coordonnées sont valides
                if (!isNaN(x) && !isNaN(y) && 
                    x >= 0 && y >= 0 && 
                    x < doc.width.value && y < doc.height.value) {
                    
                    try {
                        // Créer un échantillonneur
                        var xUnit = UnitValue(x, "px");
                        var yUnit = UnitValue(y, "px");
                        
                        var sampler = doc.colorSamplers.add([xUnit, yUnit]);
                        
                        // Sécuriser l'accès aux valeurs de couleur
                        var sampledColor = [
                            sampler.color.rgb.red || 0,
                            sampler.color.rgb.green || 0,
                            sampler.color.rgb.blue || 0
                        ];
                        
                        writeLog("Sampled color (left " + (i+1) + "): R=" + sampledColor[0] + " G=" + sampledColor[1] + " B=" + sampledColor[2], "DEBUG");
                        
                        // Comparer avec la couleur de fond (correspondance exacte)
                        var colorDiff = Math.abs(sampledColor[0] - r) + 
                                      Math.abs(sampledColor[1] - g) + 
                                      Math.abs(sampledColor[2] - b);
                        
                        var pointEmpty = (colorDiff === 0);
                        writeLog("Color difference: " + colorDiff + ", point empty: " + pointEmpty, "DEBUG");
                        
                        // Si un seul point n'est pas vide, toute la zone est considérée comme non vide
                        if (!pointEmpty) {
                            leftEmpty = false;
                        }
                        
                        // Supprimer l'échantillonneur
                        sampler.remove();
                    } catch (e) {
                        writeLog("ERROR sampling left point " + (i+1) + ": " + e, "ERROR");
                    }
                } else {
                    writeLog("Left point " + (i+1) + " coordinates out of bounds", "WARNING");
                }
            }
            
            // Vérifier tous les points du côté droit
            for (var i = 0; i < samplingPoints.rightPoints.length && rightEmpty; i++) {
                var pointArray = samplingPoints.rightPoints[i];
                var x = pointArray[0];
                var y = pointArray[1];
                
                writeLog("Checking right point " + (i+1) + ": " + x + "," + y, "DEBUG");
                
                // Vérifier que les coordonnées sont valides
                if (!isNaN(x) && !isNaN(y) && 
                    x >= 0 && y >= 0 && 
                    x < doc.width.value && y < doc.height.value) {
                    
                    try {
                        // Créer un échantillonneur
                        var xUnit = UnitValue(x, "px");
                        var yUnit = UnitValue(y, "px");
                        
                        var sampler = doc.colorSamplers.add([xUnit, yUnit]);
                        
                        // Sécuriser l'accès aux valeurs de couleur
                        var sampledColor = [
                            sampler.color.rgb.red || 0,
                            sampler.color.rgb.green || 0,
                            sampler.color.rgb.blue || 0
                        ];
                        
                        writeLog("Sampled color (right " + (i+1) + "): R=" + sampledColor[0] + " G=" + sampledColor[1] + " B=" + sampledColor[2], "DEBUG");
                        
                        // Comparer avec la couleur de fond (correspondance exacte)
                        var colorDiff = Math.abs(sampledColor[0] - r) + 
                                      Math.abs(sampledColor[1] - g) + 
                                      Math.abs(sampledColor[2] - b);
                        
                        var pointEmpty = (colorDiff === 0);
                        writeLog("Color difference: " + colorDiff + ", point empty: " + pointEmpty, "DEBUG");
                        
                        // Si un seul point n'est pas vide, toute la zone est considérée comme non vide
                        if (!pointEmpty) {
                            rightEmpty = false;
                        }
                        
                        // Supprimer l'échantillonneur
                        sampler.remove();
                    } catch (e) {
                        writeLog("ERROR sampling right point " + (i+1) + ": " + e, "ERROR");
                    }
                } else {
                    writeLog("Right point " + (i+1) + " coordinates out of bounds", "WARNING");
                }
            }
            
            writeLog("Sampling results - Left: " + leftEmpty + ", Right: " + rightEmpty, "DEBUG");
            return [leftEmpty, rightEmpty];
        } 
        // Pour les cellules de type "Single"
        else {
            // Vérifier que les points d'échantillonnage sont bien définis
            if (!samplingPoints || !samplingPoints.points) {
                writeLog("ERROR: Sampling points not defined for Single cell", "ERROR");
                return [false];
            }
            
            // Vérifier tous les points
            for (var i = 0; i < samplingPoints.points.length && singleEmpty; i++) {
                var pointArray = samplingPoints.points[i];
                var x = pointArray[0];
                var y = pointArray[1];
                
                writeLog("Checking point " + (i+1) + ": " + x + "," + y, "DEBUG");
                
                // Vérifier que les coordonnées sont valides
                if (!isNaN(x) && !isNaN(y) && 
                    x >= 0 && y >= 0 && 
                    x < doc.width.value && y < doc.height.value) {
                    
                    try {
                        // Créer un échantillonneur
                        var xUnit = UnitValue(x, "px");
                        var yUnit = UnitValue(y, "px");
                        
                        var sampler = doc.colorSamplers.add([xUnit, yUnit]);
                        
                        // Sécuriser l'accès aux valeurs de couleur
                        var sampledColor = [
                            sampler.color.rgb.red || 0,
                            sampler.color.rgb.green || 0,
                            sampler.color.rgb.blue || 0
                        ];
                        
                        writeLog("Sampled color (point " + (i+1) + "): R=" + sampledColor[0] + " G=" + sampledColor[1] + " B=" + sampledColor[2], "DEBUG");
                        
                        // Comparer avec la couleur de fond (correspondance exacte)
                        var colorDiff = Math.abs(sampledColor[0] - r) + 
                                      Math.abs(sampledColor[1] - g) + 
                                      Math.abs(sampledColor[2] - b);
                        
                        var pointEmpty = (colorDiff === 0);
                        writeLog("Color difference: " + colorDiff + ", point empty: " + pointEmpty, "DEBUG");
                        
                        // Si un seul point n'est pas vide, toute la zone est considérée comme non vide
                        if (!pointEmpty) {
                            singleEmpty = false;
                        }
                        
                        // Supprimer l'échantillonneur
                        sampler.remove();
                    } catch (e) {
                        writeLog("ERROR sampling point " + (i+1) + ": " + e, "ERROR");
                    }
                } else {
                    writeLog("Point " + (i+1) + " coordinates out of bounds", "WARNING");
                }
            }
            
            writeLog("Sampling results - Single: " + singleEmpty, "DEBUG");
            return [singleEmpty];
        }
    } catch (e) {
        writeLog("Error in checkSamplers: " + e, "ERROR");
        writeLog("====== END checkSamplers (error) ======", "ERROR");
        
        // Retourner des valeurs par défaut en cas d'erreur
        if (cellType.toLowerCase() === "spread") {
            return [false, false];
        } else {
            return [false];
        }
    }
}

/**
 * Fonction pour calculer les points d'échantillonnage
 * @param {Object} cell - Objet cellule
 * @param {string} cellType - Type de cellule
 * @returns {Object} - Objet contenant les points d'échantillonnage
 */
function calculateSamplingPoints(cell, cellType) {
    try {
        writeLog("====== START calculateSamplingPoints ======", "DEBUG");
        
        // Obtenir le niveau de détection des cellules depuis les préférences
        var preferences = readPreferencesFromPlist();
        var detectionLevel = parseInt(getPreferenceValue(preferences, "cellDetectionLevel", 3));
        
        // S'assurer que le niveau est valide (1-5)
        if (isNaN(detectionLevel) || detectionLevel < 1 || detectionLevel > 5) {
            detectionLevel = 3; // Niveau par défaut
        }
        
        writeLog("Using cell detection level: " + detectionLevel, "DEBUG");
        
        // Vérifier si l'objet cell est correctement structuré
        if (!cell || !cell.bounds) {
            writeLog("ERROR: Cell object is not properly structured", "ERROR");
            return null;
        }
        
        // Extraire les dimensions de la cellule depuis la propriété bounds
        var bounds = cell.bounds;
        var minX = bounds.minX;
        var maxX = bounds.maxX;
        var minY = bounds.minY;
        var maxY = bounds.maxY;
        
        // Calculer les dimensions et le centre de la cellule
        var width = maxX - minX;
        var height = maxY - minY;
        var centerX = minX + (width / 2);
        var centerY = minY + (height / 2);
        
        writeLog("Cell dimensions: width=" + width + ", height=" + height + ", center=(" + centerX + "," + centerY + ")", "DEBUG");
        
        // Points d'échantillonnage pour les cellules de type "Spread"
        if (cellType.toLowerCase() === "spread") {
            // Calculer le centre de chaque moitié
            var leftCenterX = minX + (width / 4);
            var rightCenterX = minX + (width * 3 / 4);
            var middleY = minY + (height / 2);
            
            var leftPoints = [];
            var rightPoints = [];
            
            // Générer les points selon le niveau de détection
            switch (detectionLevel) {
                case 1:
                    // 1 point au centre de chaque moitié
                    leftPoints.push([leftCenterX, middleY]);
                    rightPoints.push([rightCenterX, middleY]);
                    break;
                    
                case 2:
                    // 2 points pour chaque moitié
                    var quarterHeight = height / 4;
                    leftPoints.push([leftCenterX, middleY - quarterHeight]);
                    leftPoints.push([leftCenterX, middleY + quarterHeight]);
                    rightPoints.push([rightCenterX, middleY - quarterHeight]);
                    rightPoints.push([rightCenterX, middleY + quarterHeight]);
                    break;
                    
                case 3:
                    // 3 points pour chaque moitié
                    var thirdHeight = height / 3;
                    leftPoints.push([leftCenterX, middleY]);
                    leftPoints.push([leftCenterX, middleY - thirdHeight]);
                    leftPoints.push([leftCenterX, middleY + thirdHeight]);
                    rightPoints.push([rightCenterX, middleY]);
                    rightPoints.push([rightCenterX, middleY - thirdHeight]);
                    rightPoints.push([rightCenterX, middleY + thirdHeight]);
                    break;
                    
                case 4:
                case 5: // Niveaux 4 et 5 utilisent 4 points pour les cellules Spread
                    // 4 points pour chaque moitié
                    var quarterHeight = height / 4;
                    leftPoints.push([leftCenterX, middleY - quarterHeight * 1.5]);
                    leftPoints.push([leftCenterX, middleY - quarterHeight * 0.5]);
                    leftPoints.push([leftCenterX, middleY + quarterHeight * 0.5]);
                    leftPoints.push([leftCenterX, middleY + quarterHeight * 1.5]);
                    rightPoints.push([rightCenterX, middleY - quarterHeight * 1.5]);
                    rightPoints.push([rightCenterX, middleY - quarterHeight * 0.5]);
                    rightPoints.push([rightCenterX, middleY + quarterHeight * 0.5]);
                    rightPoints.push([rightCenterX, middleY + quarterHeight * 1.5]);
                    break;
                    
                default:
                    // Fallback - 3 points par défaut
                    var thirdHeight = height / 3;
                    leftPoints.push([leftCenterX, middleY]);
                    leftPoints.push([leftCenterX, middleY - thirdHeight]);
                    leftPoints.push([leftCenterX, middleY + thirdHeight]);
                    rightPoints.push([rightCenterX, middleY]);
                    rightPoints.push([rightCenterX, middleY - thirdHeight]);
                    rightPoints.push([rightCenterX, middleY + thirdHeight]);
            }
            
            writeLog("Generated " + leftPoints.length + " sampling points for left part and " + 
                    rightPoints.length + " for right part of cell type: " + cellType, "DEBUG");
            
            return {
                leftPoint: leftPoints[0], // Pour compatibilité avec le code existant
                rightPoint: rightPoints[0], // Pour compatibilité avec le code existant
                leftPoints: leftPoints,
                rightPoints: rightPoints,
                cellBounds: bounds // OPTIMISATION : Ajouter les bounds pour la détection par calques
            };
        } 
        // Points d'échantillonnage pour les cellules de type "Single"
        else {
            var points = [];
            
            // Générer les points selon le niveau de détection
            switch (detectionLevel) {
                case 1:
                    // 1 point au centre
                    points.push([centerX, centerY]);
                    break;
                    
                case 2:
                    // 2 points dans une zone moyenne
                    var offsetX = width / 4;
                    points.push([centerX - offsetX, centerY]);
                    points.push([centerX + offsetX, centerY]);
                    break;
                    
                case 3:
                    // 3 points dans une zone moyenne
                    var offsetX = width / 5;
                    var offsetY = height / 5;
                    points.push([centerX, centerY]);
                    points.push([centerX - offsetX, centerY - offsetY]);
                    points.push([centerX + offsetX, centerY + offsetY]);
                    break;
                    
                case 4:
                    // 4 points
                    var offsetX = width / 5;
                    var offsetY = height / 5;
                    points.push([centerX - offsetX, centerY - offsetY]);
                    points.push([centerX + offsetX, centerY - offsetY]);
                    points.push([centerX - offsetX, centerY + offsetY]);
                    points.push([centerX + offsetX, centerY + offsetY]);
                    break;
                    
                case 5:
                    // 5 points
                    var offsetX = width / 5;
                    var offsetY = height / 5;
                    points.push([centerX, centerY]);
                    points.push([centerX - offsetX, centerY - offsetY]);
                    points.push([centerX + offsetX, centerY - offsetY]);
                    points.push([centerX - offsetX, centerY + offsetY]);
                    points.push([centerX + offsetX, centerY + offsetY]);
                    break;
                    
                default:
                    // Fallback - 3 points par défaut
                    var offsetX = width / 5;
                    var offsetY = height / 5;
                    points.push([centerX, centerY]);
                    points.push([centerX - offsetX, centerY - offsetY]);
                    points.push([centerX + offsetX, centerY + offsetY]);
            }
            
            writeLog("Generated " + points.length + " sampling points for cell type: " + cellType, "DEBUG");
            
            return {
                point: points[0], // Pour compatibilité avec le code existant
                points: points,
                cellBounds: bounds // OPTIMISATION : Ajouter les bounds pour la détection par calques
            };
        }
    } catch (e) {
        writeLog("Error in calculateSamplingPoints: " + e, "ERROR");
        writeLog("====== END calculateSamplingPoints (error) ======", "ERROR");
        
        // Retourner un point par défaut en cas d'erreur
        if (cellType.toLowerCase() === "spread") {
            // Utiliser les propriétés bounds si disponibles, sinon des valeurs par défaut
            var minX = (cell && cell.bounds) ? cell.bounds.minX : 0;
            var maxX = (cell && cell.bounds) ? cell.bounds.maxX : 100;
            var minY = (cell && cell.bounds) ? cell.bounds.minY : 0;
            var maxY = (cell && cell.bounds) ? cell.bounds.maxY : 100;
            
            var width = maxX - minX;
            var height = maxY - minY;
            
            var leftCenterX = minX + (width / 4);
            var rightCenterX = minX + (width * 3 / 4);
            var middleY = minY + (height / 2);
            
            return {
                leftPoint: [leftCenterX, middleY],
                rightPoint: [rightCenterX, middleY],
                leftPoints: [[leftCenterX, middleY]],
                rightPoints: [[rightCenterX, middleY]]
            };
        } else {
            // Utiliser les propriétés bounds si disponibles, sinon des valeurs par défaut
            var minX = (cell && cell.bounds) ? cell.bounds.minX : 0;
            var maxX = (cell && cell.bounds) ? cell.bounds.maxX : 100;
            var minY = (cell && cell.bounds) ? cell.bounds.minY : 0;
            var maxY = (cell && cell.bounds) ? cell.bounds.maxY : 100;
            
            var width = maxX - minX;
            var height = maxY - minY;
            
            var centerX = minX + (width / 2);
            var centerY = minY + (height / 2);
            
            return {
                point: [centerX, centerY],
                points: [[centerX, centerY]]
            };
        }
    }
}

/**
 * Fonction pour créer un guide horizontal
 * @param {number} yPosition - Position y du guide
 * @returns {void}  
 */
function createHorizontalGuide(yPosition) {
    try {
        var idMk = charIDToTypeID("Mk  ");
        var desc = new ActionDescriptor();
        var idNw = charIDToTypeID("Nw  ");
        var descGuide = new ActionDescriptor();
        var idOrnt = charIDToTypeID("Ornt");
        var idOrnt = charIDToTypeID("Ornt");
        var idHrzn = charIDToTypeID("Hrzn");
        descGuide.putEnumerated(idOrnt, idOrnt, idHrzn);
        var idPstn = charIDToTypeID("Pstn");
        var idPxl = charIDToTypeID("#Pxl");
        descGuide.putUnitDouble(idPstn, idPxl, yPosition);
        var idGd = charIDToTypeID("Gd  ");
        desc.putObject(idNw, idGd, descGuide);
        executeAction(idMk, desc, DialogModes.NO);
    } catch(e) {
        writeLog("Error creating horizontal guide: " + e, "CRITICAL");
    }
}

/**
 * Fonction pour créer un guide vertical
 * @param {number} xPosition - Position x du guide
 * @returns {void}  
 */
function createVerticalGuide(xPosition) {
    try {
        var idMk = charIDToTypeID("Mk  ");
        var desc = new ActionDescriptor();
        var idNw = charIDToTypeID("Nw  ");
        var descGuide = new ActionDescriptor();
        var idOrnt = charIDToTypeID("Ornt");
        var idOrnt = charIDToTypeID("Ornt");
        var idVrtc = charIDToTypeID("Vrtc");
        descGuide.putEnumerated(idOrnt, idOrnt, idVrtc);
        var idPstn = charIDToTypeID("Pstn");
        var idPxl = charIDToTypeID("#Pxl");
        descGuide.putUnitDouble(idPstn, idPxl, xPosition);
        var idGd = charIDToTypeID("Gd  ");
        desc.putObject(idNw, idGd, descGuide);
        executeAction(idMk, desc, DialogModes.NO);
    } catch(e) {
        writeLog("Error creating vertical guide: " + e, "CRITICAL");
    }
}


/**
 * Fonction pour trouver un calque par son nom dans un groupe
 * @param {Object} layerSet - Objet contenant les calques
 * @param {string} layerName - Nom du calque à trouver
 * @returns {Object|null} - Objet contenant le calque ou null en cas d'erreur
 */
function findLayerByName(layerSet, layerName) {
    try {
        // Essayer de trouver directement dans les calques d'art
        if (layerSet.artLayers) {
            for (var i = 0; i < layerSet.artLayers.length; i++) {
                if (layerSet.artLayers[i].name === layerName) {
                    return layerSet.artLayers[i];
                }
            }
        }
        
        // Essayer de trouver dans les sous-groupes
        if (layerSet.layerSets) {
            for (var j = 0; j < layerSet.layerSets.length; j++) {
                if (layerSet.layerSets[j].name === layerName) {
                    return layerSet.layerSets[j];
                }
                
                // Recherche récursive dans les sous-groupes
                var foundLayer = findLayerByName(layerSet.layerSets[j], layerName);
                if (foundLayer) {
                    return foundLayer;
                }
            }
        }
        
        // Si on arrive ici, le calque n'a pas été trouvé
        writeLog("Layer '" + layerName + "' not found in the group", "DEBUG");
        return null;
    } catch (e) {
        writeLog("ERROR searching for layer '" + layerName + "': " + e);
        return null;
    }
}

/**
 * Fonction pour trouver ou créer un groupe
 * @param {Object} parentGroup - Objet parent contenant les groupes
 * @param {string} groupName - Nom du groupe à trouver ou créer
 * @returns {Object} - Objet contenant le groupe trouvé ou créé
 */
function findOrCreateGroup(parentGroup, groupName) {
    try {
        // Essayer de trouver le groupe existant
        return parentGroup.layerSets.getByName(groupName);
    } catch (e) {
        // Si le groupe n'existe pas, le créer
        var newGroup = parentGroup.layerSets.add();
        newGroup.name = groupName;
        return newGroup;
    }
}

/**
 * Fonction pour lire les métadonnées du fichier .board
 * @param {string} boardPath - Chemin du fichier .board
 * @returns {Object|null} - Objet contenant les métadonnées ou null en cas d'erreur
 */
function readBoardMetadata(boardPath) {
    try {
        writeLog("====== START readBoardMetadata ======", "DEBUG");
        writeLog("Reading metadata from file: " + boardPath, "DEBUG");
        
        // Vérifier si le fichier existe
        if (!fileExists(boardPath)) {
            writeLog("ERROR: The .board file does not exist: " + boardPath, "ERROR");
            writeLog("====== END readBoardMetadata (error) ======", "ERROR");
            return null;
        }
        
        // Lire le contenu du fichier
        var content = readFile(boardPath);
        if (!content) {
            writeLog("ERROR: Unable to read .board file: " + boardPath, "ERROR");
            writeLog("====== END readBoardMetadata (error) ======", "ERROR");
            return null;
        }
        
        // Séparer le contenu en lignes
        var lines = content.split("\n");
        var metadata = {};
        
        // Parcourir les lignes pour extraire les métadonnées (lignes commençant par #)
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            // Supprimer les espaces au début et à la fin sans utiliser trim()
            while (line.charAt(0) === " " || line.charAt(0) === "\t") {
                line = line.substring(1);
            }
            while (line.charAt(line.length - 1) === " " || line.charAt(line.length - 1) === "\t") {
                line = line.substring(0, line.length - 1);
            }
            
            // Vérifier si la ligne est une métadonnée
            if (line.charAt(0) === "#") {
                // Extraire la clé et la valeur
                var parts = line.substring(1).split("=");
                if (parts.length >= 2) {
                    var key = parts[0];
                    // Supprimer les espaces au début et à la fin de la clé
                    while (key.charAt(0) === " " || key.charAt(0) === "\t") {
                        key = key.substring(1);
                    }
                    while (key.charAt(key.length - 1) === " " || key.charAt(key.length - 1) === "\t") {
                        key = key.substring(0, key.length - 1);
                    }
                    
                    var value = parts.slice(1).join("="); // Gérer les valeurs contenant des =
                    // Supprimer les espaces au début et à la fin de la valeur
                    while (value.charAt(0) === " " || value.charAt(0) === "\t") {
                        value = value.substring(1);
                    }
                    while (value.charAt(value.length - 1) === " " || value.charAt(value.length - 1) === "\t") {
                        value = value.substring(0, value.length - 1);
                    }
                    
                    // Convertir les valeurs numériques
                    if (!isNaN(parseFloat(value)) && isFinite(value)) {
                        value = parseFloat(value);
                    }
                    
                    metadata[key] = value;
                    writeLog("Metadata found: " + key + " = " + value);
                }
            }
        }
        
        writeLog("Total number of metadata found: " + countObjectProperties(metadata), "DEBUG");
        writeLog("====== END readBoardMetadata ======", "DEBUG");
        return metadata;
    } catch (e) {
        writeLog("Error reading metadata from .board file: " + e, "ERROR");
        writeLog("====== END readBoardMetadata (error) ======", "ERROR");
        return null;
    }
}

/**
 * Fonction pour mettre à jour le fichier .board avec les nouvelles coordonnées
 * @param {Object} bounds - Objet contenant les coordonnées du rectangle
 * @param {string} boardPath - Chemin du fichier .board
 * @param {number} newCellIndex - Index de la cellule à mettre à jour
 */
function updateBoardFileHorizontally(bounds, boardPath, newCellIndex) {
    try {
        // Formater les coordonnées
        var coordinateString = formatCoordinates(bounds);
        
        // Ajouter l'identifiant de cellule au début
        coordinateString = newCellIndex + "," + coordinateString;
        
        // Lire le contenu actuel du fichier
        var file = new File(boardPath);
        file.open("r");
        var content = file.read();
        file.close();
        
        // Diviser en lignes
        var lines = content.split("\n");
        
        // Séparer les métadonnées des coordonnées
        var metadataLines = [];
        var coordinateLines = [];
        
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].replace(/^\s+|\s+$/g, ""); // Équivalent de trim()
            if (line === "") continue; // Ignorer les lignes vides
            
            if (line.indexOf("#") === 0) {
                // C'est une ligne de métadonnées
                metadataLines.push(line);
            } else {
                // C'est une ligne de coordonnées
                coordinateLines.push(line);
            }
        }
        
        // Ajouter la nouvelle ligne de coordonnées
        coordinateLines.push(coordinateString);
        
        // Reconstruire le contenu du fichier avec les métadonnées en premier
        var newContent = metadataLines.join("\n");
        if (metadataLines.length > 0 && coordinateLines.length > 0) {
            newContent += "\n"; // Ajouter une ligne vide entre les métadonnées et les coordonnées
        }
        newContent += coordinateLines.join("\n");
        
        // Réécrire le fichier
        file = new File(boardPath);
        file.open("w");
        file.write(newContent);
        file.close();
        
        writeLog("New cell added to .board file: " + coordinateString, "DEBUG");
        writeLog("Metadata preserved: " + metadataLines.length + " lines", "DEBUG");
        
    } catch (e) {
        writeLog("Error updating .board file: " + e, "ERROR");
    }
}

/**
 * Fonction pour sauvegarder les coordonnées d'une cellule dans le fichier .board
 * @param {Object} bounds - Objet contenant les coordonnées du rectangle
 * @param {string} boardPath - Chemin du fichier .board
 * @param {number} newCellIndex - Index de la cellule à sauvegarder
 * @param {boolean} needsReorganization - Indique si une réorganisation est nécessaire
 */
function saveCellCoordinates(bounds, boardPath, newCellIndex, needsReorganization) {
    try {
        writeLog("====== START saveCellCoordinates ======", "DEBUG");
        writeLog("Saving coordinates in: " + boardPath, "DEBUG");
        
        // Récupérer les valeurs de dropZone et layoutWidth depuis les préférences
        var preferences = readPreferencesFromPlist();
        var dropZone = false;
        var layoutWidth = 0;
        
        if (preferences) {
            dropZone = getPreferenceValue(preferences, "dropZone", false);
            layoutWidth = getPreferenceValue(preferences, "layoutWidth", 0);
            writeLog("Values from preferences - dropZone: " + dropZone + ", layoutWidth: " + layoutWidth, "DEBUG");
        }
        
        // Ajuster les coordonnées si dropZone est active
        if (dropZone === true) {
            // Extraire les points du rectangle
            var minX = bounds.minX;
            var maxX = bounds.maxX;
            var minY = bounds.minY;
            var maxY = bounds.maxY;
            
            // Si les coordonnées X dépassent layoutWidth, les ajuster
            if (maxX > layoutWidth && layoutWidth > 0) {
                writeLog("Adjusting X coordinates to respect layoutWidth: " + layoutWidth, "DEBUG");
                maxX = layoutWidth;
                bounds.maxX = layoutWidth;
            }
        }
        
        // Obtenir le prochain index de cellule si non fourni
        if (typeof newCellIndex === 'undefined' || newCellIndex === null) {
            newCellIndex = getNextCellIndex(boardPath);
            if (newCellIndex === -1) {
            writeLog("ERROR: Impossible to get the next cell index", "ERROR");
            writeLog("====== END saveCellCoordinates (error) ======", "ERROR");
            return false;
            }
        }
        
        writeLog("Using cell index: " + newCellIndex);
        
        // Formater les coordonnées
        var coordinateString = formatCoordinates(bounds);
        if (!coordinateString) {
            writeLog("ERROR: Impossible to format coordinates", "ERROR");
            writeLog("====== END saveCellCoordinates (error) ======", "ERROR");
            return false;
        }
        
        // Ajouter l'indice de la cellule au début de la ligne
        coordinateString = newCellIndex + "," + coordinateString;
        writeLog("Formatted coordinates with cell index: " + coordinateString, "DEBUG");
        
        // Écrire dans le fichier
        var boardFile = new File(boardPath);
        if (!boardFile.exists) {
            writeLog("ERROR: .board file does not exist: " + boardPath, "ERROR");
            writeLog("====== END saveCellCoordinates (error) ======", "ERROR");
            return false;
        }
        
        boardFile.open("a");
        boardFile.writeln(coordinateString);
        boardFile.close();
        
        writeLog("Coordinates saved successfully: " + coordinateString, "DEBUG");    
        
        // Réorganiser le fichier .board si nécessaire (pour les extensions horizontales ou alternées)
        if (needsReorganization === true) {
            writeLog("Reorganization requested after saving coordinates", "DEBUG");
            reorganizeBoardFile(boardPath);
        }
        
        writeLog("====== END saveCellCoordinates ======", "DEBUG");
        return true;
    } catch (e) {
        writeLog("Error saving coordinates: " + e, "ERROR");
        writeLog("====== END saveCellCoordinates (error) ======", "ERROR");
        return false;
    }
}

/**
 * Fonction pour obtenir le prochain index de cellule disponible
 * @param {string} boardPath - Chemin du fichier .board
 * @returns {number} - Index de la cellule suivante ou -1 en cas d'erreur
 */
function getNextCellIndex(boardPath) {
    try {
        writeLog("====== START getNextCellIndex ======", "DEBUG");
        writeLog("Searching for the next cell index in: " + boardPath, "DEBUG");
        
        // Vérifier si le fichier existe
        if (!fileExists(boardPath)) {
            writeLog("ERROR: .board file does not exist: " + boardPath, "ERROR");
            writeLog("====== END getNextCellIndex (error) ======", "ERROR");
            return -1;
        }
        
        // Lire le contenu du fichier
        var content = readFile(boardPath);
        if (!content) {
            writeLog("ERROR: Impossible to read .board file: " + boardPath, "ERROR");
            writeLog("====== END getNextCellIndex (error) ======", "ERROR");
            return -1;
        }
        
        // Séparer le contenu en lignes
        var lines = content.split("\n");
        
        // Compter les lignes qui ne sont pas des métadonnées (ne commençant pas par #)
        var cellCount = 0;
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            // Supprimer les espaces au début et à la fin sans utiliser trim()
            while (line.charAt(0) === " " || line.charAt(0) === "\t") {
                line = line.substring(1);
            }
            
            // Si la ligne n'est pas vide et ne commence pas par #, c'est une ligne de coordonnées
            if (line.length > 0 && line.charAt(0) !== "#") {
                cellCount++;
            }
        }
        
        writeLog("Number of cells found: " + cellCount, "DEBUG");
        writeLog("Next cell index: " + (cellCount + 1), "DEBUG");
        writeLog("====== END getNextCellIndex ======", "DEBUG");
        return cellCount + 1;
    } catch (e) {
        writeLog("Error searching for the next cell index: " + e, "ERROR");
        writeLog("====== END getNextCellIndex (error) ======", "ERROR");
        return -1;
    }
}

/**
 * Fonction pour formater les coordonnées en chaîne
 * @param {Object} bounds - Objet contenant les coordonnées du rectangle
 * @returns {string|null} - Chaîne de coordonnées formatées ou null en cas d'erreur
 */
function formatCoordinates(bounds) {
    try {
        writeLog("====== START formatCoordinates ======", "DEBUG");
        
        // Vérifier que bounds est un objet valide
        if (!bounds || typeof bounds !== "object") {
            writeLog("ERROR: bounds is not a valid object", "ERROR");
            writeLog("====== END formatCoordinates (error) ======", "ERROR");
            return null;
        }
        
        // Extraire les coordonnées
        var minX = bounds.minX;
        var maxX = bounds.maxX;
        var minY = bounds.minY;
        var maxY = bounds.maxY;
        
        // Vérifier que les coordonnées sont valides
        if (isNaN(minX) || isNaN(maxX) || isNaN(minY) || isNaN(maxY)) {
            writeLog("ERROR: Invalid coordinates - minX: " + minX + ", maxX: " + maxX + ", minY: " + minY + ", maxY: " + maxY, "ERROR");
            writeLog("====== END formatCoordinates (error) ======", "ERROR");
            return null;
        }
        
        // Calculer les coordonnées des 4 coins du rectangle
        var topLeft = [minX, minY];
        var bottomLeft = [minX, maxY];
        var bottomRight = [maxX, maxY];
        var topRight = [maxX, minY];
        
        // Formater les coordonnées en chaîne de caractères
        var coordinateString = topLeft[0] + "," + topLeft[1] + "," +
                               bottomLeft[0] + "," + bottomLeft[1] + "," +
                               bottomRight[0] + "," + bottomRight[1] + "," +
                               topRight[0] + "," + topRight[1];
        
        writeLog("Formatted coordinates: " + coordinateString, "DEBUG");
        writeLog("====== END formatCoordinates ======", "DEBUG");
        return coordinateString;
    } catch (e) {
        writeLog("Error formatting coordinates: " + e, "ERROR");
        writeLog("====== END formatCoordinates (error) ======", "ERROR");
        return null;
    }
}

/**
 * Fonction pour sauvegarder le document Photoshop
 * @param {string} psbPath - Chemin du fichier .psb
 * @returns {boolean} - Vrai si le document a été sauvegardé, faux sinon
 */
function savePS(psbPath) {
    try {
        writeLog("====== START savePS ======", "DEBUG");
        writeLog("Saving document: " + psbPath, "DEBUG");
        
        // Vérifier si le document est ouvert
        if (app.documents.length === 0) {
            writeLog("No document open", "DEBUG");
            return false;
        }
        
        // Référence au document actif
        var doc = app.activeDocument;
        
        // Sauvegarder le document
        try {
            writeLog("Saving document", "DEBUG");
            doc.save();
            writeLog("Document saved successfully", "DEBUG");
            return true;
        } catch (e) {
            writeLog("ERROR during saving: " + e, "ERROR");
            
            // Méthode alternative si la sauvegarde standard échoue
            try {
                writeLog("Alternative saving attempt", "DEBUG");
                
                var saveDesc = new ActionDescriptor();
                var asCopy = new ActionDescriptor();
                asCopy.putBoolean(stringIDToTypeID("maximizeCompatibility"), true);
                saveDesc.putObject(charIDToTypeID("As  "), charIDToTypeID("Pht8"), asCopy);
                saveDesc.putPath(charIDToTypeID("In  "), new File(psbPath));
                saveDesc.putBoolean(charIDToTypeID("LwCs"), true);
                executeAction(charIDToTypeID("save"), saveDesc, DialogModes.NO);
                
                writeLog("Document saved successfully (alternative method)", "DEBUG");
                return true;
            } catch (e2) {
                writeLog("ERROR with alternative method: " + e2, "ERROR");
                return false;
            }
        }
    } catch (e) {
        writeLog("CRITICAL ERROR in savePS: " + e, "ERROR");
        writeLog("====== END savePS (error) ======", "ERROR");
        return false;
    }
}

/**
 * Fonction pour fermer le document Photoshop
 * @param {string} psbPath - Chemin du fichier .psb
 * @returns {boolean} - Vrai si le document a été fermé, faux sinon
 */
function closePS(psbPath) {
    try {
        writeLog("====== START closePS ======", "DEBUG");
        writeLog("Closing document: " + psbPath);
        
        // Vérifier si le document est ouvert
        if (app.documents.length === 0) {
            writeLog("No document open", "DEBUG");
            return false;
        }
        
        // Référence au document actif
        var doc = app.activeDocument;
        
        // Fermer le document sans sauvegarder
        try {
            writeLog("Closing document without saving", "DEBUG");
            doc.close(SaveOptions.DONOTSAVECHANGES);
            writeLog("Document closed successfully", "DEBUG");
            return true;
        } catch (e) {
            writeLog("ERROR during closing: " + e, "ERROR");
            return false;
        }
    } catch (e) {
        writeLog("CRITICAL ERROR in closePS: " + e, "ERROR");
        writeLog("====== END closePS (error) ======", "ERROR");
        return false;
    }
}

/**
 * Fonction pour écrire un rapport de traitement
 * @param {Array} results - Tableau contenant les résultats de traitement
 * @returns {boolean} - Vrai si le rapport a été écrit, faux sinon
 */
function writeProcessingReport(results) {
    try {
        writeLog("====== START writeProcessingReport ======", "DEBUG");
        
        // Obtenir le chemin du document actif s'il existe
        var reportPath = "";
        
        if (app.documents.length > 0) {
            try {
                var docPath = app.activeDocument.path.fsName;
                var boardFolderPath = docPath + "/.board";
                
                // Créer le dossier .board s'il n'existe pas
                var boardFolder = new Folder(boardFolderPath);
                if (!boardFolder.exists) {
                    boardFolder.create();
                }
                
                reportPath = boardFolderPath + "/processing_report.txt";
            } catch (e) {
                writeLog("ERROR accessing document folder: " + e, "ERROR");
            }
        }
        
        // Si le chemin n'est pas défini et qu'on a un dossier global, l'utiliser
        if (!reportPath && globalDestFolder) {
            var globalBoardFolder = new Folder(globalDestFolder + "/.board");
            if (!globalBoardFolder.exists) {
                globalBoardFolder.create();
            }
            reportPath = globalBoardFolder.fsName + "/processing_report.txt";
        }
        
        // Si toujours pas de chemin, utiliser un emplacement de secours
        if (!reportPath) {
            var tempPath = Folder.temp.fsName;
            reportPath = tempPath + "/board_processing_report.txt";
        }
        
        writeLog("Writing report to: " + reportPath, "DEBUG");
        
        // Ouvrir le fichier pour écriture
        var reportFile = new File(reportPath);
        reportFile.open("w");
        
        // Écrire l'en-tête du rapport
        var now = new Date();
        var dateTimeStr = now.getFullYear() + "-" + 
                        padZero(now.getMonth() + 1) + "-" + 
                        padZero(now.getDate()) + " " +
                        padZero(now.getHours()) + ":" + 
                        padZero(now.getMinutes()) + ":" + 
                        padZero(now.getSeconds());
                        
        reportFile.writeln("PROCESSING REPORT - " + dateTimeStr);
        reportFile.writeln("========================================");
        reportFile.writeln("Number of files processed: " + results.length);
        reportFile.writeln("========================================");
        reportFile.writeln("");
        
        // Calculer le nombre de succès et d'échecs
        var successCount = 0;
        var failCount = 0;
        
        for (var i = 0; i < results.length; i++) {
            if (results[i].success) {
                successCount++;
            } else {
                failCount++;
            }
        }
        
        reportFile.writeln("Success: " + successCount);
        reportFile.writeln("Failures: " + failCount);
        reportFile.writeln("");
        reportFile.writeln("DETAILS:");
        reportFile.writeln("========================================");
        
        // Écrire les détails pour chaque fichier
        for (var i = 0; i < results.length; i++) {
            var result = results[i];
            reportFile.writeln("File " + (i+1) + ": " + result.file);
            reportFile.writeln("Status: " + (result.success ? "Success" : "Failure"));
            if (result.executionTime) {
                reportFile.writeln("Execution time: " + result.executionTime + " ms");
            }
            reportFile.writeln("----------------------------------------");
        }
        
        // Fermer le fichier
        reportFile.close();
        
        writeLog("Report written successfully", "DEBUG");
        writeLog("====== END writeProcessingReport ======", "DEBUG");
        return true;
    } catch (e) {
        writeLog("ERROR during report writing: " + e, "ERROR");
        writeLog("====== END writeProcessingReport (error) ======", "ERROR");
        return false;
    }
}

/**
 * Fonction utilitaire pour ajouter des zéros devant un nombre
 * @param {number} num - Le nombre à modifier
 * @returns {string} - Le nombre avec des zéros devant s'il est inférieur à 10
 */
function padZero(num) {
    return (num < 10) ? "0" + num : num.toString();
}

/**
 * Fonction utilitaire pour vérifier si un fichier existe
 * @param {string} filePath - Chemin du fichier à vérifier
 * @returns {boolean} - Vrai si le fichier existe, faux sinon
 */
function fileExists(filePath) {
    if (!filePath) return false;
    
    // Essayer avec le chemin tel quel
    var file = new File(filePath);
    if (file.exists) return true;
    
    // Essayer avec les %20 remplacés par des espaces
    var pathWithSpaces = filePath.replace(/%20/g, " ");
    if (pathWithSpaces !== filePath) {
        file = new File(pathWithSpaces);
        if (file.exists) return true;
    }
    
    // Essayer avec les espaces supprimés
    var pathNoSpaces = filePath.replace(/ /g, "");
    if (pathNoSpaces !== filePath) {
        file = new File(pathNoSpaces);
        if (file.exists) return true;
    }
    
    // Essayer avec les espaces remplacés par %20
    var pathWithPercent20 = filePath.replace(/ /g, "%20");
    if (pathWithPercent20 !== filePath) {
        file = new File(pathWithPercent20);
        if (file.exists) return true;
    }
    
    return false;
}

/**
 * Fonction utilitaire pour lire le contenu d'un fichier
 * @param {string} filePath - Chemin du fichier à lire
 * @returns {string|null} - Contenu du fichier ou null en cas d'erreur
 */
function readFile(filePath) {
    try {
        if (!fileExists(filePath)) {
            writeLog("ERROR: File does not exist: " + filePath, "ERROR");
            return null;
        }
        
        var file = new File(filePath);
        file.open("r");
        var content = file.read();
        file.close();
        return content;
    } catch (e) {
        writeLog("ERROR reading file: " + e, "ERROR");
        return null;
    }
}

/**
 * Fonction pour trouver l'index d'une valeur dans un tableau
 * @param {Array} array - Le tableau dans lequel chercher
 * @param {number} value - La valeur à trouver
 * @returns {number} - L'index de la valeur, ou -1 si non trouvé
 */
function arrayIndexOf(array, value) {
    for (var i = 0; i < array.length; i++) {
        if (Math.abs(array[i] - value) < 0.001) { // Utiliser une tolérance pour les comparaisons de nombres à virgule flottante
            return i;
        }
    }
    return -1;
}

/**
 * Vérifie si une variable est un tableau
 * @param {any} arr - Variable à tester
 * @returns {boolean} - Vrai si c'est un tableau
 */
function isArray(arr) {
    try {
        // En ExtendScript, on peut vérifier si c'est un tableau en testant la propriété length
        // et en vérifiant si l'objet a une méthode push
        return arr !== null && 
               typeof arr === 'object' && 
               'length' in arr && 
               typeof arr.length === 'number' &&
               typeof arr.push === 'function';
    } catch (e) {
        return false;
    }
}

/**
 * Détermine l'orientation d'une image
 * @param {string} filePath - Chemin du fichier image
 * @returns {string} - "Portrait" ou "Landscape"
 */
function getImageOrientation(filePath) {
    try {
        var imageFile = new File(filePath);
        if (!imageFile.exists) {
            writeLog("Image file does not exist: " + filePath, "ERROR");
            return "Portrait"; // Valeur par défaut
        }

        // Ouvrir temporairement l'image pour obtenir ses dimensions
        var tempDoc = app.open(imageFile);
        var width = tempDoc.width.value;
        var height = tempDoc.height.value;
        tempDoc.close(SaveOptions.DONOTSAVECHANGES);

        return width > height ? "Landscape" : "Portrait";
    } catch (e) {
        writeLog("Error getting image orientation: " + e, "ERROR");
        return "Portrait"; // Valeur par défaut en cas d'erreur
    }
}

/**
 * Fonction pour sauvegarder une valeur de préférence dans le fichier plist
 * @param {string} key - Clé de la préférence
 * @param {string|number|boolean} value - Valeur à sauvegarder
 * @returns {boolean} - Vrai si la sauvegarde a réussi, faux sinon
 */
function savePreferenceValue(key, value) {
    try {
        // Liste des emplacements potentiels pour le fichier plist
        var userHome = Folder.userData.parent.parent;
        var possiblePaths = [
            // Emplacement standard
            userHome + "/Library/Preferences/Board/com.dityan.Board.plist",
        ];
        
        // Vérifier chaque chemin possible
        var plistFile = null;
        var foundPath = "";
        
        for (var i = 0; i < possiblePaths.length; i++) {
            var testFile = new File(possiblePaths[i]);
            if (testFile.exists) {
                plistFile = testFile;
                foundPath = possiblePaths[i];
                writeLog("Fichier plist trouvé à: " + foundPath, "DEBUG");
                break;
            }
        }
        
        if (!plistFile) {
            writeLog("ERROR: No plist file found for saving preference", "ERROR");
            return false;
        }
        
        // Lire le contenu actuel du fichier plist
        plistFile.open("r");
        var content = plistFile.read();
        plistFile.close();
        
        // Vérifier si la clé existe déjà
        var keyRegex = new RegExp("<key>" + key + "</key>\\s*<(string|real|integer|true|false)>(.*?)</\\1>", "g");
        var boolKeyRegex = new RegExp("<key>" + key + "</key>\\s*<(true|false)/>", "g");
        
        var newValue;
        if (typeof value === "string") {
            newValue = "<key>" + key + "</key>\n\t<string>" + value + "</string>";
        } else if (typeof value === "number") {
            if (Math.floor(value) === value) {
                newValue = "<key>" + key + "</key>\n\t<integer>" + value + "</integer>";
            } else {
                newValue = "<key>" + key + "</key>\n\t<real>" + value + "</real>";
            }
        } else if (typeof value === "boolean") {
            newValue = "<key>" + key + "</key>\n\t<" + value + "/>";
        } else {
            writeLog("ERROR: Unsupported value type for plist: " + typeof value, "ERROR");
            return false;
        }
        
        var modified = false;
        
        // Remplacer la valeur existante si elle existe
        if (keyRegex.test(content)) {
            content = content.replace(keyRegex, newValue);
            modified = true;
        } else if (boolKeyRegex.test(content)) {
            content = content.replace(boolKeyRegex, newValue);
            modified = true;
        }
        
        // Si la clé n'existe pas, l'ajouter avant la fermeture du dictionnaire
        if (!modified) {
            content = content.replace("</dict>", newValue + "\n</dict>");
        }
        
        // Écrire le contenu modifié dans le fichier
        plistFile.open("w");
        plistFile.write(content);
        plistFile.close();
        
        writeLog("Preference saved: " + key + " = " + value, "DEBUG");
        return true;
    } catch (e) {
        writeLog("ERROR saving preference: " + e, "ERROR");
        return false;
    }
}

/**
 * Réorganise les cellules dans le fichier .board en fonction de leur position spatiale
 * pour maintenir une structure logique (gauche à droite, haut en bas)
 * @param {string} boardPath - Chemin vers le fichier .board
 * @return {boolean} - true si la réorganisation a réussi, false sinon
 */
function reorganizeBoardFile(boardPath) {
    try {
        writeLog("Reorganizing board file to maintain logical structure...", "DEBUG");
        
        // Vérifier que le fichier existe
        if (!fileExists(boardPath)) {
            writeLog("Board file does not exist: " + boardPath, "ERROR");
            return false;
        }
        
        // Lire le contenu complet du fichier .board
        var fileContent = readFile(boardPath);
        if (!fileContent) {
            writeLog("Could not read board file for reorganization", "ERROR");
            return false;
        }
        
        writeLog("Board file content read successfully, length: " + fileContent.length, "DEBUG");
        
        // Extraire les lignes qui sont des métadonnées (commençant par #)
        var lines = fileContent.split("\n");
        writeLog("Number of lines in board file: " + lines.length, "DEBUG");
        
        var metadataLines = [];
        var cellLines = [];
        
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].replace(/^\s+|\s+$/g, ""); // Équivalent de trim()
            if (line.length === 0) continue;
            
            if (line.charAt(0) === "#") {
                metadataLines.push(line);
            } else {
                cellLines.push(line);
            }
        }
        
        writeLog("Metadata lines: " + metadataLines.length + ", Cell lines: " + cellLines.length, "DEBUG");
        
        // Si aucune cellule trouvée, retourner
        if (cellLines.length === 0) {
            writeLog("No cell coordinates found in board file", "WARNING");
            return false;
        }
        
        // Extraire imgMaxHeight des métadonnées pour le calcul de tolérance
        var imgMaxHeight = 1000; // Valeur par défaut
        for (var i = 0; i < metadataLines.length; i++) {
            if (metadataLines[i].indexOf("#imgMaxHeight=") === 0) {
                imgMaxHeight = parseFloat(metadataLines[i].substr(14));
                break;
            }
        }
        
        writeLog("Using imgMaxHeight: " + imgMaxHeight + " for tolerance calculation", "DEBUG");
        
        // Convertir les lignes de cellules en objets
        var cells = [];
        for (var i = 0; i < cellLines.length; i++) {
            var parts = cellLines[i].split(",");
            if (parts.length >= 9) {
                try {
                    var cellIndex = parseInt(parts[0]);
                    var topLeftX = parseFloat(parts[1]);
                    var topLeftY = parseFloat(parts[2]);
                    var bottomLeftX = parseFloat(parts[3]);
                    var bottomLeftY = parseFloat(parts[4]);
                    var bottomRightX = parseFloat(parts[5]);
                    var bottomRightY = parseFloat(parts[6]);
                    var topRightX = parseFloat(parts[7]);
                    var topRightY = parseFloat(parts[8]);
                    
                    // Calculer le centre de la cellule
                    var centerX = (topLeftX + bottomRightX) / 2;
                    var centerY = (topLeftY + bottomRightY) / 2;
                    
                    cells.push({
                        index: cellIndex,
                        coordinates: cellLines[i],
                        centerX: centerX,
                        centerY: centerY
                    });
                    
                    writeLog("Processed cell " + cellIndex + " at center: " + centerX + "," + centerY, "DEBUG");
                } catch (parseError) {
                    writeLog("Error parsing cell line: " + cellLines[i] + " - " + parseError, "ERROR");
                }
            } else {
                writeLog("Invalid cell line format: " + cellLines[i], "WARNING");
            }
        }
        
        writeLog("Processed " + cells.length + " cells for reorganization", "DEBUG");
        
        // Trier les cellules: d'abord par Y (sans tolérance), puis par X
        cells.sort(function(a, b) {
            // Trier d'abord par Y
            var yDiff = a.centerY - b.centerY;
            if (Math.abs(yDiff) > 0.1) { // Utiliser une très petite tolérance
                return yDiff;
            }
            // Si même Y, trier par X
            return a.centerX - b.centerX;
        });
        
        writeLog("Cells sorted by position (Y then X)", "DEBUG");
        
        // Reconstruire le fichier .board avec les cellules réorganisées
        var newFileContent = "";
        
        // Ajouter les métadonnées en premier
        for (var i = 0; i < metadataLines.length; i++) {
            newFileContent += metadataLines[i] + "\n";
        }
        
        // Ajouter les cellules dans le nouvel ordre
        for (var i = 0; i < cells.length; i++) {
            try {
                // Extraire les parties de la ligne
                var parts = cells[i].coordinates.split(",");
                // Remplacer l'index de la cellule par le nouvel index (i+1)
                parts[0] = (i + 1).toString();
                // Reconstruire la ligne
                newFileContent += parts.join(",") + "\n";
                
                writeLog("Reordered cell" + (i+1) + " (was cell" + cells[i].index + ")", "DEBUG");
            } catch (reorderError) {
                writeLog("Error reordering cell " + cells[i].index + ": " + reorderError, "ERROR");
            }
        }
        
        // Écrire le fichier .board mis à jour
        try {
            var boardFile = new File(boardPath);
            boardFile.open('w');
            boardFile.write(newFileContent);
            boardFile.close();
            
            writeLog("Board file reorganized successfully", "INFO");
            return true;
        } catch (writeError) {
            writeLog("Error writing reorganized board file: " + writeError, "ERROR");
            return false;
        }
    } catch (e) {
        writeLog("Error reorganizing board file: " + e, "ERROR");
        return false;
    }
}

/**
 * Fonction pour normaliser les chemins de fichiers (gestion des espaces)
 * @param {string} path - Chemin de fichier
 * @returns {string} - Chemin de fichier normalisé
 */
function normalizePath(path) {
    if (!path) return path;
    
    // Tableau pour stocker toutes les variantes de chemins à essayer
    var pathVariants = [];
    
    // Ajouter le chemin original en premier
    pathVariants.push(path);
    
    // Variante 1: Remplacer les %20 par des espaces (priorité haute)
    var pathWithSpaces = path.replace(/%20/g, " ");
    if (pathWithSpaces !== path) {
        pathVariants.push(pathWithSpaces);
    }
    
    // Essayer toutes les variantes prioritaires d'abord
    for (var i = 0; i < pathVariants.length; i++) {
        var variant = pathVariants[i];
        var file = new File(variant);
        if (file.exists) {
            writeLog("Found file with priority path variant: " + variant, "DEBUG");
            return variant;
        }
    }
    
    // Si les variantes prioritaires échouent, essayer les autres variantes
    
    // Variante 2: Remplacer les espaces par %20
    var pathWithPercent20 = path.replace(/ /g, "%20");
    if (pathWithPercent20 !== path && !arrayContains(pathVariants, pathWithPercent20)) {
        pathVariants.push(pathWithPercent20);
    }
    
    // Variante 3: Essayer de remplacer les underscores par des espaces
    var pathWithUnderscoresAsSpaces = path.replace(/_/g, " ");
    if (pathWithUnderscoresAsSpaces !== path && !arrayContains(pathVariants, pathWithUnderscoresAsSpaces)) {
        pathVariants.push(pathWithUnderscoresAsSpaces);
    }
    
    // Variante 4: Essayer d'insérer des espaces entre les majuscules consécutives
    var pathWithSpacesBetweenCaps = path.replace(/([A-Z])([A-Z])/g, "$1 $2");
    if (pathWithSpacesBetweenCaps !== path && !arrayContains(pathVariants, pathWithSpacesBetweenCaps)) {
        pathVariants.push(pathWithSpacesBetweenCaps);
    }
    
    // Variante 5 (dernier recours): Supprimer tous les espaces
    var pathNoSpaces = path.replace(/ /g, "");
    if (pathNoSpaces !== path && !arrayContains(pathVariants, pathNoSpaces)) {
        pathVariants.push(pathNoSpaces);
    }
    
    // Essayer toutes les variantes restantes
    for (var j = 2; j < pathVariants.length; j++) {
        var variant = pathVariants[j];
        var file = new File(variant);
        if (file.exists) {
            writeLog("Found file with fallback path variant: " + variant, "DEBUG");
            return variant;
        }
    }
    
    // Si aucune variante n'existe, retourner le chemin original avec espaces si possible
    if (pathWithSpaces !== path) {
        writeLog("No file found, returning path with spaces: " + pathWithSpaces, "DEBUG");
        return pathWithSpaces;
    }
    
    // Sinon, retourner le chemin original
    writeLog("No file found, returning original path: " + path, "DEBUG");
    return path;
}

/**
 * Fonction pour formater le temps en HH:MM:SS
 * @param {number} milliseconds - Millisecondes
 * @returns {string} - Temps formaté
 */
function formatTime(milliseconds) {
    var seconds = Math.floor(milliseconds / 1000);
    var hours = Math.floor(seconds / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    seconds = seconds % 60;
    
    return padZero(hours) + ":" + padZero(minutes) + ":" + padZero(seconds);
}

/**
 * Fonction pour créer et afficher la barre de progression
 * @param {string} title - Titre de la barre de progression
 * @param {number} maxValue - Valeur maximale de la barre de progression
 * @returns {Object} - Objet contenant les textes et la barre secondaire
 */
function createProgressBar(title, maxValue) {
    try {
        // Réinitialiser les variables de temps
        gStartTime = new Date();
        gLastUpdateTime = new Date();
        gProcessedItems = 0;
        gTotalItems = maxValue;
        
        // Créer une fenêtre de dialogue avec fond sombre
        gProgressWindow = new Window("palette", title, undefined, {closeButton: false});
        gProgressWindow.orientation = "column";
        gProgressWindow.alignChildren = ["center", "center"];
        gProgressWindow.spacing = 5; // Ajouter de l'espacement entre les éléments
        gProgressWindow.margins = 16; // Ajouter des marges
        
        // Définir la couleur de fond de la fenêtre
        gProgressWindow.graphics.backgroundColor = gProgressWindow.graphics.newBrush(gProgressWindow.graphics.BrushType.SOLID_COLOR, [0.2, 0.2, 0.2]);
        
        // Créer un groupe pour le texte d'en-tête
        var headerGroup = gProgressWindow.add("group");
        headerGroup.orientation = "row";
        headerGroup.alignChildren = ["left", "center"];
        headerGroup.spacing = 5;
        headerGroup.preferredSize.width = 400;
        headerGroup.margins = [0, 0, 0, 10]; // Ajouter une marge en bas
        
        // Ajouter un texte pour le statut principal
        var headerText = headerGroup.add("statictext", undefined, "Initializing...");
        headerText.preferredSize.width = 400; // Utiliser toute la largeur disponible
        headerText.preferredSize.height = 20; // Définir une hauteur fixe
        headerText.graphics.font = ScriptUI.newFont(headerText.graphics.font.family, "bold", 14);
        headerText.graphics.foregroundColor = headerText.graphics.newPen(headerText.graphics.PenType.SOLID_COLOR, [1, 1, 1], 1);
        
        // Ajouter un texte pour le nom du fichier
        var fileText = gProgressWindow.add("statictext", undefined, "");
        fileText.preferredSize.width = 400;
        fileText.preferredSize.height = 20;
        fileText.graphics.font = ScriptUI.newFont(fileText.graphics.font.family, "bold", 12);
        fileText.graphics.foregroundColor = fileText.graphics.newPen(headerText.graphics.PenType.SOLID_COLOR, [1, 1, 1], 1);
        fileText.justify = "center";

        // Ajouter un texte pour le temps
        var timeText = gProgressWindow.add("statictext", undefined, "");
        timeText.preferredSize.width = 400;
        timeText.preferredSize.height = 20;
        timeText.graphics.font = ScriptUI.newFont(timeText.graphics.font.family, "regular", 12);
        timeText.graphics.foregroundColor = timeText.graphics.newPen(headerText.graphics.PenType.SOLID_COLOR, [1, 1, 1], 1);
        timeText.justify = "center";
        
        // Ajouter la barre de progression
        gProgressBar = gProgressWindow.add("progressbar", undefined, 0, maxValue);
        gProgressBar.preferredSize.width = 400;
        gProgressBar.preferredSize.height = 10;
        gProgressBar.value = 0;
        
        // Créer un groupe pour la ligne de détails
        var detailsGroup = gProgressWindow.add("group");
        detailsGroup.orientation = "row";
        detailsGroup.alignChildren = ["left", "center"];
        detailsGroup.spacing = 10;
        detailsGroup.preferredSize.width = 400;
        
        // Ajouter un texte pour les détails des opérations (ajusté pour laisser de la place à la barre secondaire)
        var detailsText = detailsGroup.add("statictext", undefined, "");
        detailsText.preferredSize.width = 280; // Réduit pour laisser de la place à la barre secondaire
        detailsText.preferredSize.height = 20;
        detailsText.graphics.font = ScriptUI.newFont(detailsText.graphics.font.family, "bold", 11);
        detailsText.graphics.foregroundColor = detailsText.graphics.newPen(headerText.graphics.PenType.SOLID_COLOR, [1, 1, 1], 1);
        
        // Ajouter une barre de progression secondaire
        var secondaryProgressBar = detailsGroup.add("progressbar", undefined, 0, 100);
        secondaryProgressBar.preferredSize.width = 110;
        secondaryProgressBar.preferredSize.height = 3;
        secondaryProgressBar.value = 0;
        
        // Ajouter un bouton d'annulation
        var cancelButton = gProgressWindow.add("button", undefined, "Stop");
        cancelButton.preferredSize.width = 100;
        cancelButton.preferredSize.height = 25;
        cancelButton.margins = [0, 10, 0, 0];
        cancelButton.onClick = function() {
            gProgressCancelled = true;
            gProgressWindow.close();
        };
        
        // Positionner au centre de l'écran
        gProgressWindow.center();
        
        // Afficher la fenêtre
        gProgressWindow.show();
        
        // Retourner un objet avec tous les textes et la barre secondaire
        return {
            headerText: headerText,
            fileText: fileText,
            detailsText: detailsText,
            timeText: timeText,
            secondaryProgressBar: secondaryProgressBar
        };
    } catch (e) {
        writeLog("Error creating progress bar: " + e, "ERROR");
        return null;
    }
}

/**
 * Fonction pour mettre à jour la barre de progression
 * @param {number} value - Valeur de la barre de progression
 * @param {Object} statusObj - Objet contenant les textes et la barre secondaire
 * @param {string} message - Message à afficher
 * @param {string} filename - Nom du fichier
 * @param {string} details - Détails à afficher
 * @param {number} secondaryProgress - Valeur de la barre secondaire
 */
function updateProgressBar(value, statusObj, message, filename, details, secondaryProgress) {
    try {
        if (gProgressWindow && gProgressBar) {
            // Mettre à jour la valeur de la barre de progression si fournie
            if (value !== null) {
                gProgressBar.value = value;
                gProcessedItems = value;
            }
            
            // Mettre à jour le texte d'en-tête uniquement si un nouveau message est fourni
            if (statusObj && statusObj.headerText && message && message.length > 0) {
                statusObj.headerText.text = message;
            }
            
            // Mettre à jour le nom du fichier uniquement si un nouveau nom est fourni
            if (statusObj && statusObj.fileText && filename && filename.length > 0) {
                statusObj.fileText.text = filename;
            }
            
            // Mettre à jour le texte des détails
            if (statusObj && statusObj.detailsText) {
                statusObj.detailsText.text = details || "";
            }
            
            // Gérer la barre de progression secondaire
            if (statusObj && statusObj.secondaryProgressBar) {
                if (secondaryProgress !== undefined) {
                    // Afficher et mettre à jour la barre secondaire
                    statusObj.secondaryProgressBar.visible = true;
                    statusObj.secondaryProgressBar.value = secondaryProgress;
                    // Ajuster la largeur du texte de détails
                    statusObj.detailsText.preferredSize.width = 280;
                } else {
                    // Masquer la barre secondaire et utiliser toute la largeur pour le texte
                    statusObj.secondaryProgressBar.visible = false;
                    statusObj.detailsText.preferredSize.width = 400;
                }
            }
            
            // Calculer et mettre à jour le temps
            if (statusObj && statusObj.timeText) {
                var currentTime = new Date();
                var elapsedTime = currentTime - gStartTime;
                var elapsedStr = formatTime(elapsedTime);
                
                // Calculer le temps estimé restant
                var remainingTime = "calculating...";
                if (gProcessedItems > 0) {
                    var timePerItem = elapsedTime / gProcessedItems;
                    var remainingItems = gTotalItems - gProcessedItems;
                    var estimatedRemainingTime = timePerItem * remainingItems;
                    remainingTime = formatTime(estimatedRemainingTime);
                }
                
                statusObj.timeText.text = "Elapsed: " + elapsedStr + " - Remaining: " + remainingTime;
            }
            
            // Forcer une mise à jour de l'affichage
            gProgressWindow.update();
        }
    } catch (e) {
        writeLog("Error updating progress bar: " + e, "ERROR");
    }
}

/**
 * Fonction pour fermer la barre de progression
 * @returns {void}
 */
function closeProgressBar() {
    try {
        if (gProgressWindow) {
            gProgressWindow.close();
            gProgressWindow = null;
            gProgressBar = null;
            gProgressCancelled = false;
            gStartTime = null;
            gLastUpdateTime = null;
            gProcessedItems = 0;
            gTotalItems = 0;
        }
    } catch (e) {
        writeLog("Error closing progress bar: " + e, "ERROR");
    }
}

/**
 * Fonction pour vérifier si l'opération a été annulée
 * @returns {boolean} - Vrai si l'opération a été annulée, faux sinon
 */
function isProgressCancelled() {
    return gProgressCancelled;
}

/**
 * Fonction pour calculer le temps d'exécution du script en secondes et l'afficher dans les logs
 * @returns {void}
 */
function logExecutionTime() {
    var endTime = new Date().getTime();
    var executionTimeMs = endTime - SCRIPT_START_TIME;
    var executionTimeSec = executionTimeMs / 1000;
    var timePerImage = gProcessedItems > 0 ? executionTimeSec / gProcessedItems : 0;
    writeLog("Script execution time: " + executionTimeSec.toFixed(2) + " seconds (average " + timePerImage.toFixed(2) + " seconds per image)", "INFO");
}

/**
 * Fonction pour délier le masque du calque actif
 * @returns {boolean} - Vrai si le masque a été délié, faux sinon
 */
function unlinkMask() {
    try {
        writeLog("Unlinking mask from layer", "INFO");
        
        var idset = stringIDToTypeID("set");
        var desc = new ActionDescriptor();
        var idnull = stringIDToTypeID("null");
        
        // Référence au calque cible
        var ref = new ActionReference();
        var idlayer = stringIDToTypeID("layer");
        var idordinal = stringIDToTypeID("ordinal");
        var idtargetEnum = stringIDToTypeID("targetEnum");
        ref.putEnumerated(idlayer, idordinal, idtargetEnum);
        
        desc.putReference(idnull, ref);
        
        // Configuration pour délier le masque
        var idto = stringIDToTypeID("to");
        var layerDesc = new ActionDescriptor();
        var iduserMaskLinked = stringIDToTypeID("userMaskLinked");
        layerDesc.putBoolean(iduserMaskLinked, false);
        
        var idlayer = stringIDToTypeID("layer");
        desc.putObject(idto, idlayer, layerDesc);
        
        // Exécuter l'action
        executeAction(idset, desc, DialogModes.NO);
        writeLog("Mask unlinked successfully", "DEBUG");
        
        return true;
    } catch (e) {
        writeLog("ERROR in unlinkMask: " + e, "ERROR");
        return false;
    }
}

/**
 * Fonction pour vérifier si un document est déjà ouvert dans Photoshop
 * @param {string} filePath - Chemin du fichier à vérifier
 * @returns {boolean} - Vrai si le document est ouvert, faux sinon
 */
function isDocumentAlreadyOpen(filePath) {
    try {
        writeLog("Checking if document is already open: " + filePath, "DEBUG");
        if (app.documents.length === 0) {
            writeLog("No documents open", "DEBUG");
            return false;
        }
        
        // Normaliser le chemin pour comparer
        filePath = normalizePath(filePath);
        
        // Vérifier chaque document ouvert
        for (var i = 0; i < app.documents.length; i++) {
            try {
                var doc = app.documents[i];
                // Utiliser doc.fullName pour obtenir le chemin complet
                var docPath = normalizePath(doc.fullName.toString());
                
                writeLog("Comparing paths:", "DEBUG");
                writeLog("- Document path: " + docPath, "DEBUG");
                writeLog("- Target path: " + filePath, "DEBUG");
                
                if (docPath === filePath) {
                    writeLog("Document already open: " + filePath, "INFO");
                    return doc;
                }
            } catch (e) {
                writeLog("Error comparing document path: " + e, "ERROR");
                // Continuer avec le document suivant
            }
        }
        
        writeLog("Document not found among open documents", "DEBUG");
        return false;
    } catch (e) {
        writeLog("Error in isDocumentAlreadyOpen: " + e, "ERROR");
        return false;
    }
}

/**
 * Gestion améliorée du placement d'overlays pour Photoshop
 * @param {string} cellType - Type de cellule ("Single" ou "Spread")
 * @param {number} currentCell - Index de la cellule courante
 * @param {number} cellHeight - Hauteur de la cellule en pixels
 * @param {number} cellWidth - Largeur de la cellule en pixels
 * @param {Array} overlayFiles - Liste des fichiers d'overlay à utiliser
 * @param {Object} options - Options de configuration
 * @param {number} options.totalRows - Nombre total de lignes
 * @param {number} options.totalCols - Nombre total de colonnes
 * @param {string} options.boardPath - Chemin du fichier .board
 * @param {number} options.opacity - Opacité (0-100)
 * @param {string} options.blendMode - Mode de fusion
 * @param {boolean} options.maintainAspectRatio - Maintenir les proportions
 * @return {Object} Informations de placement avec statut de succès
 */
function handleOverlayPlacement(cellType, currentCell, cellHeight, cellWidth, overlayFiles, options) {
    writeLog("handleOverlayPlacement called for cell " + currentCell, "DEBUG");
    
    // Log détaillé des paramètres reçus
    writeLog("Parameters received:", "DEBUG");
    writeLog("- cellType: " + cellType, "DEBUG");
    writeLog("- currentCell: " + currentCell, "DEBUG");
    writeLog("- cellHeight: " + cellHeight, "DEBUG");
    writeLog("- cellWidth: " + cellWidth, "DEBUG");
    writeLog("- overlayFiles: " + (overlayFiles ? overlayFiles.length : "undefined") + " files", "DEBUG");
    writeLog("- options: " + (options ? "present" : "undefined"), "DEBUG");
    
    // Vérification détaillée des paramètres
    if (!cellType) {
        writeLog("Missing cellType parameter", "ERROR");
        return { success: false, error: "Missing cellType" };
    }
    
    if (!overlayFiles) {
        writeLog("Missing overlayFiles parameter", "ERROR");
        return { success: false, error: "Missing overlayFiles" };
    }
    
    if (!isArray(overlayFiles)) {
        writeLog("overlayFiles is not an array", "ERROR");
        return { success: false, error: "overlayFiles must be an array" };
    }
    
    if (overlayFiles.length === 0) {
        writeLog("overlayFiles array is empty", "ERROR");
        return { success: false, error: "No overlay files provided" };
    }

    if (!options) {
        writeLog("Missing options parameter", "ERROR");
        return { success: false, error: "Missing options" };
    }

    // Vérification des options requises
    if (!options.totalRows || !options.totalCols) {
        writeLog("Missing required options - totalRows: " + options.totalRows + ", totalCols: " + options.totalCols, "ERROR");
        return { success: false, error: "Missing required options" };
    }

    try {
        // Vérifier que currentCell est un nombre valide
        if (typeof currentCell !== 'number' || isNaN(currentCell)) {
            writeLog("Invalid cell number: " + currentCell, "ERROR");
            return { success: false, error: "Invalid cell number" };
        }

        // Vérifier que options contient les valeurs nécessaires
        if (!options || !options.totalRows || !options.totalCols) {
            writeLog("Missing required options", "ERROR");
            return { success: false, error: "Missing options" };
        }

        // Calculer la position dans la grille
        var row = Math.ceil(currentCell / options.totalCols);
        var col = ((currentCell - 1) % options.totalCols) + 1;

        writeLog("Cell position calculated - row: " + row + ", col: " + col, "DEBUG");

        // Récupérer l'index du fichier overlay
        var currentIndex = getNextOverlayIndex({
            row: row,
            col: col,
            totalRows: options.totalRows,
            totalCols: options.totalCols
        }, overlayFiles, options.boardPath);

        if (isNaN(currentIndex)) {
            writeLog("Invalid overlay index calculated", "ERROR");
            return { success: false, error: "Invalid overlay index" };
        }

        // Récupérer le fichier actuel
        var currentFile = overlayFiles[currentIndex];
        if (!currentFile) {
            writeLog("No overlay file found at index " + currentIndex, "ERROR");
            return { success: false, error: "No overlay file found" };
        }

        writeLog("Using file: " + currentFile + " (index: " + currentIndex + ") for cell " + currentCell, "DEBUG");

        // Déterminer l'orientation
        var orientation = getImageOrientation(currentFile);
        writeLog("File orientation: " + orientation, "DEBUG");
        
        // Calculer le prochain index pour spread mode si nécessaire
        var nextIndex = (currentIndex + 1) % overlayFiles.length;
        
        // Préparer le résultat
        var result = {
            success: true,
            placement: {
                position: "center",
                filePath: null,
                leftPath: null,
                rightPath: null
            },
            orientation: orientation,
            cellDimensions: {
                width: cellWidth,
                height: cellHeight
            }
        };
        
        // Déterminer le positionnement en fonction du type de cellule et de l'orientation
        if (cellType.toLowerCase() === "spread" && orientation === "Portrait") {
            writeLog("Using split position for portrait in spread cell", "DEBUG");
            result.placement.position = "split";
            result.placement.leftPath = currentFile;
            
            // Pour la partie droite, utiliser le fichier suivant ou le même si un seul fichier
            if (overlayFiles.length > 1) {
                result.placement.rightPath = overlayFiles[nextIndex];
                writeLog("Using different file for right side: " + result.placement.rightPath, "DEBUG");
            } else {
                result.placement.rightPath = currentFile;
                writeLog("Using same file for both sides (only one available)", "DEBUG");
            }
        } else {
            writeLog("Using center position for " + cellType + " cell with " + orientation + " image", "DEBUG");
            result.placement.position = "center";
            result.placement.filePath = currentFile;
        }
        
        return result;
    } catch(e) {
        writeLog("Error in handleOverlayPlacement: " + e, "ERROR");
        return {
            success: false,
            error: String(e)
        };
    }
}

/**
 * Crée les calques d'overlay pour une cellule donnée
 * @param {number} cellLX - Coordonnée X gauche de la cellule
 * @param {number} cellRX - Coordonnée X droite de la cellule
 * @param {number} cellTY - Coordonnée Y haut de la cellule
 * @param {number} cellBY - Coordonnée Y bas de la cellule
 * @param {number} marginMask - Marge à appliquer
 * @param {LayerSet} overlayGroup - Groupe de calques pour les overlays
 * @param {Array} overlayFiles - Liste des fichiers d'overlay
 * @param {Object} options - Options supplémentaires
 * @param {string} options.cellType - Type de cellule ("Single" ou "Spread")
 * @param {number} options.cellNumber - Numéro de la cellule
 * @param {number} options.row - Numéro de ligne
 * @param {number} options.col - Numéro de colonne
 * @param {number} options.totalRows - Nombre total de lignes
 * @param {number} options.totalCols - Nombre total de colonnes
 * @param {string} options.boardPath - Chemin du fichier .board
 */
function createOverlayLayers(cellLX, cellRX, cellTY, cellBY, marginMask, overlayGroup, overlayFiles, options) {
    try {
        // Vérifier les paramètres requis
        if (!overlayGroup || !overlayFiles || overlayFiles.length === 0) {
            writeLog("Missing required parameters for overlay creation", "ERROR");
            return false;
        }

        // Calculer les dimensions de la cellule
        var cellWidth = cellRX - cellLX;
        var cellHeight = cellBY - cellTY;

        // Préparer les options pour handleOverlayPlacement
        var placementOptions = {
            opacity: 100,
            blendMode: "normal",
            maintainAspectRatio: true,
            centerPlacement: true,
            maxResizePercentage: 100,
            useRotation: false,
            rotationAngle: 0,
            boardPath: options.boardPath,
            totalRows: options.totalRows,
            totalCols: options.totalCols
        };

        // Appeler handleOverlayPlacement
        var overlayResult = handleOverlayPlacement(
            options.cellType || "Single",
            options.cellNumber,
            cellHeight,
            cellWidth,
            overlayFiles,
            placementOptions
        );

        if (!overlayResult.success) {
            writeLog("Overlay placement failed: " + overlayResult.error, "ERROR");
            return false;
        }

        // Fonction utilitaire pour placer et configurer un calque d'overlay
        function placeAndConfigureOverlay(filePath, targetX, targetY, maxWidth, maxHeight, layerName) {
            try {
                var overlayLayer = overlayGroup.artLayers.add();
                overlayLayer.name = layerName;
                app.activeDocument.activeLayer = overlayLayer;

                // Placer le fichier
                var idPlc = charIDToTypeID("Plc ");
                var desc = new ActionDescriptor();
                desc.putPath(charIDToTypeID("null"), new File(filePath));
                executeAction(idPlc, desc, DialogModes.NO);

                // Convertir en Smart Object
                var idnewPlacedLayer = stringIDToTypeID("newPlacedLayer");
                executeAction(idnewPlacedLayer, undefined, DialogModes.NO);

                // Obtenir les dimensions initiales
                var placedLayer = app.activeDocument.activeLayer;
                var bounds = placedLayer.bounds;
                var initialWidth = bounds[2].value - bounds[0].value;
                var initialHeight = bounds[3].value - bounds[1].value;

                // Calculer le facteur d'échelle
                var widthRatio = maxWidth / initialWidth;
                var heightRatio = maxHeight / initialHeight;
                var scaleFactor = Math.min(widthRatio, heightRatio) * 100;

                // Redimensionner
                placedLayer.resize(scaleFactor, scaleFactor, AnchorPosition.TOPLEFT);

                // Obtenir les nouvelles dimensions
                var newBounds = placedLayer.bounds;
                var newWidth = newBounds[2].value - newBounds[0].value;
                var newHeight = newBounds[3].value - newBounds[1].value;

                // Calculer la position finale
                var finalX = targetX;
                var finalY = targetY;

                // Centrer si l'image est plus petite que l'espace disponible
                if (newWidth < maxWidth) {
                    finalX += (maxWidth - newWidth) / 2;
                }
                if (newHeight < maxHeight) {
                    finalY += (maxHeight - newHeight) / 2;
                }

                // Déplacer le calque
                var deltaX = finalX - newBounds[0].value;
                var deltaY = finalY - newBounds[1].value;
                placedLayer.translate(deltaX, deltaY);

                return placedLayer;
            } catch(e) {
                writeLog("Error placing overlay: " + e, "ERROR");
                return null;
            }
        }

        if (overlayResult.placement.position === "center") {
            // Placement centré - Utiliser les dimensions complètes de la cellule
            var maxWidth = cellRX - cellLX;  // Ne pas soustraire les marges
            var maxHeight = cellBY - cellTY;  // Ne pas soustraire les marges
            var layerName = "Overlay R" + options.row + "C" + options.col;

            var placedLayer = placeAndConfigureOverlay(
                overlayResult.placement.filePath,
                cellLX,  // Position sans marge
                cellTY,  // Position sans marge
                maxWidth,
                maxHeight,
                layerName
            );

        } else if (overlayResult.placement.position === "split") {
            // Placement divisé pour les spreads - Utiliser la moitié de la cellule
            var halfCellWidth = (cellRX - cellLX) / 2;  // Ne pas soustraire les marges
            var maxHeight = cellBY - cellTY;  // Ne pas soustraire les marges

            // Côté gauche
            var leftLayerName = "Overlay R" + options.row + "C" + options.col + "_L";
            var leftLayer = placeAndConfigureOverlay(
                overlayResult.placement.leftPath,
                cellLX,  // Position sans marge
                cellTY,  // Position sans marge
                halfCellWidth,
                maxHeight,
                leftLayerName
            );

            // Côté droit
            var rightLayerName = "Overlay R" + options.row + "C" + options.col + "_R";
            var rightLayer = placeAndConfigureOverlay(
                overlayResult.placement.rightPath,
                cellLX + halfCellWidth,  // Position sans marge
                cellTY,  // Position sans marge
                halfCellWidth,
                maxHeight,
                rightLayerName
            );

            if (!rightLayer) {
                writeLog("Failed to place right overlay", "ERROR");
                if (leftLayer) leftLayer.remove();
                return false;
            }
        }

        return true;
    } catch(e) {
        writeLog("Error creating overlay layers: " + e, "ERROR");
        return false;
    }
}

/**
 * Lit l'index d'overlay pour une cellule spécifique depuis le fichier .board
 * @param {string} boardPath - Chemin du fichier .board
 * @param {number} row - Numéro de ligne
 * @param {number} col - Numéro de colonne
 * @return {number} Index de l'overlay ou -1 si non trouvé
 */
function readOverlayIndexFromBoard(boardPath, row, col) {
    try {
        var cellKey = "overlay_index_cell_" + row + "_" + col;
        var boardFile = new File(boardPath);
        if (!boardFile.exists) {
            return -1;
        }

        boardFile.open("r");
        var content = boardFile.read();
        boardFile.close();

        var regex = new RegExp("#" + cellKey + "=(\\d+)");
        var match = content.match(regex);

        if (match && match.length > 1) {
            return parseInt(match[1], 10);
        }

        return -1;
    } catch(e) {
        writeLog("Error reading overlay index: " + e, "ERROR");
        return -1;
    }
}

/**
 * Sauvegarde l'index d'overlay pour une cellule dans le fichier .board
 * @param {string} boardPath - Chemin du fichier .board
 * @param {number} row - Numéro de ligne
 * @param {number} col - Numéro de colonne
 * @param {number} index - Index à sauvegarder
 */
function saveOverlayIndexToBoard(boardPath, row, col, index) {
    try {
        var cellKey = "overlay_index_cell_" + row + "_" + col;
        var metadata = {
            overlayIndexes: {}
        };
        metadata.overlayIndexes[cellKey] = index;

        // Utiliser writeMetadataToBoard qui gère la fusion avec les métadonnées existantes
        writeMetadataToBoard(boardPath, metadata);
    } catch(e) {
        writeLog("Error saving overlay index: " + e, "ERROR");
    }
}

/**
 * Détermine le prochain index d'overlay à utiliser
 * @param {Object} cellInfo - Informations sur la cellule
 * @param {Array} overlayFiles - Liste des fichiers d'overlay
 * @param {string} boardPath - Chemin du fichier .board
 * @return {number} Index du fichier à utiliser
 */
function getNextOverlayIndex(cellInfo, overlayFiles, boardPath) {
    try {
        if (!overlayFiles || overlayFiles.length === 0) {
            return 0;
        }

        // Lire l'index actuel
        var currentIndex = readOverlayIndexFromBoard(boardPath, cellInfo.row, cellInfo.col);

        // Si premier usage ou données corrompues
        if (currentIndex < 0 || currentIndex >= overlayFiles.length) {
            // Calculer l'index initial basé sur la position de la cellule
            var cellNumber = (cellInfo.row - 1) * cellInfo.totalCols + (cellInfo.col - 1);
            currentIndex = (cellNumber * 2) % overlayFiles.length;
        } else {
            // Incrémenter l'index pour la rotation
            if (currentIndex % 2 === 0) {
                currentIndex = (currentIndex + 1) % overlayFiles.length;
            } else {
                currentIndex = (currentIndex - 1 + overlayFiles.length) % overlayFiles.length;
            }
        }

        // Sauvegarder le nouvel index
        saveOverlayIndexToBoard(boardPath, cellInfo.row, cellInfo.col, currentIndex);

        return currentIndex;
    } catch(e) {
        writeLog("Error in getNextOverlayIndex: " + e, "ERROR");
        return 0;
    }
}

/**
 * Écrit les métadonnées au début du fichier .board
 * @param {string} boardPath - Chemin vers le fichier .board
 * @param {Object} metadata - Métadonnées à écrire
 */
function writeMetadataToBoard(boardPath, metadata) {
    try {
        // Vérifier si le fichier existe déjà
        var boardFile = new File(boardPath);
        var existingContent = "";
        var existingMetadata = {};
        var overlayIndexes = {};
        var hasExistingMetadata = false;
        
        if (boardFile.exists) {
            // Lire le contenu existant
            boardFile.open("r");
            var allContent = boardFile.read();
            boardFile.close();
            
            // Séparer les métadonnées des coordonnées
            var lines = allContent.split("\n");
            var contentLines = [];
            var metadataLines = [];
            
            for (var i = 0; i < lines.length; i++) {
                if (lines[i].indexOf("#") === 0) {
                    metadataLines.push(lines[i]);
                    hasExistingMetadata = true;
                    
                    // Extraire les métadonnées existantes
                    var parts = lines[i].substring(1).split("=");
                    if (parts.length === 2) {
                        var key = parts[0];
                        var value = parts[1];
                        
                        if (key.indexOf("overlay_index_cell_") === 0) {
                            overlayIndexes[key] = value;
                        } else {
                            existingMetadata[key] = value;
                        }
                    }
                } else {
                    contentLines.push(lines[i]);
                }
            }
            
            existingContent = contentLines.join("\n");
            
            // Supprimer le fichier existant
            boardFile.remove();
        }
        
        // Ouvrir le fichier en mode écriture
        boardFile = new File(boardPath);
        boardFile.open("w");
        
        // Fusionner les métadonnées
        var finalMetadata = {};
        
        // 1. Ajouter les métadonnées existantes
        for (var key in existingMetadata) {
            if (existingMetadata.hasOwnProperty(key)) {
                finalMetadata[key] = existingMetadata[key];
            }
        }
        
        // 2. Ajouter/remplacer par les nouvelles métadonnées
        for (var key in metadata) {
            if (metadata.hasOwnProperty(key)) {
                if (key === "overlayIndexes") {
                    for (var cellKey in metadata.overlayIndexes) {
                        if (metadata.overlayIndexes.hasOwnProperty(cellKey)) {
                            overlayIndexes[cellKey] = metadata.overlayIndexes[cellKey];
                        }
                    }
                } else {
                    finalMetadata[key] = metadata[key];
                }
            }
        }
        
        // Écrire les métadonnées
        for (var key in finalMetadata) {
            if (finalMetadata.hasOwnProperty(key)) {
                var line = "#" + key + "=" + finalMetadata[key];
                boardFile.writeln(line);
            }
        }
        
        // Écrire les index d'overlay
        for (var cellKey in overlayIndexes) {
            if (overlayIndexes.hasOwnProperty(cellKey)) {
                boardFile.writeln("#" + cellKey + "=" + overlayIndexes[cellKey]);
            }
        }
        
        // Écrire le contenu existant
        if (existingContent) {
            boardFile.write(existingContent);
        }
        
        boardFile.close();
        writeLog("Metadata written to board file", "DEBUG");
    } catch(e) {
        writeLog("Error writing metadata to board file: " + e, "ERROR");
    }
}

/**
 * Fonction pour ajuster la vue du document pour voir toute la zone
 * @returns {boolean} - Vrai si l'ajustement a réussi, faux sinon
 */
function fitDocumentOnScreen() {
    try {
        // Forcer l'ajustement de la vue pour voir tout le document
        var idslct = charIDToTypeID("slct");
        var desc = new ActionDescriptor();
        var idnull = charIDToTypeID("null");
        var ref = new ActionReference();
        var idMn = charIDToTypeID("Mn  ");
        var idMnIt = charIDToTypeID("MnIt");
        var idFtOn = charIDToTypeID("FtOn");
        ref.putEnumerated(idMn, idMnIt, idFtOn);
        desc.putReference(idnull, ref);
        executeAction(idslct, desc, DialogModes.NO);
        
        // Forcer un rafraîchissement de l'affichage
        app.refresh();
        
        // Ajouter un petit délai pour s'assurer que l'affichage est mis à jour
        $.sleep(100);
        
        writeLog("Document view adjusted to fit on screen", "DEBUG");
        return true;
    } catch (e) {
        writeLog("Error adjusting document view: " + e, "ERROR");
        return false;
    }
}

/**
 * Fonction pour placer un fichier image dans le document
 * @param {string} filePath - Chemin du fichier image à placer
 * @param {number} imgMaxHeight - Hauteur maximale de l'image
 * @param {number} imgMaxWidth - Largeur maximale de l'image
 * @param {string} cellType - Type de cellule (Single ou Spread)
 * @param {string} orientationImg - Orientation de l'image
 * @param {string} resizeMode - Mode de redimensionnement
 * @param {string} landscapeMode - Mode paysage
 * @param {string} boardPath - Chemin du fichier .board
 * @returns {boolean} - Vrai si le placement a réussi, faux sinon
 */
function placeFile(filePath, imgMaxHeight, imgMaxWidth, cellType, orientationImg, resizeMode, landscapeMode, boardPath) {
    try {
        writeLog("====== START placeFile ======", "INFO");
        writeLog("Placing file: " + filePath, "INFO");
        writeLog("Max dimensions: " + imgMaxWidth + "x" + imgMaxHeight, "INFO");
        writeLog("Cell type: " + cellType + ", Resize mode: " + resizeMode + ", Landscape mode: " + landscapeMode, "INFO");
        
        // Normaliser le chemin du fichier
        filePath = normalizePath(filePath);
        
        // Vérifier que le fichier existe
        var file = new File(filePath);
        if (!file.exists) {
            writeLog("ERROR: File does not exist: " + filePath, "ERROR");
            return null;
        }
        
        // Référence au document actif
        var doc = app.activeDocument;
        
        // Placer le fichier
        try {
            if (resizeMode === "noResize") {
                // En mode "noResize", utiliser une méthode qui préserve la taille originale
                writeLog("Using alternative placement method for 'noResize' mode to preserve original size", "DEBUG");
                var desc = new ActionDescriptor();
                var desc2 = new ActionDescriptor();
                var idPlc = charIDToTypeID("Plc ");
                var idnull = charIDToTypeID("null");
                desc.putPath(idnull, new File(filePath));
                var idFTcs = charIDToTypeID("FTcs");
                var idQCSt = charIDToTypeID("QCSt");
                var idQcsa = charIDToTypeID("Qcsa");
                desc.putEnumerated(idFTcs, idQCSt, idQcsa);
                var idOfst = charIDToTypeID("Ofst");
                desc2.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), 0);
                desc2.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), 0);
                desc.putObject(idOfst, idOfst, desc2);
                executeAction(idPlc, desc, DialogModes.NO);
            } else {
                // Pour les autres modes, utiliser la méthode standard
                writeLog("Using standard placement method for resize modes", "DEBUG");
                var idPlc = charIDToTypeID("Plc ");
                var desc = new ActionDescriptor();
                var idnull = charIDToTypeID("null");
                desc.putPath(idnull, new File(filePath));
                executeAction(idPlc, desc, DialogModes.NO);
            }
            writeLog("Placement successful", "DEBUG");
            
            // Convertir en Smart Object
            writeLog("Converting to Smart Object", "DEBUG");
            var idnewPlacedLayer = stringIDToTypeID("newPlacedLayer");
            executeAction(idnewPlacedLayer, undefined, DialogModes.NO);
            writeLog("Conversion to Smart Object successful", "DEBUG");
        } catch (e) {
            writeLog("ERROR with placement or Smart Object conversion: " + e, "ERROR");
            return false;
        }
        
        // Obtenir les dimensions initiales
        var layer = doc.activeLayer;
        var layerBounds = layer.bounds;
        var width = layerBounds[2].value - layerBounds[0].value;
        var height = layerBounds[3].value - layerBounds[1].value;
        
        writeLog("Original dimensions: " + width + "x" + height, "DEBUG");
        
        // Déterminer l'orientation réelle de l'image
        var actualOrientation = (width > height) ? "Landscape" : "Portrait";
        writeLog("Actual image orientation: " + actualOrientation, "DEBUG");
        
        // Si le mode est "noResize", retourner immédiatement sans redimensionnement
        if (resizeMode === "noResize") {
            writeLog("No resize mode: keeping original size", "DEBUG");
            
            // S'assurer que l'image est bien à 100% de sa taille originale
            try {
                writeLog("Resetting Smart Object to 100% scale", "DEBUG");
                
                // Vérifier les dimensions actuelles
                var currentWidth = width;
                var currentHeight = height;
                
                // Obtenir les dimensions originales du Smart Object
                var desc = new ActionDescriptor();
                var ref = new ActionReference();
                ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
                desc.putReference(charIDToTypeID("null"), ref);
                var result = executeActionGet(ref);
                
                // Vérifier si le calque est un Smart Object
                if (result.hasKey(stringIDToTypeID("smartObject"))) {
                    // Forcer le redimensionnement à 100%
                    layer.resize(100, 100, AnchorPosition.MIDDLECENTER);
                    writeLog("Smart Object reset to 100% scale", "DEBUG");
                    
                    // Vérifier les nouvelles dimensions
                    layerBounds = layer.bounds;
                    width = layerBounds[2].value - layerBounds[0].value;
                    height = layerBounds[3].value - layerBounds[1].value;
                    writeLog("Dimensions after reset: " + width + "x" + height, "DEBUG");
                }
            } catch (e) {
                writeLog("WARNING: Could not reset Smart Object to 100%: " + e, "WARNING");
                // Continuer malgré l'erreur
            }
            
            return actualOrientation;
        }
        
        // ÉTAPE 1: Déterminer l'espace cible (cellule entière ou demi-cellule)
        var useFullCell = false;
        var targetWidth, targetHeight;
        
        // Déterminer si on utilise une cellule entière ou une demi-cellule
        if (cellType === "Single") {
            // Pour une cellule Single, on utilise toujours la cellule entière
            useFullCell = true;
        } else if (cellType === "Spread") {
            if (actualOrientation === "Landscape" && landscapeMode === "spread") {
                // Image paysage en mode spread dans une cellule Spread: utiliser la cellule entière
                useFullCell = true;
            } else {
                // Image portrait ou image paysage en mode single dans une cellule Spread: utiliser une demi-cellule
                useFullCell = false;
            }
        }
        
        // ÉTAPE 2: Calculer les dimensions cibles en fonction de l'espace
        // Lire la préférence useMarginInResize
        var preferences = readPreferencesFromPlist();
        var useMarginInResize = getPreferenceValue(preferences, "useMarginInResize", false);
        
        // Déterminer la valeur correcte de marge
        var marginSize = 0; // Valeur par défaut: pas de marge
        
        // Lire adjustedMargin depuis le fichier .board (pas depuis les préférences)
        var boardMetadata = null;
        
        // Vérifier si boardPath est défini
        if (boardPath) {
            boardMetadata = readBoardMetadata(boardPath);
            if (boardMetadata && boardMetadata.adjustedMargin !== undefined) {
                marginSize = parseFloat(boardMetadata.adjustedMargin);
                writeLog("Using adjustedMargin from board file: " + marginSize + "px", "DEBUG");
            } else {
                writeLog("No adjustedMargin found in board file, using zero margin", "DEBUG");
            }
        } else {
            writeLog("Board path not provided, using zero margin", "WARNING");
        }
        
        if (useFullCell) {
            // Pour une cellule complète (Single ou Spread), on soustrait toujours 2 * marginSize
            if (useMarginInResize) {
                targetWidth = imgMaxWidth - (2 * marginSize);
                targetHeight = imgMaxHeight - (2 * marginSize);
                writeLog("Using FULL cell with dimensions: " + targetWidth + "x" + targetHeight + " (with margins)", "INFO");
            } else {
                targetWidth = imgMaxWidth;
                targetHeight = imgMaxHeight;
                writeLog("Using FULL cell with dimensions: " + targetWidth + "x" + targetHeight + " (no margins)", "INFO");
            }
        } else {
            // Pour une demi-cellule (Spread utilisé en mode single), même logique
            if (useMarginInResize) {
                targetWidth = (imgMaxWidth / 2) - (2 * marginSize);
                targetHeight = imgMaxHeight - (2 * marginSize);
                writeLog("Using HALF cell with dimensions: " + targetWidth + "x" + targetHeight + " (with margins)", "INFO");
            } else {
                targetWidth = imgMaxWidth / 2;
                targetHeight = imgMaxHeight;
                writeLog("Using HALF cell with dimensions: " + targetWidth + "x" + targetHeight + " (no margins)", "INFO");
            }
        }
                
        // ÉTAPE 3: Appliquer la logique de redimensionnement selon le mode et l'orientation
        var ratio = 1;

        // Cas spécial: Landscape en mode cover et single dans une demi-cellule
        if (actualOrientation === "Landscape" && resizeMode === "cover" && !useFullCell) {
            // Pour cover, on veut que la hauteur corresponde exactement à la hauteur de la cellule
            ratio = targetHeight / height;
            writeLog("SPECIAL CASE: Landscape in cover mode in half cell - Using height ratio: " + ratio, "INFO");
        }
        // Cas spécial: Landscape en mode fit et single dans une demi-cellule
        else if (actualOrientation === "Landscape" && resizeMode === "fit" && !useFullCell) {
            // Pour fit, on veut que la largeur corresponde exactement à la largeur de la demi-cellule
            ratio = targetWidth / width;
            writeLog("SPECIAL CASE: Landscape in fit mode in half cell - Using width ratio: " + ratio, "INFO");
        }
        // Cas général
        else {
            // Calculer les ratios standard
            var widthRatio = targetWidth / width;
            var heightRatio = targetHeight / height;
            
            writeLog("Width ratio: " + widthRatio + ", Height ratio: " + heightRatio, "INFO");
            
            if (resizeMode === "cover") {
                // En mode cover, on utilise le ratio maximum pour s'assurer que l'image couvre toute la zone
                ratio = Math.max(widthRatio, heightRatio);
                writeLog("Cover mode: using maximum ratio: " + ratio, "INFO");
            } else if (resizeMode === "fit") {
                // En mode fit, on utilise le ratio minimum pour s'assurer que l'image tient dans la zone
                ratio = Math.min(widthRatio, heightRatio);
                writeLog("Fit mode: using minimum ratio: " + ratio, "INFO");
            } else {
                // Par défaut, utiliser le mode cover
                ratio = Math.max(widthRatio, heightRatio);
                writeLog("Unknown resize mode, falling back to cover mode: " + ratio, "WARNING");
            }
        }
        
        // Appliquer le redimensionnement si nécessaire
        if (ratio !== 1) {
            try {
                writeLog("Applying resizing with ratio: " + ratio, "INFO");
                layer.resize(ratio * 100, ratio * 100, AnchorPosition.MIDDLECENTER);
                
                // Vérifier les dimensions finales après redimensionnement
                layerBounds = layer.bounds;
                width = layerBounds[2].value - layerBounds[0].value;
                height = layerBounds[3].value - layerBounds[1].value;
                writeLog("Final dimensions after resize: " + width + "x" + height, "INFO");
            } catch (e) {
                writeLog("ERROR during resizing: " + e, "ERROR");
            }
        } else {
            writeLog("No resizing needed (ratio = 1)", "INFO");
        }
        
        writeLog("====== END placeFile (success) ======", "INFO");
        return actualOrientation;
    } catch (e) {
        writeLog("CRITICAL ERROR in placeFile: " + e, "ERROR");
        writeLog("====== END placeFile (error) ======", "ERROR");
        return false;
    }
}

/**
 * Fonction pour ajouter des cellules au layout
 * @param {Array} cellsData - Tableau contenant les données des cellules
 * @param {number} nbrCurrentCells - Nombre de cellules existantes
 * @param {number} nbrRows - Nombre de lignes
 * @param {number} nbrCols - Nombre de colonnes
 * @param {string} psbPath - Chemin du fichier .psb
 * @param {number} imgMaxHeight - Hauteur maximale de l'image
 * @param {number} imgMaxWidth - Largeur maximale de l'image
 * @param {number} layoutSpacing - Espacement entre les cellules
 * @param {number} marginMask - Masque de marge
 * @param {string} boardPath - Chemin du fichier .board
 * @param {boolean} autoPlace - Indique si l'auto placement est activé
 * @param {boolean} createGuide - Indique si la création de guides est activé
 * @param {string} cellType - Type de cellule
 * @param {boolean} overlayMaskOn - Indique si le masque d'overlay est activé
 * @param {number} widthImg - Largeur de l'image
 * @param {string} dropZone - Zone de placement
 * @param {number} layoutWidth - Largeur du layout
 * @param {string} extensionDirection - Direction d'extension
 * @param {string} effectiveOrientation - Orientation effective de l'image
 * @param {Object} progressInfo - Informations de progression
 * @param {Document} doc - Document actif
 * @param {string} landscapeMode - Mode paysage
 * @returns {boolean} - Vrai si le placement a réussi, faux sinon
 */
function addCellsToLayout(cellsData, nbrCurrentCells, nbrRows, nbrCols, psbPath, imgMaxHeight, imgMaxWidth, layoutSpacing, marginMask, boardPath, autoPlace, createGuide, cellType, overlayMaskOn, widthImg, dropZone, layoutWidth, extensionDirection, orientationImg, progressInfo) {
    try {
        writeLog("//////////////////////////////////////////////////////////////====== START addCellsToLayout ======", "INFO");
        writeLog("Received overlayMaskOn value: " + overlayMaskOn + " (type: " + typeof overlayMaskOn + ")", "DEBUG");
        
        // Variables pour les overlays
        var overlayGroup = null;
        var overlayFiles = []; 
        var boardElementsGroup = null;

        // Ouvrir ou créer le document Photoshop
        var doc = app.activeDocument;
        if (!doc) {
            writeLog("No active document found", "ERROR");
            return false;
        }

        // Créer ou obtenir le groupe Board Elements
        try {
            boardElementsGroup = doc.layerSets.getByName("Board Elements");
            writeLog("Found existing Board Elements group", "DEBUG");
        } catch (e) {
            boardElementsGroup = doc.layerSets.add();
            boardElementsGroup.name = "Board Elements";
            writeLog("Created new Board Elements group", "DEBUG");
        }

        // Si les overlays sont activés, lire les fichiers depuis le .board
        if (overlayMaskOn === true) {
            try {
                // Lire les métadonnées du fichier .board pour obtenir les overlays
                var boardMetadata = readBoardMetadata(boardPath);
                if (boardMetadata && boardMetadata.overlayFiles) {
                    writeLog("Found overlayFiles in board metadata", "DEBUG");
                    
                    // Initialiser overlayFiles comme un tableau vide
                    overlayFiles = [];
                    
                    // Récupérer les overlayFiles des métadonnées
                    if (typeof boardMetadata.overlayFiles === 'string') {
                        writeLog("overlayFiles is a string, parsing...", "DEBUG");
                        try {
                            // Si c'est une chaîne JSON, la parser
                            if (boardMetadata.overlayFiles.charAt(0) === '[') {
                                var parsedFiles = eval('(' + boardMetadata.overlayFiles + ')');
                                if (isArray(parsedFiles)) {
                                    overlayFiles = parsedFiles;
                                    writeLog("Successfully parsed JSON array with " + overlayFiles.length + " files", "DEBUG");
                                } else {
                                    overlayFiles = [boardMetadata.overlayFiles];
                                    writeLog("Parsed result is not an array, using as single file", "WARNING");
                                }
                            } else {
                                // Si c'est une chaîne simple, la convertir en tableau
                                overlayFiles = [boardMetadata.overlayFiles];
                                writeLog("Using single file path", "DEBUG");
                            }
                        } catch(e) {
                            writeLog("Error parsing overlayFiles: " + e + ", treating as single file", "WARNING");
                            overlayFiles = [boardMetadata.overlayFiles];
                        }
                    } else if (isArray(boardMetadata.overlayFiles)) {
                        overlayFiles = boardMetadata.overlayFiles.slice(); // Créer une copie du tableau
                        writeLog("Using array from metadata with " + overlayFiles.length + " files", "DEBUG");
                    } else {
                        overlayFiles = [boardMetadata.overlayFiles];
                        writeLog("Converting non-array value to single-item array", "DEBUG");
                    }

                    // Vérifier que tous les fichiers existent
                    var validFiles = [];
                    for (var i = 0; i < overlayFiles.length; i++) {
                        var file = new File(overlayFiles[i]);
                        if (file.exists) {
                            validFiles.push(overlayFiles[i]);
                            writeLog("Valid overlay file found: " + overlayFiles[i], "DEBUG");
                        } else {
                            writeLog("Overlay file not found: " + overlayFiles[i], "WARNING");
                        }
                    }

                    if (validFiles.length > 0) {
                        overlayFiles = validFiles;
                        writeLog("Found " + overlayFiles.length + " valid overlay files", "INFO");
                    } else {
                        overlayFiles = [];
                        writeLog("No valid overlay files found", "WARNING");
                    }
                    
                    // Vérification finale du type
                    if (!isArray(overlayFiles)) {
                        writeLog("Final check: overlayFiles is not an array, resetting to empty array", "WARNING");
                        overlayFiles = [];
                    }
                } else {
                    writeLog("No overlay files found in board metadata", "WARNING");
                    overlayFiles = [];
                }
            } catch(e) {
                writeLog("Error reading overlay files from board: " + e, "ERROR");
                overlayFiles = [];
            }
        }
        
        // S'assurer que overlayFiles est bien un tableau standard et inverser l'ordre
        var normalizedOverlayFiles = [];
        for (var ofIdx = overlayFiles.length - 1; ofIdx >= 0; ofIdx--) {
            normalizedOverlayFiles.push(overlayFiles[ofIdx]);
        }
        
        writeLog("Normalized overlayFiles into standard array with " + normalizedOverlayFiles.length + " items", "DEBUG");


        // Récupérer la direction d'extension depuis les préférences si elle n'est pas spécifiée
        if (!extensionDirection || (extensionDirection !== "Bottom" && extensionDirection !== "Right" && extensionDirection !== "Alternate")) {
            if (preferences) {
                extensionDirection = getPreferenceValue(preferences, "extensionDirection", "");
                
                if (extensionDirection !== "Bottom" && extensionDirection !== "Right" && extensionDirection !== "Alternate") {
                    // Par défaut, utiliser l'extension Bottom
                    extensionDirection = "Bottom";
                }
                
                writeLog("Extension direction retrieved from preferences: " + extensionDirection, "DEBUG");
            } else {
                // Par défaut, utiliser l'extension Bottom
                extensionDirection = "Bottom";
                writeLog("Default extension direction: " + extensionDirection, "DEBUG");
            }
        }
        
        // Déterminer la direction effective d'extension
        var effectiveDirection = extensionDirection;
        
        
        // Si le mode est Alternate, utiliser la dernière direction et enregistrer l'inverse
        if (extensionDirection === "Alternate") {
            // Mise à jour de la barre de progression secondaire
            if (gProgressWindow && progressInfo) {
                updateProgressBar(null, progressInfo, 
                    null,
                    null,
                    "Determining extension direction...",
                    10
                );
            }
            
            var extDir = getPreferenceValue(preferences, "extDir", "");
            
            if (extDir === "Right") {
                effectiveDirection = "Bottom";
                // Sauvegarder la prochaine direction
                if (preferences) {
                    writeLog("Next recommended extension direction: Right", "INFO");
                    savePreferenceValue("extDir", "Bottom");
                }
            } else {
                effectiveDirection = "Right";
                // Sauvegarder la prochaine direction
                if (preferences) {
                    writeLog("Next recommended extension direction: Bottom", "INFO");
                    savePreferenceValue("extDir", "Right");
                }
            }
            
            writeLog("Alternate mode: using " + effectiveDirection + " direction", "INFO");
        }
        
        writeLog("Received parameters - imgMaxHeight: " + imgMaxHeight + ", imgMaxWidth: " + imgMaxWidth + 
                 ", layoutSpacing: " + layoutSpacing + ", marginMask: " + marginMask + 
                 ", layoutWidth: " + layoutWidth + ", extensionDirection: " + extensionDirection + 
                 ", effectiveDirection: " + effectiveDirection, "DEBUG");
        
        // Lire les métadonnées du fichier .board
        var boardMetadata = readBoardMetadata(boardPath);
        
        // Convertir les paramètres en nombres pour s'assurer qu'ils sont valides
        imgMaxHeight = parseFloat(imgMaxHeight);
        imgMaxWidth = parseFloat(imgMaxWidth);
        layoutSpacing = parseFloat(layoutSpacing);
        marginMask = parseFloat(marginMask);
        layoutWidth = parseFloat(layoutWidth);
        
        // Utiliser adjustedMargin et adjustedSpacing du fichier .board si disponibles
        if (boardMetadata) {
            if (boardMetadata.adjustedMargin !== undefined) {
                marginMask = boardMetadata.adjustedMargin;
                writeLog("Using adjustedMargin from .board file: " + marginMask, "DEBUG");
            }
            
            if (boardMetadata.adjustedSpacing !== undefined) {
                layoutSpacing = boardMetadata.adjustedSpacing;
                writeLog("Using adjustedSpacing from .board file: " + layoutSpacing, "DEBUG");
            }
            
            if (boardMetadata.imgMaxWidth !== undefined) {
                imgMaxWidth = boardMetadata.imgMaxWidth;
                writeLog("Using imgMaxWidth from .board file: " + imgMaxWidth, "DEBUG");
            }
            
            if (boardMetadata.imgMaxHeight !== undefined) {
                imgMaxHeight = boardMetadata.imgMaxHeight;
                writeLog("Using imgMaxHeight from .board file: " + imgMaxHeight, "DEBUG");
            }

            if (boardMetadata.overlayFiles !== undefined) {
                overlayFiles = boardMetadata.overlayFiles;
                writeLog("Using overlayFiles from .board file: " + overlayFiles, "DEBUG");
            }
        }
        
        // Vérifier la validité des paramètres
        if (isNaN(imgMaxHeight) || imgMaxHeight <= 0) {
            writeLog("ERROR: Invalid imgMaxHeight: " + imgMaxHeight, "ERROR");
            return null;
        }
        
        if (isNaN(imgMaxWidth) || imgMaxWidth <= 0) {
            writeLog("ERROR: Invalid imgMaxWidth: " + imgMaxWidth, "ERROR");
            return null;
        }
        
        if (isNaN(layoutSpacing) || layoutSpacing < 0) {
            writeLog("ERROR: Invalid layoutSpacing: " + layoutSpacing, "ERROR");
            return null;
        }
        
        if (isNaN(marginMask) || marginMask < 0) {
            writeLog("ERROR: Invalid marginMask: " + marginMask, "ERROR");
            return null;
        }
        
        // Récupérer les couleurs depuis les métadonnées
        var boardColor = "FFFFFF";
        var marginColor = "000000";
        var backgroundColor = "FFFFFF";
        
        if (boardMetadata) {
            if (boardMetadata.boardColor) {
                boardColor = boardMetadata.boardColor.replace("#", "");
            }
            
            if (boardMetadata.marginColor) {
                marginColor = boardMetadata.marginColor.replace("#", "");
            }
            
            if (boardMetadata.backgroundColor) {
                backgroundColor = boardMetadata.backgroundColor.replace("#", "");
            }
        }
        
        // Déterminer les coordonnées de la nouvelle cellule en analysant les cellules existantes
        var selLX, selRX, selTY, selBY;
        
        // Analyser les coordonnées existantes
        var existingCells = readBoardFile(boardPath);
        
        // Variables pour stocker la première cellule créée
        var firstAddedCell = null;
        var firstAddedCellId = null;
        
        // Obtenir les informations du layout pour déterminer la structure de la grille initiale
        var layoutInfo = getLayoutCoordinates(boardPath);
        var initialRows = layoutInfo ? layoutInfo.nbrRows : 0;
        var initialCols = layoutInfo ? layoutInfo.nbrCols : 0;
        writeLog("ADD CELLS - INITIAL GRID STRUCTURE - Nombre de colonnes: " + initialCols + ", Nombre de lignes: " + initialRows, "INFO");
        
        if (existingCells && countObjectProperties(existingCells) > 0) {
            writeLog("Using existing cells to determine new cell coordinates", "DEBUG");
            
            // Trouver les limites actuelles du layout
            var maxX = 0;
            var maxY = 0;
            var lastColX = 0;
            var lastRowY = 0;
            var cellWidth = 0;
            var cellHeight = 0;
            
            // Parcourir les cellules existantes pour trouver la dernière colonne et ligne
            for (var cellId in existingCells) {
                if (existingCells.hasOwnProperty(cellId)) {
                    var cell = existingCells[cellId];
                    
                    // Mettre à jour les limites maximales
                    if (cell.bounds.maxX > maxX) maxX = cell.bounds.maxX;
                    if (cell.bounds.maxY > maxY) maxY = cell.bounds.maxY;
                    
                    // Calculer la largeur et hauteur de la cellule
                    var width = cell.bounds.maxX - cell.bounds.minX;
                    var height = cell.bounds.maxY - cell.bounds.minY;
                    
                    if (width > 0) cellWidth = width;
                    if (height > 0) cellHeight = height;
                    
                    // Identifier les cellules de la dernière colonne
                    if (cell.bounds.maxX === maxX) {
                        lastColX = cell.bounds.minX;
                    }
                    
                    // Identifier les cellules de la dernière ligne
                    if (cell.bounds.maxY === maxY) {
                        lastRowY = cell.bounds.minY;
                    }
                }
            }
            
            writeLog("Layout limits - maxX: " + maxX + ", maxY: " + maxY, "DEBUG");
            writeLog("Cell dimensions from .board - width: " + cellWidth + ", height: " + cellHeight, "DEBUG");
            
            // Créer un tableau pour stocker les coordonnées de toutes les nouvelles cellules
            var newCells = [];
            
            var initialExistingCols = initialCols;

            if (effectiveDirection === "Right") {
                // Extension horizontale: ajouter une nouvelle colonne à droite
                // Mise à jour de la barre de progression secondaire
                if (gProgressWindow && progressInfo) {
                    updateProgressBar(null, progressInfo, 
                        null,
                        null,
                        "Preparing horizontal extension...",
                        30
                    );
                }
                
                // Calculer la position X de la nouvelle colonne
                var newColX = maxX + layoutSpacing;
                
                // Trouver toutes les positions Y des cellules existantes pour créer une cellule à chaque ligne
                var rowPositions = [];
                for (var cellId in existingCells) {
                    if (existingCells.hasOwnProperty(cellId)) {
                        var cell = existingCells[cellId];
                        var cellMinY = cell.bounds.minY;
                        
                        // Ajouter la position Y si elle n'est pas déjà dans le tableau
                        if (!arrayContains(rowPositions, cellMinY)) {
                            rowPositions.push(cellMinY);
                        }
                    }
                }
                
                // Trier les positions Y pour traiter les lignes de haut en bas
                rowPositions.sort(function(a, b) { return a - b; });
                
                writeLog("Found " + rowPositions.length + " rows to extend with a new column", "INFO");
                
                // Pour chaque nouvelle cellule
                for (var i = 0; i < rowPositions.length; i++) {
                    // Mise à jour de la barre de progression secondaire
                    if (gProgressWindow && progressInfo) {
                        var progress = 30 + Math.round((i / rowPositions.length) * 70);
                        updateProgressBar(null, progressInfo, 
                            null,
                            null,
                            "Creating cell " + (i + 1) + " of " + rowPositions.length,
                            progress
                        );
                    }
                    
                    var rowY = rowPositions[i];
                    
                    // Calculer les coordonnées de la nouvelle cellule
                    var cellCoords = {
                        minX: newColX,
                        maxX: newColX + cellWidth,
                        minY: rowY,
                        maxY: rowY + cellHeight
                    };
                    
                    newCells.push(cellCoords);
                    writeLog("New cell coordinates for row " + i + ": " + cellCoords.minX + "," + cellCoords.minY + " -> " + cellCoords.maxX + "," + cellCoords.maxY, "DEBUG");
                    
                    // Stocker la première cellule (celle la plus en haut)
                    if (firstAddedCell === null || cellCoords.minY < firstAddedCell.minY) {
                        firstAddedCell = cellCoords;
                        firstAddedCellId = nbrCurrentCells + i + 1; // Calculer l'ID probable
                        writeLog("Identified potential first cell (top-most) with ID: " + firstAddedCellId, "DEBUG");
                    }
                }
                
                // Mettre à jour le nombre de colonnes
                nbrCols++;
                
                // Sauvegarder la direction d'extension pour la prochaine fois
                if (extensionDirection === "Alternate" && preferences) {
                    writeLog("Saving next extension direction: Bottom", "INFO");
                    savePreferenceValue("extDir", "Right");
                }
        } else {
                // Extension verticale: ajouter une nouvelle ligne en bas
                // Mise à jour de la barre de progression secondaire
                if (gProgressWindow && progressInfo) {
                    updateProgressBar(null, progressInfo, 
                        null,
                        null,
                        "Preparing vertical extension...",
                        30
                    );
                }
                
                // Calculer la position Y de la nouvelle ligne
                var newRowY = maxY + layoutSpacing;
                
                // Trouver toutes les positions X des cellules existantes pour créer une cellule à chaque colonne
                var colPositions = [];
                for (var cellId in existingCells) {
                    if (existingCells.hasOwnProperty(cellId)) {
                        var cell = existingCells[cellId];
                        var cellMinX = cell.bounds.minX;
                        
                        // Ajouter la position X si elle n'est pas déjà dans le tableau
                        if (!arrayContains(colPositions, cellMinX)) {
                            colPositions.push(cellMinX);
                        }
                    }
                }
                
                // Trier les positions X pour traiter les colonnes de gauche à droite
                colPositions.sort(function(a, b) { return a - b; });
                
                writeLog("Found " + colPositions.length + " columns to extend with a new row", "INFO");
                
                // Pour chaque nouvelle cellule
                for (var i = 0; i < colPositions.length; i++) {
                    // Mise à jour de la barre de progression secondaire
                    if (gProgressWindow && progressInfo) {
                        var progress = 30 + Math.round((i / colPositions.length) * 70);
                        updateProgressBar(null, progressInfo, 
                            null,
                            null,
                            "Creating cell " + (i + 1) + " of " + colPositions.length,
                            progress
                        );
                    }
                    
                    var colX = colPositions[i];
                    
                    // Calculer les coordonnées de la nouvelle cellule
                    var cellCoords = {
                        minX: colX,
                        maxX: colX + cellWidth,
                        minY: newRowY,
                        maxY: newRowY + cellHeight
                    };
                    
                    newCells.push(cellCoords);
                    writeLog("New cell coordinates for column " + i + ": " + cellCoords.minX + "," + cellCoords.minY + " -> " + cellCoords.maxX + "," + cellCoords.maxY, "DEBUG");
                    
                    // Stocker la première cellule (celle la plus à gauche)
                    if (firstAddedCell === null || cellCoords.minX < firstAddedCell.minX) {
                        firstAddedCell = cellCoords;
                        firstAddedCellId = nbrCurrentCells + i + 1; // Calculer l'ID probable
                        writeLog("Identified potential first cell (left-most) with ID: " + firstAddedCellId, "DEBUG");
                    }
                }
                
                // Mettre à jour le nombre de lignes
                nbrRows++;
                
                // Sauvegarder la direction d'extension pour la prochaine fois
                if (extensionDirection === "Alternate" && preferences) {
                    writeLog("Saving next extension direction: Right", "INFO");
                    savePreferenceValue("extDir", "Bottom");
                }
            }
            
            // Utiliser les coordonnées de la dernière cellule pour le redimensionnement du canevas
            if (newCells.length > 0) {
                var lastCell = newCells[newCells.length - 1];
                selLX = lastCell.minX;
                selRX = lastCell.maxX;
                selTY = lastCell.minY;
                selBY = lastCell.maxY;
            } else {
                // Fallback au cas où aucune cellule n'a été créée
                if (effectiveDirection === "Right") {
                    selLX = maxX + layoutSpacing;
                    selRX = selLX + cellWidth;
                    selTY = lastRowY;
                    selBY = selTY + cellHeight;
                } else {
                    selLX = lastColX;
                    selRX = selLX + cellWidth;
                    selTY = maxY + layoutSpacing;
                    selBY = selTY + cellHeight;
                }
            }
        } else {
            // Aucune cellule existante trouvée, utiliser les valeurs des paramètres
            writeLog("No existing cells found, using parameter values", "WARNING");
            
            if (effectiveDirection === "Right") {
            // Extension horizontale: ajouter une colonne à droite
            selLX = (nbrCols * imgMaxWidth) + (nbrCols * layoutSpacing);
            selRX = selLX + imgMaxWidth;
            selTY = 0;
            selBY = imgMaxHeight;
            
                writeLog("Horizontal extension with default values", "INFO");
                writeLog("New cell coordinates: " + selLX + "," + selTY + " -> " + selRX + "," + selBY, "DEBUG");
                
                // Dans ce cas, il n'y a qu'une seule cellule, donc c'est la première
                firstAddedCell = {
                    minX: selLX,
                    maxX: selRX,
                    minY: selTY,
                    maxY: selBY
                };
                firstAddedCellId = 1; // Première cellule
                writeLog("First cell identified with ID: 1", "DEBUG");
            
            // Mettre à jour le nombre de colonnes
            nbrCols++;
            
            // Sauvegarder la direction d'extension pour la prochaine fois
                if (extensionDirection === "Alternate" && preferences) {
                    writeLog("Saving next extension direction: Bottom", "INFO");
                    savePreferenceValue("extDir", "Right");
            }
        } else {
            // Extension verticale: ajouter une ligne en bas
            selLX = 0;
            selRX = imgMaxWidth;
            selTY = (nbrRows * imgMaxHeight) + (nbrRows * layoutSpacing);
            selBY = selTY + imgMaxHeight;
            
                writeLog("Vertical extension with default values", "INFO");
                writeLog("New cell coordinates: " + selLX + "," + selTY + " -> " + selRX + "," + selBY, "DEBUG");
                
                // Dans ce cas, il n'y a qu'une seule cellule, donc c'est la première
                firstAddedCell = {
                    minX: selLX,
                    maxX: selRX,
                    minY: selTY,
                    maxY: selBY
                };
                firstAddedCellId = 1; // Première cellule
                writeLog("First cell identified with ID: 1", "DEBUG");
            
            // Mettre à jour le nombre de lignes
            nbrRows++;
            
            // Sauvegarder la direction d'extension pour la prochaine fois
                if (extensionDirection === "Alternate" && preferences) {
                    writeLog("Saving next extension direction: Right", "INFO");
                    savePreferenceValue("extDir", "Bottom");
                }
            }
        }
        
        // Ouvrir le document si nécessaire
        if (!doc) {
            doc = app.open(new File(psbPath));
        }
        
        // Obtenir les dimensions originales du document
        var originalWidth = doc.width.value;
        var originalHeight = doc.height.value;
        
        // Trouver le groupe Board Elements et déverrouiller tous les calques
        var boardElementsGroup;
        try {
            boardElementsGroup = doc.layerSets.getByName("Board Elements");
            
            // Déverrouiller le groupe et tous ses calques
            if (boardElementsGroup.allLocked) {
                boardElementsGroup.allLocked = false;
                writeLog("Board Elements group unlocked", "DEBUG");
            }
        } catch (e) {
            writeLog("Error searching for Board Elements group: " + e, "ERROR");
            return null;
        }
        
        // Trouver les calques nécessaires
        var marieLouiseLayer = null;
        var bordersLayer = null;
        var guttersLayer = null;
        var singlePageGroup = null;
        var legendLayer = null;
        var overlayGroup = null;
        
        try {
            // Trouver les calques nécessaires
            marieLouiseLayer = findLayerByName(boardElementsGroup, "Mask");
            bordersLayer = findLayerByName(boardElementsGroup, "Borders");
            legendLayer = findLayerByName(boardElementsGroup, "Legend");
            overlayGroup = findLayerByName(boardElementsGroup, "Overlay");
            // Déverrouiller les calques
            if (marieLouiseLayer && marieLouiseLayer.allLocked) {
                marieLouiseLayer.allLocked = false;
                writeLog("Mask layer unlocked", "DEBUG");
            }
            
            if (bordersLayer && bordersLayer.allLocked) {
                bordersLayer.allLocked = false;
                writeLog("Layer Borders unlocked", "DEBUG");
            }
            
            if (legendLayer && legendLayer.allLocked) {
                legendLayer.allLocked = false;
                writeLog("Layer Legend unlocked", "DEBUG");
            }
            
            if (overlayGroup && overlayGroup.allLocked) {
                overlayGroup.allLocked = false;
                writeLog("Layer Overlay unlocked", "DEBUG");
            }
            
            // Trouver les calques spécifiques pour le type Spread
                    if (cellType.toLowerCase() === "spread") {
                guttersLayer = findLayerByName(boardElementsGroup, "Gutters");
                if (guttersLayer && guttersLayer.allLocked) {
                    guttersLayer.allLocked = false;
                    writeLog("Layer Gutters unlocked", "DEBUG");
                }
                
                // Trouver le groupe Simple page Mask
                try {
                    singlePageGroup = boardElementsGroup.layerSets.getByName("Simple page Mask");
                    if (singlePageGroup && singlePageGroup.allLocked) {
                        singlePageGroup.allLocked = false;
                        writeLog("Simple page Mask group unlocked", "DEBUG");
                    }
                } catch (e) {
                    writeLog("Simple page Mask group not found: " + e, "ERROR");
                }
            }
        } catch (e) {
            writeLog("Error searching for layers: " + e, "ERROR");
            return null;
        }
        
        // Étendre le canevas si nécessaire
        if (effectiveDirection === "Right") {
            // Extension horizontale: augmenter la largeur
            if (originalWidth < selRX + layoutSpacing) {
                try {
                    // Calculer la nouvelle largeur en ajoutant une cellule complète + espacement
                    var newWidth = originalWidth + cellWidth + layoutSpacing;
                    // Utiliser la méthode resizeCanvas avec l'ancrage à gauche
                    doc.resizeCanvas(newWidth, originalHeight, AnchorPosition.TOPLEFT);
                    writeLog("Canvas extended horizontally to " + newWidth + "x" + originalHeight + " (anchor: top left)", "DEBUG");
                    
                    // Ajuster la vue pour voir tout le document
                    fitDocumentOnScreen();
                } catch (e) {
                    writeLog("Error during horizontal canvas extension: " + e, "ERROR");
                    
                    // Méthode alternative avec executeAction si resizeCanvas échoue
                    try {
                        var idCnvS = charIDToTypeID("CnvS");
                        var desc = new ActionDescriptor();
                        var idWdth = charIDToTypeID("Wdth");
                        var idPxl = charIDToTypeID("#Pxl");
                        desc.putUnitDouble(idWdth, idPxl, newWidth);
                        var idHght = charIDToTypeID("Hght");
                        desc.putUnitDouble(idHght, idPxl, originalHeight);
                        var idHrzn = charIDToTypeID("Hrzn");
                        var idHrzL = charIDToTypeID("HrzL");
                        desc.putEnumerated(idHrzn, idHrzn, idHrzL);
                        var idVrtc = charIDToTypeID("Vrtc");
                        var idVrtT = charIDToTypeID("VrtT");
                        desc.putEnumerated(idVrtc, idVrtc, idVrtT);
                        executeAction(idCnvS, desc, DialogModes.NO);
                        writeLog("Canvas extended horizontally with executeAction (alternative method)", "DEBUG");
                        
                        // Ajuster la vue pour voir tout le document
                        fitDocumentOnScreen();
                    } catch (e2) {
                        writeLog("Error during horizontal canvas extension (alternative method): " + e2, "ERROR");
                        return null;
                    }
                }
                
                // Remplir la zone nouvellement créée sur le calque Mask
                if (marieLouiseLayer) {
                    doc.activeLayer = marieLouiseLayer;
                    
                    // Sélectionner uniquement la zone nouvellement ajoutée
                    var newAreaSelection = [
                        [originalWidth, 0],
                        [originalWidth, originalHeight],
                        [newWidth, originalHeight],
                        [newWidth, 0]
                    ];
                    
                    doc.selection.select(newAreaSelection);
                    
                    // Remplir avec la couleur de fond
                    var marieLouiseColor = new SolidColor();
                    marieLouiseColor.rgb.hexValue = boardColor;
                    doc.selection.fill(marieLouiseColor);
                    
                    // Désélectionner
                            doc.selection.deselect();
                            
                    writeLog("Newly created area filled on the Mask layer", "DEBUG");
                }
                
                // Remplir la zone nouvellement créée sur le calque Borders
                if (bordersLayer) {
                    doc.activeLayer = bordersLayer;
                    
                    // Sélectionner la zone nouvellement créée
                    var newAreaSelection = [
                        [originalWidth, 0],
                        [originalWidth, originalHeight],
                        [newWidth, originalHeight],
                        [newWidth, 0]
                    ];
                    
                    doc.selection.select(newAreaSelection);
                                    
                                    // Remplir avec la couleur de bordure
                    var borderColor = new SolidColor();
                    borderColor.rgb.hexValue = marginColor;
                    doc.selection.fill(borderColor);
                    
                    // Désélectionner
                                    doc.selection.deselect();
                                    
                    writeLog("Newly created area filled on the Borders layer", "DEBUG");
                }
                
                // Remplir la zone nouvellement créée sur le calque Background
                try {
                    // Trouver le calque Background
                    var bgLayer = doc.artLayers.getByName("Background");
                    if (bgLayer) {
                        doc.activeLayer = bgLayer;
                        
                        // Sélectionner la zone nouvellement créée
                        var newAreaSelection = [
                            [originalWidth, 0],
                            [originalWidth, originalHeight],
                            [newWidth, originalHeight],
                            [newWidth, 0]
                        ];
                        
                        doc.selection.select(newAreaSelection);
                        
                        // Remplir avec la couleur d'arrière-plan
                        var bgColorObj = new SolidColor();
                        bgColorObj.rgb.hexValue = backgroundColor;
                        doc.selection.fill(bgColorObj);
                        
                        // Désélectionner
                        doc.selection.deselect();
                        
                        writeLog("Newly created area filled on the Background layer with color: " + backgroundColor, "DEBUG");
                    } else {
                        writeLog("Background layer not found", "WARNING");
                    }
                } catch (e) {
                    writeLog("Error filling Background layer: " + e, "ERROR");
                }
            }
        } else {
            // Extension verticale: augmenter la hauteur
            if (originalHeight < selBY + layoutSpacing) {
                try {
                    // Calculer la nouvelle hauteur en ajoutant une cellule complète + espacement
                    var newHeight = originalHeight + cellHeight + layoutSpacing;
                    // Utiliser la méthode resizeCanvas avec l'ancrage en haut
                    doc.resizeCanvas(originalWidth, newHeight, AnchorPosition.TOPRIGHT);
                    writeLog("Canvas extended vertically to " + originalWidth + "x" + newHeight + " (anchor: top right)", "DEBUG");
                    
                    // Ajuster la vue pour voir tout le document
                    fitDocumentOnScreen();
                } catch (e) {
                    writeLog("Error during vertical canvas extension: " + e, "ERROR");
                    
                    // Méthode alternative avec executeAction si resizeCanvas échoue
                    try {
                        var idCnvS = charIDToTypeID("CnvS");
                        var desc = new ActionDescriptor();
                        var idWdth = charIDToTypeID("Wdth");
                        var idPxl = charIDToTypeID("#Pxl");
                        desc.putUnitDouble(idWdth, idPxl, originalWidth);
                        var idHght = charIDToTypeID("Hght");
                        desc.putUnitDouble(idHght, idPxl, newHeight);
                        var idHrzn = charIDToTypeID("Hrzn");
                        var idHrzL = charIDToTypeID("HrzL");
                        desc.putEnumerated(idHrzn, idHrzn, idHrzL);
                        var idVrtc = charIDToTypeID("Vrtc");
                        var idVrtT = charIDToTypeID("VrtT");
                        desc.putEnumerated(idVrtc, idVrtc, idVrtT);
                        executeAction(idCnvS, desc, DialogModes.NO);
                        writeLog("Canvas extended vertically with executeAction (alternative method)", "DEBUG");
                        
                        // Ajuster la vue pour voir tout le document
                        fitDocumentOnScreen();
                    } catch (e2) {
                        writeLog("Error during vertical canvas extension (alternative method): " + e2, "ERROR");
                        return null;
                    }
                }
                
                // Remplir la zone nouvellement créée sur le calque Mask
                if (marieLouiseLayer) {
                    doc.activeLayer = marieLouiseLayer;
                    
                    // Sélectionner uniquement la zone nouvellement ajoutée
                    var newAreaSelection = [
                        [0, originalHeight],
                        [0, newHeight],
                        [originalWidth, newHeight],
                        [originalWidth, originalHeight]
                    ];
                    
                    doc.selection.select(newAreaSelection);
                    
                    // Remplir avec la couleur de fond
                    var marieLouiseColor = new SolidColor();
                    marieLouiseColor.rgb.hexValue = boardColor;
                    doc.selection.fill(marieLouiseColor);
                    
                    // Désélectionner
                    doc.selection.deselect();
                    
                    writeLog("Newly created area filled on the Mask layer", "DEBUG");
                }
                
                // Remplir la zone nouvellement créée sur le calque Borders
                if (bordersLayer) {
                    doc.activeLayer = bordersLayer;
                    
                    // Sélectionner la zone nouvellement créée
                    var newAreaSelection = [
                        [0, originalHeight],
                        [0, newHeight],
                        [originalWidth, newHeight],
                        [originalWidth, originalHeight]
                    ];
                    
                    doc.selection.select(newAreaSelection);
                    
                    // Remplir avec la couleur de bordure
                    var borderColor = new SolidColor();
                    borderColor.rgb.hexValue = marginColor;
                    doc.selection.fill(borderColor);
                    
                    // Désélectionner
                    //doc.selection.deselect();
                    
                    writeLog("Newly created area filled on the Borders layer", "DEBUG");
                }
                
                // Remplir la zone nouvellement créée sur le calque Background
                try {
                    // Trouver le calque Background
                    var bgLayer = doc.artLayers.getByName("Background");
                    if (bgLayer) {
                        doc.activeLayer = bgLayer;
                        
                    // Sélectionner la zone nouvellement créée
                    var newAreaSelection = [
                        [0, originalHeight],
                        [0, newHeight],
                        [originalWidth, newHeight],
                        [originalWidth, originalHeight]
                    ];
                        
                        doc.selection.select(newAreaSelection);
                        
                        // Remplir avec la couleur d'arrière-plan
                        var bgColorObj = new SolidColor();
                        bgColorObj.rgb.hexValue = backgroundColor;
                        doc.selection.fill(bgColorObj);
                        
                        // Désélectionner
                        doc.selection.deselect();
                        
                        writeLog("Newly created area filled on the Background layer with color: " + backgroundColor, "DEBUG");
                    } else {
                        writeLog("Background layer not found", "WARNING");
                    }
                } catch (e) {
                    writeLog("Error filling Background layer: " + e, "ERROR");
                }
            }
        }
        
        // Mise à jour des calques pour la nouvelle cellule
        try {
            // Créer toutes les nouvelles cellules
            for (var i = 0; i < newCells.length; i++) {
                var cellBounds = newCells[i];
                var cellLX = cellBounds.minX;
                var cellRX = cellBounds.maxX;
                var cellTY = cellBounds.minY;
                var cellBY = cellBounds.maxY;
                
                writeLog("Creating cell " + (i+1) + " of " + newCells.length + " at coordinates: " + 
                         cellLX + "," + cellTY + " -> " + cellRX + "," + cellBY, "INFO");
                
            // 1. Mise à jour du calque Marie Louise (Mask) - Créer un "trou" pour la cellule
            if (marieLouiseLayer) {
                doc.activeLayer = marieLouiseLayer;
                
                // Créer la sélection pour la nouvelle cellule
                doc.selection.select([
                        [cellLX, cellTY],
                        [cellLX, cellBY],
                        [cellRX, cellBY],
                        [cellRX, cellTY]
                ]);
                
                // Effacer la sélection pour créer un "trou"
                doc.selection.clear();
                
                // Désélectionner
                doc.selection.deselect();
                
                    writeLog("Hole created in the Mask layer for cell " + (i+1), "DEBUG");
            }
            
            // 2. Mise à jour du calque Borders - Créer un "trou" pour la cellule (avec marges)
            if (bordersLayer) {
                doc.activeLayer = bordersLayer;
                
                // Créer la sélection pour la zone intérieure de la cellule (avec marges)
                doc.selection.select([
                        [cellLX + marginMask, cellTY + marginMask],
                        [cellLX + marginMask, cellBY - marginMask],
                        [cellRX - marginMask, cellBY - marginMask],
                        [cellRX - marginMask, cellTY + marginMask]
                ]);
                
                // Effacer la sélection pour créer un "trou"
                doc.selection.clear();
                
                // Désélectionner
                doc.selection.deselect();
                
                    writeLog("Hole created in the Borders layer for cell " + (i+1), "DEBUG");
                }
                
                // 3. Création du masque simple page pour la nouvelle cellule (pour les cellules Spread)
                if (cellType.toLowerCase() === "spread" && singlePageGroup) {
                    // Obtenir les informations du layout pour déterminer la structure de la grille
                    var layoutInfo = getLayoutCoordinates(boardPath);
                    var existingRows = layoutInfo ? layoutInfo.nbrRows : 0;
                    var existingCols = layoutInfo ? layoutInfo.nbrCols : 0;
                    
                    writeLog("Existing grid structure: " + existingRows + " rows, " + existingCols + " columns", "INFO");
                    writeLog("GRID STRUCTURE FOR MASK SEARCH - Nombre de colonnes: " + existingCols + ", Nombre de lignes: " + existingRows, "INFO");
                    
                    // Déterminer l'ID du masque simple page en fonction de la direction d'extension
                var row, col;
                    
                    if (effectiveDirection === "Right") {
                        // Extension horizontale: ajouter une colonne à droite
                        // La colonne est existingCols + 1 (pas nbrCols qui peut être incorrect)
                        col = initialExistingCols + 1;

                        // Pour les lignes, utilisez la position réelle dans la grille
                        row = i + 1; // i commence à 0, donc +1 pour la première ligne
                        
                        writeLog("Right extension: using row " + row + " and column " + col, "DEBUG");
                    } else {
                        // Extension verticale: ajouter une ligne en bas
                        // La ligne est nbrRows (le numéro de la nouvelle ligne)
                        row = nbrRows; // Utilisez nbrRows qui est déjà incrémenté plus haut
                        
                        // Pour les colonnes, utilisez la position réelle dans la grille
                        col = i + 1; // i commence à 0, donc +1 pour la première colonne
                        
                        writeLog("Bottom extension: using row " + row + " and column " + col, "DEBUG");
                    }
                
                var maskId = "R" + row + "C" + col;
                    writeLog("Creating simple page mask with ID: " + maskId + " (row=" + row + ", col=" + col + ")", "INFO");
                
                // Vérifier que les indices sont valides
                if (isNaN(row) || row < 1) {
                    writeLog("ERROR: invalid rowIndex, using default value 1", "ERROR");
                    row = 1;
                }
                if (isNaN(col) || col < 1) {
                    writeLog("ERROR: invalid colIndex, using default value 1", "ERROR");
                    col = 1;
                }
                
                // Vérifier que singlePageGroup est valide
                if (!singlePageGroup) {
                    writeLog("ERROR: singlePageGroup is null", "ERROR");
                        continue; // Passer à la cellule suivante
                }
                
                // Créer un nouveau calque pour le masque
                var maskLayer = singlePageGroup.artLayers.add();
                maskLayer.name = maskId;
                
                    // Calculer le milieu de la cellule (en utilisant la largeur réelle de la cellule)
                    var cellWidth = cellRX - cellLX;
                    var middleX = cellLX + (cellWidth / 2);
                    
                    writeLog("Cell width: " + cellWidth + ", Middle X: " + middleX, "DEBUG");
                    
                    // Créer la sélection pour le masque (au milieu de la cellule, avec largeur = marginMask)
                    doc.activeLayer = maskLayer;
                    
                    try {
                doc.selection.select([
                            [middleX - marginMask, cellTY],
                            [middleX - marginMask, cellBY],
                            [middleX + marginMask, cellBY],
                            [middleX + marginMask, cellTY]
                ]);
                
                // Remplir la sélection avec la couleur de marge
                var maskColor = new SolidColor();
                        maskColor.rgb.hexValue = marginColor.replace("#", "");
                doc.selection.fill(maskColor);
                
                // Désélectionner
                doc.selection.deselect();
                
                // Par défaut, masquer le masque simple page (il sera activé si nécessaire)
                maskLayer.visible = false;
                
                        writeLog("Simple page mask created successfully for cell " + (i+1), "DEBUG");
                    } catch (e) {
                        writeLog("Error creating simple page mask for cell " + (i+1) + ": " + e, "ERROR");
                    }
            }
            
                // 4. Création de la gouttière pour la nouvelle cellule (pour les cellules Spread)
            if (cellType.toLowerCase() === "spread" && guttersLayer) {
                doc.activeLayer = guttersLayer;
                
                // Calculer les coordonnées de la gouttière (au centre de la cellule)
                    var cellWidth = cellRX - cellLX;
                    var cellHeight = cellBY - cellTY;
                    var middleX = cellLX + (cellWidth / 2);
                    var gutterWidth = Math.max(1, Math.round(cellWidth / 1000)); // Au moins 1 pixel
                    
                    // Calculer les dimensions de la gouttière
                    var gutterHeight = cellHeight * 0.9;
                    var gutterYOffset = (cellHeight - gutterHeight) / 2;
                    
                    writeLog("Gutter positioning for cell " + (i+1) + " - cellWidth: " + cellWidth + ", cellHeight: " + cellHeight + 
                             ", middleX: " + middleX + ", gutterWidth: " + gutterWidth, "DEBUG");
                
                // Créer la sélection pour la gouttière
                    try {
                doc.selection.select([
                            [middleX - gutterWidth/2, cellTY + gutterYOffset],
                            [middleX - gutterWidth/2, cellTY + gutterYOffset + gutterHeight],
                            [middleX + gutterWidth/2, cellTY + gutterYOffset + gutterHeight],
                            [middleX + gutterWidth/2, cellTY + gutterYOffset]
                ]);
                
                // Remplir la sélection avec la couleur de gouttière
                var gutterColor = new SolidColor();
                // La couleur de gouttière est toujours fixée à 222222
                gutterColor.rgb.hexValue = "222222";
                doc.selection.fill(gutterColor);
                
                // Désélectionner
                    doc.selection.deselect();
                    
                        writeLog("Gutter created successfully for cell " + (i+1), "DEBUG");
                    } catch (e) {
                        writeLog("Error creating gutter for cell " + (i+1) + ": " + e, "ERROR");
                    }
            }
            
            // 5. Création des overlays si nécessaire
            if (overlayMaskOn === true && normalizedOverlayFiles.length > 0) {
                try {
                    // Créer le groupe Overlay si nécessaire
                    if (!overlayGroup) {
                        overlayGroup = findOrCreateGroup(boardElementsGroup, "Overlay");
                    }
        
                    var cellBounds = newCells[i];
                    var cellNumber = nbrCurrentCells + i + 1;
        
                    var overlayOptions = {
                        cellType: cellType,
                        cellNumber: cellNumber,
                        row: Math.ceil(cellNumber / nbrCols),
                        col: ((cellNumber - 1) % nbrCols) + 1,
                        totalRows: nbrRows,
                        totalCols: nbrCols,
                        boardPath: boardPath
                    };
        
                    var placementResult = handleOverlayPlacement(
                        cellType,
                        cellNumber,
                        cellBounds.maxY - cellBounds.minY,
                        cellBounds.maxX - cellBounds.minX,
                        normalizedOverlayFiles,
                        overlayOptions
                    );
        
                    if (placementResult.success) {
                        var overlaySuccess = createOverlayLayers(
                            cellBounds.minX,
                            cellBounds.maxX,
                            cellBounds.minY,
                            cellBounds.maxY,
                            marginMask,
                            overlayGroup,
                            normalizedOverlayFiles,
                            overlayOptions
                        );
        
                        writeLog("Overlay processing result for cell " + cellNumber + ": " + 
                                (overlaySuccess ? "success" : "failed"), 
                                overlaySuccess ? "INFO" : "WARNING");
                    } else {
                        writeLog("Overlay placement failed: " + placementResult.error, "ERROR");
                    }
                } catch (e) {
                    writeLog("Error creating overlay for cell " + (i+1) + ": " + e, "ERROR");
                }
            }

            // 6. Création des guides si nécessaire
            if (createGuide === true || createGuide === "true") {
                writeLog("Creating guides for cell " + (i+1) + " at positions: LX=" + cellLX + ", RX=" + cellRX + ", TY=" + cellTY + ", BY=" + cellBY, "DEBUG");
                
                // Guides verticaux
                    createVerticalGuide(cellLX);
                    writeLog("Created vertical guide at left edge: " + cellLX, "DEBUG");
                    
                    createVerticalGuide(cellRX);
                    writeLog("Created vertical guide at right edge: " + cellRX, "DEBUG");
                    
                    createVerticalGuide(cellLX + marginMask);
                    writeLog("Created vertical guide at left margin: " + (cellLX + marginMask), "DEBUG");
                    
                    createVerticalGuide(cellRX - marginMask);
                    writeLog("Created vertical guide at right margin: " + (cellRX - marginMask), "DEBUG");
                
                // Guide central pour les cellules Spread
                    if (cellType.toLowerCase() === "spread") {
                        var middleX = cellLX + ((cellRX - cellLX) / 2);
                        createVerticalGuide(middleX);
                        writeLog("Created central vertical guide for spread at: " + middleX, "DEBUG");
                }
                
                // Guides horizontaux
                    createHorizontalGuide(cellTY);
                    writeLog("Created horizontal guide at top edge: " + cellTY, "DEBUG");
                    
                    createHorizontalGuide(cellBY);
                    writeLog("Created horizontal guide at bottom edge: " + cellBY, "DEBUG");
                    
                    createHorizontalGuide(cellTY + marginMask);
                    writeLog("Created horizontal guide at top margin: " + (cellTY + marginMask), "DEBUG");
                    
                    createHorizontalGuide(cellBY - marginMask);
                    writeLog("Created horizontal guide at bottom margin: " + (cellBY - marginMask), "DEBUG");
                    
                    writeLog("All guides created for cell " + (i+1), "DEBUG");
                }
                
                // 7. Sauvegarder les coordonnées dans le fichier .board
                var newCellIndex = getNextCellIndex(boardPath);
                if (newCellIndex === -1) {
                    writeLog("ERROR: Unable to determine next cell index. Falling back to nbrCurrentCells + " + (i+1), "ERROR");
                    newCellIndex = nbrCurrentCells + i + 1;
                }
                
        var bounds = {
                    minX: cellLX,
                    maxX: cellRX,
                    minY: cellTY,
                    maxY: cellBY
                };
                
                writeLog("Saving coordinates for cell " + (i+1) + " (index: " + newCellIndex + ")", "DEBUG");
                
                // Déterminer si la réorganisation est nécessaire (toujours pour l'extension vers la droite)
                var needsReorg = (effectiveDirection === "Right");
                if (needsReorg) {
                    writeLog("Reorganization will be applied after saving (Right extension)", "INFO");
                }
                
                var saveResult = saveCellCoordinates(bounds, boardPath, newCellIndex, needsReorg);
        if (!saveResult) {
                    writeLog("Error saving cell coordinates for cell " + (i+1), "ERROR");
                }
            }
            
            // Repositionner le calque Legend par rapport à la nouvelle ligne/colonne
            if (legendLayer) {
                doc.activeLayer = legendLayer;
                
                // Utiliser adjustedSpacing du fichier .board si disponible
                var spacingToUse = layoutSpacing;
                if (boardMetadata && boardMetadata.adjustedSpacing !== undefined) {
                    spacingToUse = boardMetadata.adjustedSpacing;
                    writeLog("Using adjustedSpacing for legend positioning: " + spacingToUse, "INFO");
                }
                
                // Appliquer une translation simple basée sur la direction d'extension
                if (effectiveDirection === "Right") {
                    // Extension vers la droite : déplacer la légende de la largeur d'une cellule + espacement
                    var horizontalOffset = imgMaxWidth + spacingToUse;
                    legendLayer.translate(horizontalOffset, 0);
                    writeLog("Legend layer moved right by: " + horizontalOffset + "px (imgMaxWidth + adjustedSpacing)", "INFO");
                } else {
                    // Extension vers le bas : déplacer la légende de la hauteur d'une cellule + espacement
                    var verticalOffset = imgMaxHeight + spacingToUse;
                    legendLayer.translate(0, verticalOffset);
                    writeLog("Legend layer moved down by: " + verticalOffset + "px (imgMaxHeight + adjustedSpacing)", "INFO");
                }
            }
        } catch (e) {
            writeLog("Error creating cells: " + e, "ERROR");
            // Continuer malgré l'erreur
        }
        
        // Verrouiller tous les calques à la fin
        try {
            if (marieLouiseLayer) {
                marieLouiseLayer.allLocked = true;
                writeLog("Mask layer locked", "DEBUG");
            }
            
            if (bordersLayer) {
                bordersLayer.allLocked = true;
                writeLog("Borders layer locked", "DEBUG");
            }
            
            if (legendLayer) {
                legendLayer.allLocked = true;
                writeLog("Legend layer locked", "DEBUG");
            }
            
            if (cellType.toLowerCase() === "spread") {
                if (guttersLayer) {
                    guttersLayer.allLocked = true;
                    writeLog("Gutters layer locked", "DEBUG");
                }
                
                if (singlePageGroup) {
                    singlePageGroup.allLocked = true;
                    writeLog("Simple page mask group locked", "DEBUG");
                }
            }
            
            // Verrouiller le groupe principal
            boardElementsGroup.allLocked = true;
            writeLog("Board Elements group locked", "DEBUG");
            
            // Réduire tous les groupes
            app.runMenuItem(stringIDToTypeID('collapseAllGroupsEvent'));
            writeLog("All groups collapsed", "DEBUG");
                                } catch (e) {
            writeLog("Error locking layers: " + e, "ERROR");
            // Continuer malgré l'erreur
        }
        
        writeLog("====== END addCellsToLayout ======", "DEBUG");
        
        // S'assurer que le calque actif est bien celui de l'image importée
        try {
            // Trouver le groupe "Board Content" qui contient l'image importée
            var boardContentGroup = doc.layerSets.getByName("Board Content");
            
            // L'image importée est normalement le dernier calque ajouté dans ce groupe
            if (boardContentGroup && boardContentGroup.artLayers.length > 0) {
                // Activer le dernier calque ajouté (l'image importée)
                doc.activeLayer = boardContentGroup.artLayers[0]; // Le premier calque est le plus récent
                writeLog("Active layer set back to the imported image layer", "INFO");
            } else {
                writeLog("WARNING: Could not find the imported image layer", "WARNING");
            }
        } catch (e) {
            writeLog("Error setting active layer to imported image: " + e, "WARNING");
            // Continuer malgré l'erreur
        }
        
        // Retourner les informations des nouvelles cellules
        if (newCells && newCells.length > 0) {
            // À la fin de la fonction, retourner les informations de la première cellule identifiée
            if (firstAddedCell) {
                writeLog("Returning information for the first added cell (ID: " + firstAddedCellId + ")", "INFO");
                writeLog("Cell coordinates: minX=" + firstAddedCell.minX + ", minY=" + firstAddedCell.minY + 
                         ", maxX=" + firstAddedCell.maxX + ", maxY=" + firstAddedCell.maxY, "DEBUG");
                
                // Vérifier le ID réel dans le fichier .board
                var boardCells = readBoardFile(boardPath);
                if (boardCells) {
                    // Chercher la cellule correspondante dans le fichier .board
                    for (var id in boardCells) {
                        if (boardCells.hasOwnProperty(id)) {
                            var boardCell = boardCells[id];
                            
                            // Vérifier si les coordonnées correspondent
                            if (Math.abs(boardCell.bounds.minX - firstAddedCell.minX) < 1 && 
                                Math.abs(boardCell.bounds.maxX - firstAddedCell.maxX) < 1 && 
                                Math.abs(boardCell.bounds.minY - firstAddedCell.minY) < 1 && 
                                Math.abs(boardCell.bounds.maxY - firstAddedCell.maxY) < 1) {
                                firstAddedCellId = id;
                                writeLog("Found matching cell in .board file with ID: " + id, "DEBUG");
                                break;
                            }
                        }
                    }
                }
                
                // Déterminer si une réorganisation a été effectuée
                var wasReorganized = (effectiveDirection === "Right");
                writeLog("Board file reorganization status: " + (wasReorganized ? "reorganized" : "not reorganized"), "INFO");
                
                return {
                    success: true,
                    reorganized: wasReorganized,
                    cellId: String(firstAddedCellId),
                    cell: {
                        minX: firstAddedCell.minX,
                        maxX: firstAddedCell.maxX,
                        minY: firstAddedCell.minY,
                        maxY: firstAddedCell.maxY
                    },
                    useSide: orientationImg === "Portrait" ? "left" : "center" // Par défaut pour une nouvelle cellule
                };
            }
        }
        
        // Aucune cellule créée, retourner un statut de succès avec l'information sur la réorganisation
        writeLog("No cells were created", "DEBUG");
        return {
            success: false,
            reorganized: (effectiveDirection === "Right")
        };
                        } catch (e) {
        writeLog("Error in addCellsToLayout: " + e, "ERROR");
        return null;
    }
}


/**
 * Fonction findEmptyCell pour gérer les cellules Spread et les orientations d'image
 * @param {string} boardPath - Chemin du fichier .board
 * @param {string} orientationImg - Orientation de l'image
 * @param {string} psbPath - Chemin du fichier .psb
 * @param {number} imgMaxHeight - Hauteur maximale de l'image
 * @param {number} imgMaxWidth - Largeur maximale de l'image
 * @param {number} layoutSpacing - Espacement entre les cellules
 * @param {number} marginMask - Masque de marge
 * @param {number} widthImg - Largeur de l'image
 * @param {number} heightImg - Hauteur de l'image
 * @param {boolean} autoPlace - Indique si l'auto placement est activé
 * @param {boolean} createGuide - Indique si la création de guides est activé
 * @param {string} cellType - Type de cellule
 * @param {boolean} overlayMaskOn - Indique si le masque d'overlay est activé
 * @param {boolean} autoExtend - Indique si l'auto extension est activé
 * @param {string} dropZone - Zone de placement
 * @param {number} layoutWidth - Largeur du layout
 * @param {string} extensionDirection - Direction d'extension
 * @param {string} effectiveOrientation - Orientation effective de l'image
 * @param {Object} progressInfo - Informations de progression
 * @param {Document} doc - Document actif
 * @param {string} landscapeMode - Mode paysage
 * @returns {Object} - Objet contenant les informations de la cellule trouvée
 */
function findEmptyCell(boardPath, orientationImg, psbPath, imgMaxHeight, imgMaxWidth, layoutSpacing, marginMask, widthImg, heightImg, autoPlace, createGuide, cellType,overlayMaskOn, autoExtend, dropZone, layoutWidth, extensionDirection, progressInfo, doc, landscapeMode) {
    try {
        writeLog("====== START findEmptyCell ======", "DEBUG");
        
        // Si l'image est en paysage et qu'on est en mode single pour les paysages, la traiter comme une image portrait
        var effectiveOrientation = orientationImg;
        if (orientationImg === "Landscape" && landscapeMode === "single" && cellType === "Spread") {
            effectiveOrientation = "Portrait";
            writeLog("Landscape image in single mode: treating as Portrait", "INFO");
        }
       
        writeLog("Image orientation: " + orientationImg + " (effective: " + effectiveOrientation + ")", "DEBUG");
        writeLog("Image dimensions: " + widthImg + "x" + heightImg, "DEBUG");
        writeLog("Cell type: " + cellType, "DEBUG");
        
        // Vérifier que le document est valide
        if (!doc) {
            writeLog("ERROR: No active document provided", "ERROR");
            return null;
        }

        // Lire les coordonnées du layout
        var rectangles = readBoardFile(boardPath);
        if (!rectangles || countObjectProperties(rectangles) === 0) {
            writeLog("ERROR: Unable to read layout coordinates", "ERROR");
            return null;
        }

        // Pour les images portrait dans une cellule Spread, vérifier d'abord s'il existe des cellules partiellement remplies
        if (cellType === "Spread" && effectiveOrientation === "Portrait" && gPartiallyFilledCells) {
            writeLog("Checking for partially filled Spread cells first...", "DEBUG");
                        
            var partialCellsCount = countObjectProperties(gPartiallyFilledCells);
            if (partialCellsCount > 0) {
                writeLog("Found " + partialCellsCount + " partially filled cells", "DEBUG");
                
                // Parcourir les cellules partiellement remplies
                for (var pcellId in gPartiallyFilledCells) {
                    if (gPartiallyFilledCells.hasOwnProperty(pcellId)) {
                        var usedSide = gPartiallyFilledCells[pcellId];
                        var availableSide = (usedSide === "left") ? "right" : "left";
                        
                        // Vérifier si la cellule existe dans les rectangles
                        if (rectangles.hasOwnProperty(pcellId)) {
                            var pcell = rectangles[pcellId];
                            
                            // Vérifier que la cellule a des coordonnées valides
                            if (pcell && pcell.hasOwnProperty("bounds")) {
                                writeLog("Found partially filled cell " + pcellId + " with " + availableSide + " side available", "INFO");
                                
                                // Vérifier que le côté disponible est bien vide (double vérification)
                                var samplingPoints = calculateSamplingPoints(pcell, cellType);
                                
                                // Pas besoin de formater les points, la fonction calculateSamplingPoints retourne déjà le bon format
                                // Vérifier si le côté est effectivement vide
                                var samplerResults = checkSamplers(samplingPoints, cellType);
                                var isEmpty = (availableSide === "left") ? samplerResults[0] : samplerResults[1];
                                
                                if (isEmpty) {
                                    writeLog("Confirmed " + availableSide + " side of cell " + pcellId + " is empty", "INFO");
                                    
                                    // Supprimer cette cellule de la liste des cellules partiellement remplies
                                    unregisterPartiallyFilledCell(pcellId);
                                    
                                    // Retourner cette cellule avec le côté disponible
                                    return {
                                        cellId: pcellId,
                                        cell: pcell.bounds,
                                        useSide: availableSide
                                    };
                                } else {
                                    writeLog("Side " + availableSide + " of cell " + pcellId + " is already occupied, removing from registry", "WARNING");
                                    unregisterPartiallyFilledCell(pcellId);
                                }
                            }
                        } else {
                            writeLog("Cell " + pcellId + " not found in layout, removing from registry", "WARNING");
                            unregisterPartiallyFilledCell(pcellId);
                        }
                    }
                }
            }
        }

        // Mise à jour pour indiquer le début de la recherche
        if (gProgressWindow && progressInfo) {
            updateProgressBar(null, progressInfo, 
                null, // Garder le message d'en-tête existant
                null, // Garder le nom de fichier existant
                "Searching for an empty cell..."
            );
        }

        // Variable pour suivre si nous avons trouvé une cellule avec au moins un côté libre
        var foundFreeSide = false;

        // Créer un tableau ordonné des IDs de cellules pour pouvoir commencer à partir de gLastProcessedCellId
        var cellIds = [];
        var layoutInfo = getLayoutCoordinates(boardPath);
        var nbrCols = layoutInfo ? layoutInfo.nbrCols : 3; // Valeur par défaut si non disponible
        
        // Créer un tableau temporaire avec les informations de position de chaque cellule
        var cellsWithPosition = [];
        for (var cellId in rectangles) {
            if (rectangles.hasOwnProperty(cellId)) {
                var cell = rectangles[cellId];
                var numericId = parseInt(cellId);
                
                // Calculer la ligne et la colonne basées sur l'ID et le nombre de colonnes
                var row = Math.ceil(numericId / nbrCols);
                var col = ((numericId - 1) % nbrCols) + 1;
                
                cellsWithPosition.push({
                    id: cellId,
                    row: row,
                    col: col,
                    y: cell.bounds.minY,
                    x: cell.bounds.minX
                });
            }
        }
        
        // Trier d'abord par Y (ligne) puis par X (colonne)
        cellsWithPosition.sort(function(a, b) {
            if (Math.abs(a.y - b.y) < 1) { // Si même ligne (tolérance de 1 pixel)
                return a.x - b.x; // Trier par position X
            }
            return a.y - b.y; // Sinon trier par position Y
        });
        
        // Extraire les IDs dans l'ordre trié
        cellIds = [];
        for (var i = 0; i < cellsWithPosition.length; i++) {
            cellIds.push(cellsWithPosition[i].id);
        }
        
        writeLog("Cells sorted by grid position (row by row, left to right)", "DEBUG");
        
        // Trouver l'index de départ si gFirstFreeCellId est défini
        var startIndex = 0;
        if (gFirstFreeCellId !== null) {
            var lastIndex = -1;
            // Parcourir le tableau pour trouver l'index
            for (var j = 0; j < cellIds.length; j++) {
                if (cellIds[j] === gFirstFreeCellId) {
                    lastIndex = j;
                    break;
                }
            }
            if (lastIndex !== -1) {
                startIndex = lastIndex;
                writeLog("Starting search from first free cell ID: " + gFirstFreeCellId, "INFO");
            }
        }

        // Parcourir les cellules pour trouver une cellule vide, en commençant par startIndex
        for (var i = startIndex; i < cellIds.length; i++) {
            // Mettre à jour la barre de progression secondaire
            if (gProgressWindow && progressInfo) {
                var searchProgress = Math.round((i - startIndex) / (cellIds.length - startIndex) * 100);
                updateProgressBar(null, progressInfo, 
                    null, // Garder le message d'en-tête existant
                    null, // Garder le nom de fichier existant
                    "Checking cell " + cellIds[i] + "...",
                    searchProgress
                );
            }

            var cellId = cellIds[i];
            var cell = rectangles[cellId];
            
            writeLog("\n--- Checking cell " + cellId + " ---", "DEBUG");
            
            // Vérifier que la cellule a des coordonnées valides
            if (!cell || !cell.hasOwnProperty("topLeft") || !cell.hasOwnProperty("topRight") || 
                !cell.hasOwnProperty("bottomLeft") || !cell.hasOwnProperty("bottomRight") || 
                !cell.hasOwnProperty("bounds")) {
                writeLog("Incomplete cell, skipped", "DEBUG");
                continue;
            }
            
            var bounds = cell.bounds;
            var minX = bounds.minX;
            var maxX = bounds.maxX;
            var minY = bounds.minY;
            var maxY = bounds.maxY;
            
            writeLog("Cell limits: " + stringify(bounds), "DEBUG");
            
            // Vérifier que la cellule est dans les limites du document
            if (minX < 0 || minY < 0 || maxX > doc.width.value || maxY > doc.height.value) {
                writeLog("Cell out of bounds, skipped", "DEBUG");
                continue;
            }
            
            // Calculer les points d'échantillonnage
            var samplingPoints = calculateSamplingPoints(cell, cellType);
            if (!samplingPoints) {
                writeLog("Unable to calculate sampling points, cell skipped", "WARNING");
                continue;
            }
                   
            // Vérifier si la cellule est vide
            var samplerResults = checkSamplers(samplingPoints, cellType);
            var leftEmpty = samplerResults[0];
            var rightEmpty = samplerResults[1];
            
            writeLog("Sampling results - Left: " + leftEmpty + ", Right: " + rightEmpty, "DEBUG");
            
            // Si c'est la première cellule avec au moins un côté libre et que nous n'avons pas encore trouvé de cellule libre
            if (!foundFreeSide && (leftEmpty || rightEmpty)) {
                foundFreeSide = true;
                gFirstFreeCellId = cellId;
                writeLog("First cell with free side found: " + gFirstFreeCellId, "DEBUG");
            }
            
            // Déterminer si la cellule est utilisable selon le type et l'orientation
            var cellIsUsable = false;
            var useSide = "left"; // Côté par défaut pour les cellules Spread avec image portrait
            
            if (cellType === "Single") {
                // Pour une cellule Single, elle est utilisable si elle est vide
                cellIsUsable = leftEmpty;
                writeLog("Single cell " + (cellIsUsable ? "available" : "not available"), "DEBUG");
            } else if (cellType === "Spread") {
                if (effectiveOrientation === "Landscape") {
                    // Image paysage dans cellule Spread: besoin des deux côtés vides
                    cellIsUsable = leftEmpty && rightEmpty;
                    writeLog("Spread cell for landscape image " + (cellIsUsable ? "available" : "not available"), "DEBUG");
                } else { // Portrait
                    // Image portrait dans cellule Spread: besoin d'un seul côté vide
                    if (leftEmpty && rightEmpty) {
                        // Si les deux côtés sont libres, toujours utiliser le côté gauche pour les images portrait
                        cellIsUsable = true;
                        useSide = "left"; // Toujours privilégier le côté gauche
                        writeLog("Spread cell with both sides free, using left side (default)", "DEBUG");
                    } else if (leftEmpty) {
                        cellIsUsable = true;
                        useSide = "left";
                        writeLog("Spread cell with left side free", "DEBUG");
                    } else if (rightEmpty) {
                        cellIsUsable = true;
                        useSide = "right";
                        writeLog("Spread cell with right side free", "DEBUG");
                    } else {
                        cellIsUsable = false;
                        writeLog("Spread cell fully occupied", "DEBUG");
                    }
                }
            }
            
            // Si la cellule est utilisable, la retourner
            if (cellIsUsable) {
                writeLog("Cell " + cellId + " selected as target", "INFO");
                
                // Mettre à jour gLastProcessedCellId pour la prochaine recherche
                gLastProcessedCellId = cellId;
                writeLog("Updated last processed cell ID to: " + gLastProcessedCellId, "DEBUG");
                
                // Si c'est une cellule Spread et une image portrait,
                // et qu'un seul côté est utilisé, l'enregistrer comme partiellement remplie
                if (cellType === "Spread" && effectiveOrientation === "Portrait") {
                    registerPartiallyFilledCell(cellId, useSide);
                    writeLog("Registered cell " + cellId + " as partially filled with " + useSide + " side used", "INFO");
                }
                
                return {
                    cellId: cellId,
                    cell: bounds,
                    useSide: useSide
                };
            }
        }
        
        // Si aucune cellule vide n'est trouvée et autoExtend est activé, ajouter des cellules
        if (autoExtend) {
            // Mise à jour du message de progression
            if (gProgressWindow && progressInfo) {
                updateProgressBar(null, progressInfo, 
                    null, // Garder le message d'en-tête existant
                    null, // Garder le nom de fichier existant
                    "Extending layout..."
                );
            }
            
            writeLog("No empty cell found. AutoExtend activated, attempting to extend layout...", "INFO");
            
            // Obtenir les informations du layout
            var layoutInfo = getLayoutCoordinates(boardPath);
            if (!layoutInfo) {
                writeLog("Unable to get layout information for extension", "ERROR");
                return null;
            }
            
            // Déterminer la direction d'extension
            if (!extensionDirection || (extensionDirection !== "Bottom" && extensionDirection !== "Right" && extensionDirection !== "Alternate")) {
                extensionDirection = "Bottom"; // Direction par défaut
                writeLog("Extension direction not specified or invalid, using 'Bottom'", "WARNING");
            }
            
            // Ajouter des cellules
            var extensionSuccess = addCellsToLayout(
                layoutInfo.cellsData, layoutInfo.nbrCurrentCells, layoutInfo.nbrRows, layoutInfo.nbrCols,
                psbPath, imgMaxHeight, imgMaxWidth, layoutSpacing, marginMask, boardPath,
                autoPlace, createGuide, cellType, overlayMaskOn,
                widthImg, dropZone, layoutWidth, extensionDirection, effectiveOrientation, progressInfo
            );
            
            if (extensionSuccess) {
                writeLog("Extension successful, searching for empty cell again...", "INFO");
                
                // Vérifier si une réorganisation a eu lieu
                var wasReorganized = extensionSuccess.reorganized;
                
                // Si l'extension a réussi et a retourné des informations de cellule, les utiliser directement
                if (extensionSuccess.success && extensionSuccess.cellId && extensionSuccess.cell) {
                    writeLog("Using cell information directly from extension result: " + extensionSuccess.cellId, "INFO");
                    
                    // Mettre à jour gLastProcessedCellId pour la prochaine recherche
                    gLastProcessedCellId = extensionSuccess.cellId;
                    writeLog("Updated last processed cell ID to: " + gLastProcessedCellId, "DEBUG");
                    
                    // Mettre à jour gFirstFreeCellId car cette cellule est libre
                    gFirstFreeCellId = extensionSuccess.cellId;
                    writeLog("Updated first free cell ID to: " + gFirstFreeCellId, "DEBUG");
                    
                    return {
                        cellId: extensionSuccess.cellId,
                        cell: extensionSuccess.cell,
                        useSide: extensionSuccess.useSide || (effectiveOrientation === "Portrait" ? "left" : "center")
                    };
                }
                
                // Recharger les coordonnées du layout avec les nouvelles cellules
                var newRectangles;
                
                if (wasReorganized) {
                    writeLog("Board file was reorganized, reloading complete layout information", "INFO");
                    // Relire toutes les informations du layout après réorganisation
                    var updatedLayoutInfo = getLayoutCoordinates(boardPath);
                    if (!updatedLayoutInfo) {
                        writeLog("Unable to get updated layout information after reorganization", "ERROR");
                        return null;
                    }
                    newRectangles = updatedLayoutInfo.coordinates;
                    // Mettre à jour les variables locales avec les nouvelles informations
                    layoutInfo = updatedLayoutInfo;
                } else {
                    // Si pas de réorganisation, simplement relire les rectangles
                    newRectangles = readBoardFile(boardPath);
                }
                
                if (!newRectangles || countObjectProperties(newRectangles) === 0) {
                    writeLog("Unable to read layout coordinates after extension", "ERROR");
                    return null;
                }
                
                writeLog("Number of cells after extension: " + countObjectProperties(newRectangles), "DEBUG");
                
                // Chercher la première cellule ajoutée (par ID numérique le plus bas parmi les nouvelles cellules)
                var oldCellCount = layoutInfo.nbrCurrentCells - 1; // Soustraire 1 car nous avons ajouté une cellule
                var lowestNewId = Number.MAX_VALUE;
                var firstAddedCell = null;
                
                for (var cellId in newRectangles) {
                    if (newRectangles.hasOwnProperty(cellId)) {
                        var numericId = parseInt(cellId);
                        if (!isNaN(numericId) && numericId > oldCellCount && numericId < lowestNewId) {
                            lowestNewId = numericId;
                            firstAddedCell = newRectangles[cellId];
                        }
                    }
                }

                if (firstAddedCell) {
                    writeLog("First added cell found by ID: " + lowestNewId, "DEBUG");
                    
                    // Mettre à jour gLastProcessedCellId pour la prochaine recherche
                    gLastProcessedCellId = String(lowestNewId);
                    writeLog("Updated last processed cell ID to: " + gLastProcessedCellId, "DEBUG");
                    
                    // Mettre à jour gFirstFreeCellId car cette cellule est libre
                    gFirstFreeCellId = String(lowestNewId);
                    writeLog("Updated first free cell ID to: " + gFirstFreeCellId, "DEBUG");
                    
                    // Retourner la première cellule ajoutée
                    return {
                        cellId: String(lowestNewId),
                        cell: firstAddedCell.bounds,
                        useSide: effectiveOrientation === "Portrait" ? "left" : "center" // Default for a new cell
                    };
                } else {
                    writeLog("No added cell found after extension", "WARNING");
                }
            } else {
                writeLog("Layout extension failed", "ERROR");
            }
        }
        
        writeLog("No empty cell found", "WARNING");
        writeLog("====== END findEmptyCell (no cell found) ======", "DEBUG");
        return null;
    } catch (e) {
        writeLog("ERROR in findEmptyCell: " + e, "ERROR");
        writeLog("====== END findEmptyCell (error) ======", "ERROR");
        return null;
    }
}

/**
 * Fonction putInBoard pour gérer les cellules Spread et les orientations d'image
 * @param {string} psbPath - Chemin du fichier .psb
 * @param {string} boardPath - Chemin du fichier .board
 * @param {string} imgPath - Chemin du fichier image à placer
 * @param {number} imgMaxHeight - Hauteur maximale de l'image
 * @param {number} imgMaxWidth - Largeur maximale de l'image
 * @param {number} layoutSpacing - Espacement entre les cellules
 * @param {number} marginMask - Masque de marge
 * @param {boolean} autoPlace - Indique si l'auto placement est activé
 * @param {boolean} createGuide - Indique si la création de guides est activé
 * @param {string} cellType - Type de cellule
 * @param {boolean} overlayMaskOn - Indique si le masque d'overlay est activé
 * @param {boolean} autoExtend - Indique si l'auto extension est activé
 * @param {string} dropZone - Zone de placement
 * @param {number} layoutWidth - Largeur du layout
 * @param {number} layoutHeight - Hauteur du layout
 * @param {boolean} autoMask - Indique si le masque est activé
 * @param {Object} progressInfo - Informations de progression
 * @returns {boolean} - Vrai si le placement a réussi, faux sinon
 */
function putInBoard(psbPath, boardPath, imgPath, imgMaxHeight, imgMaxWidth, layoutSpacing, marginMask, autoPlace, createGuide, cellType, overlayMaskOn, autoExtend, dropZone, layoutWidth, layoutHeight, autoMask, progressInfo) {
    writeLog("====== START putInBoard ======", "DEBUG");
        
    try {
        // Lire landscapeMode depuis les préférences
        var preferences = readPreferencesFromPlist();
        var landscapeMode = getPreferenceValue(preferences, "landscapeMode", "spread");
        var resizeMode = getPreferenceValue(preferences, "resizeMode", "cover");
        writeLog("Landscape mode: " + landscapeMode + ", Resize mode: " + resizeMode, "DEBUG");

        // Créer la barre de progression si elle n'existe pas déjà
        var localProgressInfo = progressInfo;
        if (!gProgressWindow) {
            localProgressInfo = createProgressBar("Placing images", 100);
        }
        
        // Normaliser les chemins de fichiers avec toutes les variantes possibles
        psbPath = normalizePath(psbPath);
        boardPath = normalizePath(boardPath);
        imgPath = normalizePath(imgPath);
        
        // Extraire le dossier de destination
        if (psbPath) {
            var psbFile = new File(psbPath);
            var destFolder = psbFile.parent.fsName;
            setGlobalDestFolder(destFolder);
        }
        
        writeLog("Image to place: " + imgPath, "INFO");
        writeLog("PSB document: " + psbPath, "INFO");
        writeLog("BOARD file: " + boardPath, "INFO");
        
        
        // Vérifier si le document est déjà ouvert ou l'ouvrir
        var doc = null;
        
        // Vérifier si le document est déjà ouvert
        var openDoc = isDocumentAlreadyOpen(psbPath);
        if (openDoc) {
            writeLog("Using already open document: " + psbPath, "INFO");
            doc = openDoc;
            app.activeDocument = doc; // S'assurer que ce document est actif
        } else {
            // Si le document n'est pas ouvert, l'ouvrir
            try {
                writeLog("Document not open, attempting to open: " + psbPath, "INFO");
                doc = app.open(new File(psbPath));
            } catch (e) {
                writeLog("Error opening document: " + e, "ERROR");
                writeLog("====== END putInBoard (document open failed) ======", "ERROR");
                return false;
            }
        }
        
        writeLog("Document opened/activated successfully: " + doc.name, "INFO");
        
        // Obtenir les dimensions du document
        var fullWidth = doc.width.value;
        var fullHeight = doc.height.value;
        writeLog("Document dimensions: " + fullWidth + "x" + fullHeight, "DEBUG");
        
        // Obtenir ou créer le groupe Board Content
        var boardContentGroup;
        try {
            boardContentGroup = doc.layerSets.getByName("Board Content");
            writeLog("Group 'Board Content' found", "DEBUG");
        } catch (e) {
            writeLog("Group 'Board Content' not found, creating group", "INFO");
            boardContentGroup = doc.layerSets.add();
            boardContentGroup.name = "Board Content";
        }
        
        // Créer un nouveau calque pour l'image
        var imgLayer = boardContentGroup.artLayers.add();
        imgLayer.name = "img_" + (new Date()).getTime(); // Nom unique avec timestamp
        
        // Définir le calque actif
        doc.activeLayer = imgLayer;
        
        // Placer le fichier image et obtenir l'orientation
        writeLog("Placing image file: " + imgPath, "INFO");
        var orientationImg = placeFile(imgPath, imgMaxHeight, imgMaxWidth, cellType, landscapeMode, resizeMode, landscapeMode, boardPath);
        if (!orientationImg) {
            writeLog("ERROR: Failed to place image", "ERROR");
            writeLog("====== END putInBoard (placement failed) ======", "ERROR");
            return false;
        }
        
        writeLog("Image orientation after placement: " + orientationImg, "DEBUG");
        
        // Obtenir les dimensions de l'image placée
        var layerBounds = doc.activeLayer.bounds;
        var widthImg = layerBounds[2].value - layerBounds[0].value;
        var heightImg = layerBounds[3].value - layerBounds[1].value;
        writeLog("Dimensions of placed image: " + widthImg + "x" + heightImg, "DEBUG");
        
        
        // L'orientation est déjà correctement déterminée par placeFile
        writeLog("Final image orientation: " + orientationImg, "DEBUG");
        
        // Rendre le calque de l'image temporairement transparent avant de chercher une cellule vide
        // Utiliser l'opacité à 0% au lieu de rendre le calque invisible pour de meilleures performances
        var originalOpacity = doc.activeLayer.opacity;
        doc.activeLayer.opacity = 0;
        
        // Si autoPlace est activé, rechercher une cellule vide
        if (autoPlace) {
            writeLog("AutoPlace activated, searching for an empty cell", "INFO");
            
            // Mettre à jour la barre de progression pour indiquer la recherche
            if (gProgressWindow && localProgressInfo) {
                updateProgressBar(null, localProgressInfo, 
                    null, // Garder le message d'en-tête existant
                    null, // Garder le nom de fichier existant
                    "Searching for an empty cell..."
                );
            }
            
            // Obtenir la direction d'extension à partir des préférences si disponible
            var extensionDirection = "alternate"; // Valeur par défaut
            var preferences = readPreferencesFromPlist();
            if (preferences) {
                extensionDirection = getPreferenceValue(preferences, "extensionDirection", "vertical");
                writeLog("Extension direction read from preferences: " + extensionDirection, "DEBUG");
            }
            
            // Rechercher une cellule vide en passant le statusText et le document actif
            var emptyCell = findEmptyCell(
                boardPath, orientationImg, psbPath, imgMaxHeight, imgMaxWidth, 
                layoutSpacing, marginMask, widthImg, heightImg, autoPlace, 
                createGuide, cellType, overlayMaskOn, 
                autoExtend, dropZone, layoutWidth, extensionDirection, localProgressInfo, doc, landscapeMode
            );
            
            if (emptyCell) {
                writeLog("Empty cell found: " + emptyCell.cellId, "INFO");
                
                
                // Restaurer l'opacité originale du calque avant de le positionner
                doc.activeLayer.opacity = originalOpacity;
                
                // Rafraîchir l'affichage pour montrer l'image (expérience visuelle)
                // app.refresh(); // Commenté pour vitesse maximale
                
                // Placer l'image dans la cellule vide
                try {
                    // Obtenir les coordonnées de la cellule
                    var cellBounds = emptyCell.cell;
                    var useSide = emptyCell.useSide;
                    
                    // Obtenir les dimensions actuelles de l'image
                    var layerBounds = doc.activeLayer.bounds;
                    var widthImg = layerBounds[2].value - layerBounds[0].value;
                    var heightImg = layerBounds[3].value - layerBounds[1].value;
                    
                    // Calculer les coordonnées cibles selon le type de cellule et l'orientation
                    var targetX, targetY;
                    var cellWidth = cellBounds.maxX - cellBounds.minX;
                    var cellHeight = cellBounds.maxY - cellBounds.minY;
                    
                    writeLog("Dimensions of the cell: " + cellWidth + "x" + cellHeight, "DEBUG");
                    writeLog("Cell type: " + cellType + ", side to use: " + useSide, "DEBUG");
                    
                    // Calcul de la position cible basé sur l'orientation et le type de cellule
                    if (cellType === "Single") {
                        // Pour une cellule Single, centrer l'image
                        targetX = cellBounds.minX + (cellWidth - widthImg) / 2;
                        targetY = cellBounds.minY + (cellHeight - heightImg) / 2;
                        writeLog("Image centered in a Single cell", "INFO");
                    } else if (cellType === "Spread") {
                        if (orientationImg === "Landscape" && landscapeMode === "spread") {
                            // Image paysage en mode spread: centrer sur toute la largeur
                            targetX = cellBounds.minX + (cellWidth - widthImg) / 2;
                            targetY = cellBounds.minY + (cellHeight - heightImg) / 2;
                            writeLog("Landscape image centered in a Spread cell (spread mode)", "INFO");
                        } else { // Portrait ou Landscape en mode single
                            // Centrer dans la moitié gauche ou droite
                            var halfWidth = cellWidth / 2;
                            
                            if (useSide === "left") {
                                // Centrer dans la moitié gauche
                                targetX = cellBounds.minX + (halfWidth - widthImg) / 2;
                            } else { // right
                                // Centrer dans la moitié droite
                                targetX = cellBounds.minX + halfWidth + (halfWidth - widthImg) / 2;
                            }
                            
                            targetY = cellBounds.minY + (cellHeight - heightImg) / 2;
                            writeLog("Image centered in the " + useSide + " half of a Spread cell", "INFO");
                        }
                    }
                    
                    // Appliquer la transformation pour positionner l'image
                    var currentX = layerBounds[0].value;
                    var currentY = layerBounds[1].value;
                    var deltaX = targetX - currentX;
                    var deltaY = targetY - currentY;
                    
                    writeLog("Movement: deltaX=" + deltaX + ", deltaY=" + deltaY, "DEBUG");
                    doc.activeLayer.translate(deltaX, deltaY);
                    
                    // Si autoMask est activé, appliquer un masque de fusion
                    if (autoMask) {
                        writeLog("AutoMask activated, creating a merge mask", "INFO");
                        
                        try {
                            // Calculer les coordonnées du masque selon le type de cellule et l'orientation
                            var maskBounds;
                            
                            if (cellType === "Single") {
                                // Masque pour toute la cellule sans marges
                                maskBounds = [
                                    cellBounds.minX,
                                    cellBounds.minY,
                                    cellBounds.maxX,
                                    cellBounds.maxY
                                ];
                            } else if (cellType === "Spread") {
                                var halfWidth = cellWidth / 2;
                                
                                if (orientationImg === "Landscape" && landscapeMode === "spread") {
                                    // Masque pour toute la cellule sans marges en mode spread
                                    maskBounds = [
                                        cellBounds.minX,
                                        cellBounds.minY,
                                        cellBounds.maxX,
                                        cellBounds.maxY
                                    ];
                                } else {
                                    // Portrait ou Landscape en mode single : masque sur une moitié
                                    if (useSide === "left") {
                                        maskBounds = [
                                            cellBounds.minX,
                                            cellBounds.minY,
                                            cellBounds.minX + halfWidth,
                                            cellBounds.maxY
                                        ];
                                    } else { // right
                                        maskBounds = [
                                            cellBounds.minX + halfWidth,
                                            cellBounds.minY,
                                            cellBounds.maxX,
                                            cellBounds.maxY
                                        ];
                                    }
                                }
                            }
                            
                            // Créer la sélection pour le masque
                            if (maskBounds) {
                                doc.selection.select([
                                    [maskBounds[0], maskBounds[1]],
                                    [maskBounds[0], maskBounds[3]],
                                    [maskBounds[2], maskBounds[3]],
                                    [maskBounds[2], maskBounds[1]]
                                ]);
                                
                                // Appliquer le masque
                                var idMk = charIDToTypeID("Mk  ");
                                var desc = new ActionDescriptor();
                                var idNw = charIDToTypeID("Nw  ");
                                var idChnl = charIDToTypeID("Chnl");
                                desc.putClass(idNw, idChnl);
                                var idAt = charIDToTypeID("At  ");
                                var ref = new ActionReference();
                                var idChnl = charIDToTypeID("Chnl");
                                var idChnl = charIDToTypeID("Chnl");
                                var idMsk = charIDToTypeID("Msk ");
                                ref.putEnumerated(idChnl, idChnl, idMsk);
                                desc.putReference(idAt, ref);
                                var idUsng = charIDToTypeID("Usng");
                                var idUsrM = charIDToTypeID("UsrM");
                                var idRvlS = charIDToTypeID("RvlS");
                                desc.putEnumerated(idUsng, idUsrM, idRvlS);
                                executeAction(idMk, desc, DialogModes.NO);
                                
                                // Vérifier si le masque doit être délié du calque
                                var preferences = readPreferencesFromPlist();
                                var linkedMask = getPreferenceValue(preferences, "linkedMask", true); // true par défaut
                                
                                if (!linkedMask) {
                                    writeLog("LinkedMask preference is set to false, unlinking mask", "INFO");
                                    unlinkMask();
                                }
                                
                                // Désélectionner
                                doc.selection.deselect();
                                
                                writeLog("Merge mask applied successfully", "INFO");
                            } else {
                                writeLog("WARNING: Impossible to calculate mask bounds", "WARNING");
                            }
                        } catch (maskError) {
                            writeLog("ERROR during mask creation: " + maskError, "ERROR");
                        }
                    }
                    
                    // Gérer la visibilité du masque simple page pour les cellules Spread
                    if (cellType.toLowerCase() === "spread") {
                        try {
                            // Accéder au groupe Board Elements
                            var boardElements = null;
                            try {
                                boardElements = doc.layerSets.getByName("Board Elements");
                            } catch (e) {
                                writeLog("Group 'Board Elements' not found: " + e, "ERROR");
                            }
                            
                            // Accéder au groupe Simple page Mask
                            var singlePageGroup = null;
                            if (boardElements) {
                                try {
                                    singlePageGroup = boardElements.layerSets.getByName("Simple page Mask");
                                } catch (e) {
                                    writeLog("Group 'Simple page Mask' not found: " + e, "ERROR");
                                }
                            }
                            
                            if (singlePageGroup) {
                                // Vérifier que emptyCell est défini et a un cellId
                                var maskId = "";
                                
                                if (!emptyCell || !emptyCell.cellId) {
                                    writeLog("Adjusting the visibility of the simple page mask", "INFO");
                                    
                                    // Obtenir les informations du layout pour déterminer la structure de la grille
                                    var layoutInfo = getLayoutCoordinates(boardPath);
                                    var existingRows = layoutInfo ? layoutInfo.nbrRows : 0;
                                    var existingCols = layoutInfo ? layoutInfo.nbrCols : 0;
                                    
                                    writeLog("Existing grid structure: " + existingRows + " rows, " + existingCols + " columns", "INFO");
                                    writeLog("GRID STRUCTURE FOR MASK SEARCH - Nombre de colonnes: " + existingCols + ", Nombre de lignes: " + existingRows, "INFO");
                                    
                                    // Déterminer la rangée et la colonne en fonction de la direction d'extension
                                    var row = 1;
                                    var col = 1;
                                    
                                    if (extensionDirection === "Right") {
                                        // Extension horizontale: ajouter une colonne à droite
                                        col = existingCols; 
                                        
                                        // Pour les lignes, utilisez la position réelle dans la grille
                                        row = i + 1; // i commence à 0, donc +1 pour la première ligne
                                        
                                        writeLog("Right extension: using row " + row + " and column " + col, "DEBUG");
                                    } else {
                                        // Extension verticale: ajouter une ligne en bas
                                        row = nbrRows; 
                                        
                                        // Pour les colonnes, utilisez la position réelle dans la grille
                                        col = i + 1; // i commence à 0, donc +1 pour la première colonne
                                        
                                        writeLog("Bottom extension: using row " + row + " and column " + col, "DEBUG");
                                    }
                                    
                                    // Construire l'ID du masque simple page
                                    maskId = "R" + row + "C" + col;
                                    writeLog("Calculated mask ID: " + maskId, "DEBUG");
                                } else {
                                    // Déterminer l'ID du masque simple page en fonction de l'ID de la cellule
                                    var cellParts = emptyCell.cellId.toString().match(/(\d+)/g);
                                    var cellId = parseInt(cellParts[0]);
                                    
                                    // Obtenir les informations du layout pour déterminer la structure de la grille
                                    var layoutInfo = getLayoutCoordinates(boardPath);
                                    var nbrCols = layoutInfo ? layoutInfo.nbrCols : 3; // Valeur par défaut si non disponible
                                    
                                    writeLog("Number of columns in the layout: " + nbrCols, "DEBUG");
                                    writeLog("GRID STRUCTURE FOR EXISTING CELL - Nombre de colonnes: " + nbrCols + ", Nombre de lignes: " + (layoutInfo ? layoutInfo.nbrRows : 0), "INFO");
                                    
                                    // Déterminer la rangée et la colonne en fonction de la structure du layout
                                    var row = Math.ceil(cellId / nbrCols) || 1;
                                    var col = ((cellId - 1) % nbrCols) + 1 || cellId;
                                    
                                    // Construire l'ID du masque simple page
                                    maskId = "R" + row + "C" + col;
                                    
                                    writeLog("Searching for the simple page mask: " + maskId, "DEBUG");
                                }
                                
                                // Parcourir tous les calques du groupe Simple page Mask
                                var foundMask = false;
                                for (var i = 0; i < singlePageGroup.artLayers.length; i++) {
                                    var layer = singlePageGroup.artLayers[i];
                                    
                                    // Si c'est le masque correspondant à notre cellule
                                    if (layer.name === maskId) {
                                        foundMask = true;
                                        
                                        // Pour les images portrait, activer le masque simple page
                                        // Pour les images paysage en mode spread, désactiver le masque
                                        layer.visible = (orientationImg === "Portrait" || (orientationImg === "Landscape" && landscapeMode === "single"));
                                        
                                        if (orientationImg === "Landscape") {
                                            if (landscapeMode === "spread") {
                                                writeLog("Landscape image in spread mode: simple page mask " + maskId + " disabled", "INFO");
                                            } else {
                                                writeLog("Landscape image in single mode: simple page mask " + maskId + " enabled", "INFO");
                                            }
                                        } else {
                                            writeLog("Portrait image: simple page mask " + maskId + " enabled", "INFO");
                                        }
                                        
                                        writeLog("Simple page mask " + maskId + " " + 
                                                (layer.visible ? "enabled" : "disabled") + 
                                                " for image " + effectiveOrientation, "INFO");
                                        
                                        // Sortir de la boucle une fois le masque trouvé et modifié
                                        break;
                                    }
                                    // Ne pas modifier les autres masques
                                }
                                
                                if (!foundMask) {
                                    writeLog("Warning: Simple page mask " + maskId + " not found", "WARNING");
                                }
                            } else {
                                writeLog("Warning: Simple page mask group not found", "WARNING");
                            }
                        } catch (e) {
                            writeLog("Warning: Impossible to define mask visibility: " + e, "WARNING");
                        }
                    }
                    
                    writeLog("Image successfully placed in cell " + emptyCell.cellId, "INFO");
                    
                    // Gérer le registre des cellules partiellement remplies
                    if (cellType === "Spread") {
                        if (effectiveOrientation === "Landscape") {
                            // Une image paysage occupe toute la cellule, donc la supprimer du registre
                            unregisterPartiallyFilledCell(emptyCell.cellId);
                        } else if (effectiveOrientation === "Portrait") {
                            // Vérifier d'abord si cette cellule est déjà dans le registre
                            if (gPartiallyFilledCells && gPartiallyFilledCells[emptyCell.cellId]) {
                                // La cellule était partiellement remplie et va maintenant être complètement remplie
                                unregisterPartiallyFilledCell(emptyCell.cellId);
                                writeLog("Cell " + emptyCell.cellId + " now fully occupied, removed from registry", "INFO");
                            } else {
                                // La cellule n'était pas encore dans le registre, l'ajouter comme partiellement remplie
                                registerPartiallyFilledCell(emptyCell.cellId, emptyCell.useSide);
                                writeLog("Cell " + emptyCell.cellId + " registered as partially filled with " + emptyCell.useSide + " side used", "INFO");
                            }
                        }
                    }
                    
                    writeLog("====== FIN putInBoard (succès) ======", "DEBUG");
                    gProcessedItems++; // Incrémenter le compteur d'images traitées
                    return true;
                } catch (placeError) {
                    writeLog("ERROR during cell placement: " + placeError, "ERROR");
                }
            } else {
                writeLog("No empty cell found for the image", "WARNING");
            }
        }
        
        // Si autoPlace est désactivé ou si aucune cellule n'a été trouvée,
        // centrer l'image dans le document
        try {
            var centerX = (fullWidth - widthImg) / 2;
            var centerY = (fullHeight - heightImg) / 2;
            
            writeLog("Placing image in the center of the document", "INFO");
            
            // Restaurer l'opacité originale avant de centrer
            doc.activeLayer.opacity = originalOpacity;
            
            // Rafraîchir l'affichage pour montrer l'image (expérience visuelle)
            // app.refresh(); // Commenté pour vitesse maximale
            
            var currentX = layerBounds[0].value;
            var currentY = layerBounds[1].value;
            var deltaX = centerX - currentX;
            var deltaY = centerY - currentY;
            
            doc.activeLayer.translate(deltaX, deltaY);
            
            writeLog("Image centered in the document", "INFO");
            writeLog("====== END putInBoard (centering) ======", "DEBUG");
            gProcessedItems++; // Incrémenter le compteur d'images traitées

            // Fermer la barre de progression si elle a été créée ici
            if (localProgressInfo && !progressInfo) {
                closeProgressBar();
            }
            return true;
        } catch (centerError) {
            writeLog("ERROR during image centering: " + centerError, "ERROR");
            writeLog("====== END putInBoard (centering failed) ======", "ERROR");

            // Fermer la barre de progression si elle a été créée ici
            if (localProgressInfo && !progressInfo) {
                closeProgressBar();
            }
            return false;
        }
    } catch (e) {
        // S'assurer de fermer la barre de progression en cas d'erreur
        if (localProgressInfo && !progressInfo) {
            closeProgressBar();
        }
        writeLog("Error in putInBoard: " + e, "ERROR");
        return false;
    }
}

/**
 * Fonction main() avec barre de progression
 * @returns {boolean} - Vrai si le script s'est exécuté avec succès, faux en cas d'erreur
 */
function main() {
    try {
        clearLocalLog();
        writeLog("==== MAIN SCRIPT START ====", "INFO");
        
        // Réinitialiser l'ID de la dernière cellule traitée au démarrage du script
        resetLastProcessedCellId();
        
        // Lire les arguments depuis le fichier
        scriptArguments = readArgumentsFromFile();
        var isInteractiveMode = (countObjectProperties(scriptArguments) === 0);
        
        writeLog("Arguments available: " + stringify(scriptArguments), "DEBUG");
        
        // Lire les préférences depuis le fichier plist
        var preferences = readPreferencesFromPlist();
        
        if (!preferences) {
            writeLog("Impossible to load preferences. Using default values.", "WARNING");
            preferences = {};
        }
        
        // Logger les valeurs importantes récupérées depuis le Plist
        var debugMode = getPreferenceValue(preferences, "DEBUG_MODE", false);
        var landscapeMode = getPreferenceValue(preferences, "landscapeMode", "spread");
        var resizeMode = getPreferenceValue(preferences, "resizeMode", "cover");
        var cellDetectionLevel = getPreferenceValue(preferences, "cellDetectionLevel", 3);
        
        writeLog("=== IMPORTANT PREFERENCES VALUES ===", "INFO");
        writeLog("DEBUG_MODE: " + debugMode, "INFO");
        writeLog("landscapeMode: " + landscapeMode, "INFO");
        writeLog("resizeMode: " + resizeMode, "INFO");
        writeLog("cellDetectionLevel: " + cellDetectionLevel, "INFO");
        writeLog("===================================", "INFO");
        
        // Paramètres par défaut ou chargés depuis les préférences
        var psbPath = getPreferenceValue(preferences, "psbPath", "");
        writeLog("psbPath retrieved from preferences: [" + psbPath + "]", "DEBUG");
        
        var boardPath = "";
        var imgMaxHeight = getPreferenceValue(preferences, "imgMaxHeight", 1080);
        var imgMaxWidth = getPreferenceValue(preferences, "imgMaxWidth", 1920);
        
        // Récupérer le dossier de destination à partir du chemin PSB
        if (psbPath) {
            var psbFile = new File(psbPath);
            var destFolder = psbFile.parent.fsName;
            setGlobalDestFolder(destFolder);
        }
        
        // Calculer le chemin du fichier .board
        var boardPath = "";
        if (psbPath) {
            var psbFile = new File(psbPath);
            var psbName = psbFile.name.replace(/\.psb$/i, "");
            var psbFolder = psbFile.parent.fsName;
            boardPath = psbFolder + "/" + psbName + ".board";
            
            // Vérifier si le fichier .board existe
            if (fileExists(boardPath)) {
                writeLog("Board file found: " + boardPath, "INFO");
            } else {
                // Essayer avec %20 pour les espaces
                boardPath = boardPath.replace(/ /g, "%20");
                if (fileExists(boardPath)) {
                    writeLog("Board file found: " + boardPath, "INFO");
                } else {
                    writeLog("Board file not found: " + boardPath, "WARNING");
                }
            }
        }
        
        // Normaliser les chemins de fichiers
        psbPath = normalizePath(psbPath);
        boardPath = normalizePath(boardPath);
        
        // Utiliser des valeurs par défaut raisonnables pour les dimensions
        if (imgMaxHeight <= 0 || imgMaxWidth <= 0) {
            writeLog("ATTENTION: The cell dimensions are zero or negative, using default values", "WARNING");
            imgMaxHeight = 1920;
            imgMaxWidth = 1000;
        }
        
        // Récupérer l'action à effectuer
        var action = scriptArguments.action || "putInBoard";
        writeLog("Action to perform: " + action, "INFO");
        
        if (action === "putInBoard") {
            // Récupérer les images à traiter
            var imagesToProcess = [];
            
            // Ajouter imgPath s'il existe
            if (scriptArguments.imgPath) {
                imagesToProcess.push(scriptArguments.imgPath);
                writeLog("Main image added: " + scriptArguments.imgPath, "INFO");
            }
            
            // Ajouter tous les fichiers du tableau files
            if (scriptArguments.files && scriptArguments.files.length > 0) {
                for (var i = 0; i < scriptArguments.files.length; i++) {
                    // Éviter les doublons et les chemins vides
                    var currentPath = scriptArguments.files[i];
                    if (currentPath && currentPath.length > 0 && !arrayContains(imagesToProcess, currentPath)) {
                        imagesToProcess.push(currentPath);
                        writeLog("Additional image added: " + currentPath, "DEBUG");
                    }
                }
            }
            
            // Vérifier si nous avons des images à traiter
            if (imagesToProcess.length === 0) {
                writeLog("ERROR: No image path provided for putInBoard action", "ERROR");
                
                // Mode interactif: demander à l'utilisateur de sélectionner des fichiers
                if (isInteractiveMode) {
                    writeLog("Interactive mode: requesting file selection", "INFO");
                    try {
                        // Utiliser File.openDialog avec true pour permettre la sélection de plusieurs fichiers
                        var selectedFiles = File.openDialog("Select images to place:", "Images:*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.psd", true);
                        
                        if (selectedFiles && selectedFiles.length > 0) {
                            for (var j = 0; j < selectedFiles.length; j++) {
                                imagesToProcess.push(selectedFiles[j].fsName);
                                writeLog("Selected image added: " + selectedFiles[j].fsName, "DEBUG");
                            }
                        } else {
                            writeLog("No file selected by user", "INFO");
                            return false;
                        }
                    } catch (e) {
                        writeLog("Error during file selection: " + e, "ERROR");
                        return false;
                    }
                } else {
                    return false;
                }
            }
            
            // Créer la barre de progression
            var totalImages = imagesToProcess.length;
            var progressInfo = createProgressBar("..:: BOARDING ::..", totalImages);
            
            // Initialiser la barre de progression avec le premier message
            if (progressInfo && imagesToProcess.length > 0) {
                var firstImage = imagesToProcess[0];
                updateProgressBar(0, progressInfo, 
                    "Processing image 1 of " + totalImages,
                    File.decode(firstImage.split("/").pop()),
                    "Initializing..."
                );
            }
            
            // Extraire les paramètres restants
            var layoutSpacing = parseFloat(getPreferenceValue(preferences, "layoutSpacing", "20"));
            var marginMask = parseFloat(getPreferenceValue(preferences, "marginMask", "10"));
            var autoPlace = Boolean(getPreferenceValue(preferences, "autoPlace", true));
            var createGuide = Boolean(getPreferenceValue(preferences, "createGuide", false));
            var cellType = getPreferenceValue(preferences, "cellType", "Single");
            var overlayMaskOn = Boolean(getPreferenceValue(preferences, "overlayMaskOn", false));
            var autoExtend = Boolean(getPreferenceValue(preferences, "autoExtend", true));
            var dropZone = Boolean(getPreferenceValue(preferences, "dropZone", false));
            var layoutWidth = parseFloat(getPreferenceValue(preferences, "layoutWidth", "0"));
            var layoutHeight = parseFloat(getPreferenceValue(preferences, "layoutHeight", "0"));
            var autoMask = Boolean(getPreferenceValue(preferences, "autoMask", true));
            var overlayMaskOn = Boolean(getPreferenceValue(preferences, "overlayMaskOn", false));
            
            // Surcharger avec les valeurs des arguments si elles existent
            if (scriptArguments.hasOwnProperty("layoutSpacing")) layoutSpacing = parseFloat(scriptArguments.layoutSpacing);
            if (scriptArguments.hasOwnProperty("marginMask")) marginMask = parseFloat(scriptArguments.marginMask);
            if (scriptArguments.hasOwnProperty("autoPlace")) autoPlace = (scriptArguments.autoPlace === "true");
            if (scriptArguments.hasOwnProperty("createGuide")) createGuide = (scriptArguments.createGuide === "true");
            if (scriptArguments.hasOwnProperty("cellType")) cellType = scriptArguments.cellType;
            if (scriptArguments.hasOwnProperty("overlayMaskOn")) overlayMaskOn = (scriptArguments.overlayMaskOn === "true");
            if (scriptArguments.hasOwnProperty("autoExtend")) autoExtend = (scriptArguments.autoExtend === "true");
            if (scriptArguments.hasOwnProperty("dropZone")) dropZone = (scriptArguments.dropZone === "true");
            if (scriptArguments.hasOwnProperty("layoutWidth")) layoutWidth = parseFloat(scriptArguments.layoutWidth);
            if (scriptArguments.hasOwnProperty("layoutHeight")) layoutHeight = parseFloat(scriptArguments.layoutHeight);
            if (scriptArguments.hasOwnProperty("autoMask")) autoMask = (scriptArguments.autoMask === "true");
            if (scriptArguments.hasOwnProperty("overlayMaskOn")) overlayMaskOn = (scriptArguments.overlayMaskOn === "true");
            
            // Normaliser les chemins de fichiers
            psbPath = normalizePath(psbPath);
            boardPath = normalizePath(boardPath);
            
            // Afficher les paramètres finaux
            writeLog("==== FINAL PARAMETERS UPDATED ====", "INFO");
            writeLog("psbPath: " + psbPath, "INFO");
            writeLog("boardPath: " + boardPath, "INFO");
            writeLog("imgMaxHeight: " + imgMaxHeight + ", imgMaxWidth: " + imgMaxWidth, "INFO");
            writeLog("cellType: " + cellType + ", autoPlace: " + autoPlace, "INFO");
            writeLog("createGuide: " + createGuide + ", autoMask: " + autoMask, "INFO");
            writeLog("layoutWidth: " + layoutWidth + ", layoutHeight: " + layoutHeight, "INFO");
            writeLog("overlayMaskOn: " + overlayMaskOn, "INFO");
            writeLog("==========================", "DEBUG");
            
            // Traiter les fichiers selon l'action
            if (scriptArguments.action === "putInBoard") {
                // Traiter les fichiers un par un
                var results = [];
                
                // Si imgPath est spécifié, l'utiliser comme fichier principal
                if (scriptArguments.imgPath) {
                    // Normaliser le chemin avec toutes les variantes possibles
                    scriptArguments.imgPath = normalizePath(scriptArguments.imgPath);
                    writeLog("Main image added: " + scriptArguments.imgPath, "INFO");
                    
                    // Ne pas remplacer le tableau files, mais s'assurer que imgPath est inclus
                    if (!scriptArguments.files) {
                        scriptArguments.files = [scriptArguments.imgPath];
                    } else if (!arrayContains(scriptArguments.files, scriptArguments.imgPath)) {
                        // Ajouter imgPath au début du tableau s'il n'y est pas déjà
                        scriptArguments.files.unshift(scriptArguments.imgPath);
                    }
                }
                
                // Traiter chaque fichier
                for (var i = 0; i < imagesToProcess.length; i++) {
                    // Vérifier si l'opération a été annulée
                    if (isProgressCancelled()) {
                        writeLog("Operation cancelled by user", "INFO");
                        break;
                    }
                    
                    var imgPath = imagesToProcess[i];
                    // Normaliser le chemin avec toutes les variantes possibles
                    imgPath = normalizePath(imgPath);
                    
                    // Mettre à jour la barre de progression avec les informations principales
                    updateProgressBar(i, progressInfo, 
                        "Processing image " + (i+1) + " of " + imagesToProcess.length, 
                        File.decode(imgPath.split("/").pop()),
                        "Importing image ..."
                    );
                    
                    writeLog("==== PROCESSING IMAGE " + (i+1) + "/" + imagesToProcess.length + " ====", "INFO");
                    writeLog("File: " + imgPath, "INFO");
                    
                    // Placer l'image dans le document Photoshop
                    var startTime = new Date().getTime();
                    var result = putInBoard(
                        psbPath, boardPath, imgPath, imgMaxHeight, imgMaxWidth, layoutSpacing, marginMask,
                        autoPlace, createGuide, cellType, overlayMaskOn, autoExtend,
                        dropZone, layoutWidth, layoutHeight, autoMask, progressInfo, 
                    );
                    var endTime = new Date().getTime();
                    var executionTime = endTime - startTime;
                    
                    // Enregistrer le résultat
                    results.push({
                        file: imgPath,
                        success: result !== null,
                        executionTime: executionTime
                    });
                    
                    writeLog("Processing result: " + (result !== null ? "Success" : "Failure"), "INFO");
                    writeLog("Execution time: " + executionTime + " ms", "DEBUG");
                }
                
                // Fermer la barre de progression
                closeProgressBar();
                
                // Écrire le rapport de traitement
                writeProcessingReport(results);
                
                writeLog("Processing completed for folder: " + destFolder, "INFO");
                
                // Sauvegarder le document à la fin du traitement
                var saveResult = savePS(psbPath);
                if (saveResult) {
                    writeLog("Document saved successfully after processing", "INFO");
                } else {
                    writeLog("WARNING: Failed to save document after processing", "WARNING");
                }
                
                logExecutionTime();
                writeLog("==== MAIN SCRIPT END (putInBoard) ====", "INFO");
                
                return true;
            }
            
            return false;
        } else if (action === "savePS") {
            var result = savePS(psbPath);
            logExecutionTime();
            writeLog("==== MAIN SCRIPT END (savePS) ====", "INFO");
            return result;
        } else if (action === "closePS") {
            var result = closePS(psbPath);
            logExecutionTime();
            writeLog("==== MAIN SCRIPT END (closePS) ====", "INFO");
            return result;
        } else {
            writeLog("Action non reconnue: " + action, "ERROR");
            logExecutionTime();
            writeLog("==== MAIN SCRIPT END (unknown action) ====", "INFO");
            return false;
        }
    } catch (e) {
        // S'assurer que la barre de progression est fermée en cas d'erreur
        closeProgressBar();
        
        writeLog("Critical error in main execution: " + e, "ERROR");
        logExecutionTime();
        writeLog("==== MAIN SCRIPT END (error) ====", "ERROR");
        return false;
    }
}

// Charger la configuration des logs au démarrage
loadLogConfiguration();
// Exécuter la fonction principale
try {
    main();
    } catch (e) {
        writeLog("Critical error in main execution: " + e, "ERROR");
    }
