# Open Board - GIMP Scripts

[English](#english) | [Français](#français)

---

<a name="english"></a>
## 🇬🇧 English

**Open Board** is the open-source version of [**Board**](https://github.com/Igrekess/BOARD) (which works integrated with Capture One and Photoshop/InDesign and still in beta/dev). It's a set of Python scripts for GIMP that allow you to create, manage, and organize image boards professionally. Perfect for portfolios, mood boards, reference sheets, or any organized image presentation.

![GIMP Version](https://img.shields.io/badge/GIMP-2.10%2B-purple)
![Python](https://img.shields.io/badge/Python-2.7-blue)
![License](https://img.shields.io/badge/license-MIT-green)

### Features

#### 1. **Create Board** - Board Creation
- Customizable cell grid creation (columns × rows)
- Support for **Single** and **Spread** (double-page) modes
- Automatic resizing for space optimization
- Margin, spacing, and border management
- Overlay support (decorative masks)
- Customizable logo and caption addition
- Automatic guide generation
- `.board` file generation containing metadata

#### 2. **Import Images** - Image Import ⚡ **10-15x faster!**
- Import by folder (all images)
- Single image import
- Pattern-based import (e.g., `IMG_*.jpg`)
- Automatic placement in empty cells
- **NEW: Session cache for 10-15x performance improvement**
- Intelligent orientation handling (portrait/landscape)
- Resize modes: **fit**, **cover**, **noResize**
- Automatic board extension if needed
- Automatic cell masks
- Real-time performance metrics in logs

#### 3. **Add Image Names** - Name Addition
- Automatic filename addition below each image
- Customizable font, size, and color
- Intelligent positioning based on cell type
- Support for Single and Spread modes

### Installation

#### Prerequisites
- GIMP 2.10 or higher
- Python 2.7 (included with GIMP)
- Python 3 (for the installer script)

#### 🚀 Quick Install (Recommended)

**macOS / Linux:**
```bash
cd /path/to/OPENBOARD
./install.sh
```

**Windows:**
```cmd
cd C:\path\to\OPENBOARD
install.bat
```

The installer will:
- ✓ Check if GIMP is installed (offer to download if not)
- ✓ Automatically locate your GIMP plugin directory
- ✓ Copy all scripts to the correct location
- ✓ Set proper permissions

👉 **For detailed installation instructions, see [INSTALL.md](INSTALL.md)**

#### 📦 Manual Installation

1. **Download the scripts** from this repository

2. **Copy ALL the files** to the GIMP scripts folder (⚠️ including `openboard_common.py`):
   
   **macOS:**
   ```bash
   ~/Library/Application Support/GIMP/2.10/plug-ins/
   ```
   
   **Linux:**
   ```bash
   ~/.config/GIMP/2.10/plug-ins/
   ```
   
   **Windows:**
   ```
   C:\Users\[YourName]\AppData\Roaming\GIMP\2.10\plug-ins\
   ```

3. **Make scripts executable** (macOS/Linux):
   ```bash
   chmod +x openboard_common.py
   chmod +x createOpenBoard.py
   chmod +x importOpenBoard.py
   chmod +x addImageNames.py
   ```

   **⚠️ IMPORTANT:** `openboard_common.py` MUST be in the same directory as the other scripts!

4. **Restart GIMP**

Scripts will appear in the menu: **File → Open Board**

### Usage

#### Complete Workflow

##### 1️⃣ Create a New Board

1. In GIMP (main window), go to: **File → Open Board → Create Board...**

2. Configure your board:
   - **Project Name**: `MyPortfolio`
   - **Destination Folder**: Choose where to save
   - **Canvas**: Dimensions and resolution (e.g., A3 at 300 DPI)
   - **Grid**: Number of rows and columns
   - **Cell Type**: Single or Spread
   - **Cell Dimensions**: Width, height, margins
   - **Colors**: Background, borders, masks
   - **Extras**: Logo, caption, overlays

3. Click **OK**

✅ An `.xcf` file and a `.board` file are created

##### 2️⃣ Import Images

1. Open your board (the `.xcf` file)

2. Go to: **File → Open Board → Import Images...**

3. Configure the import:
   - **Import Mode**: Folder, Single Image, or Pattern
   - **Source**: Select your folder/file
   - **Cell Type**: Must match your board (Single/Spread)
   - **Resize mode**:
     - `fit`: Image fits entirely in the cell
     - `cover`: Image fills the cell (may be cropped)
     - `noResize`: Original size
   - **Auto-extend**: Automatically adds rows/columns if needed
   - **Direction**: Bottom, Right, or Alternate

4. Click **OK**

✅ Images are automatically placed in cells

##### 3️⃣ Add Image Names (Optional)

1. In your open board, go to: **File → Open Board → Add Image Names...**

2. Configure the text:
   - **Font**: Choose your font
   - **Size**: In pixels
   - **Color**: Text color
   - **Distance**: Space between cell and text

3. Click **OK**

✅ Filenames appear below each image

### 📁 Project Structure

```
OpenBoard/
├── src/
│   ├── openboard_common.py     # ⚡ Shared utilities & performance cache (v2.0)
│   ├── createOpenBoard.py      # Board creation with validation
│   ├── importOpenBoard.py      # Image import (10-15x faster!)
│   ├── addImageNames.py        # Name addition with error handling
│   └── test_common.py          # Test script for openboard_common
├── install.py                  # Installation script (Python)
├── install.sh                  # Installation script (macOS/Linux)
├── install.bat                 # Installation script (Windows)
├── README.md                   # This file
├── INSTALL.md                  # Detailed installation guide
├── REFACTORING_SUMMARY.md      # v2.0 refactoring details
└── LICENSE                     # MIT License
```

### 🔧 .board File Format

`.board` files are text files containing:

```
# Board Layout File
#boardName=MyBoard
#nbrCols=3
#nbrRows=4
#cellWidth=800
#cellHeight=600
#cellType=spread
#adjustedMargin=20
1,100,100,100,700,900,700,900,100
2,920,100,920,700,1720,700,1720,100
...
```

Each cell line contains: `index,topLeftX,topLeftY,bottomLeftX,bottomLeftY,bottomRightX,bottomRightY,topRightX,topRightY`

### Use Cases

- **Photography Portfolios**: Create professional boards
- **Mood Boards**: Organize your visual references
- **Contact Sheets**: Organized previews
- **Storyboards**: For animation or cinema
- **Product Catalogs**: Collection presentations
- **Character Sheets**: For video game design

### Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Propose new features
- Submit pull requests

### Changelog

#### Version 2.0 (October 2025) - Performance & Refactoring 🚀
- ⚡ **Performance**: Import 10-15x faster with session cache system
- 🔧 **Refactoring**: Shared code in `openboard_common.py` module
- ✅ **Validation**: Robust parameter checking with clear error messages
- 📚 **Documentation**: Complete docstrings for all functions (100%)
- 🐛 **Reliability**: Improved error handling with specific exception types
- 🔍 **Logging**: Performance metrics in logs (cache build time, import speed)
- 🧹 **Code Quality**: Eliminated ~400 lines of duplicated code
- ⚙️ **Default**: Auto-extend enabled by default for better UX

#### Version 1.0 (2025)
- ✅ Board creation with customizable grids
- ✅ Image import with automatic placement
- ✅ Image name addition
- ✅ Single and Spread mode support
- ✅ Automatic board extension
- ✅ Overlay support
- ✅ Extension change: `.dit` → `.board`
- ✅ Unified menu: File → Open Board

### License

MIT License - see LICENSE file for details

### Author

**Yan Senez**

---

**Note**: These scripts were developed for GIMP 2.10 with Python 2.7 (Python-Fu). They use the GIMP Python-Fu API which is not available outside the GIMP environment.

---

<a name="français"></a>
## 🇫🇷 Français

**Open Board** est la version open source de [**Board**](https://github.com/Igrekess/BOARD) (qui fonctionne en intégration avec Capture One et Photoshop/InDesign, et qui est toujours en beta/dev). Il s'agit d'un ensemble de scripts Python pour GIMP qui permettent de créer, gérer et organiser des planches d'images (boards) de manière professionnelle. Parfait pour les portfolios, les mood boards, les planches de référence ou toute présentation d'images organisée.

![GIMP Version](https://img.shields.io/badge/GIMP-2.10%2B-purple)
![Python](https://img.shields.io/badge/Python-2.7-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Fonctionnalités

#### 1. **Create Board** - Création de planches
- Création de grilles de cellules personnalisables (colonnes × lignes)
- Support des modes **Single** et **Spread** (double page)
- Redimensionnement automatique pour optimiser l'espace
- Gestion des marges, espacements et bordures
- Support des overlays (masques décoratifs)
- Ajout de logo et légende personnalisables
- Génération automatique de guides
- Création d'un fichier `.board` contenant les métadonnées

#### 2. **Import Images** - Import d'images ⚡ **10-15x plus rapide !**
- Import par dossier (toutes les images)
- Import d'image unique
- Import par pattern (ex: `IMG_*.jpg`)
- Placement automatique dans les cellules vides
- **NOUVEAU : Cache de session pour gain de performance 10-15x**
- Gestion intelligente de l'orientation (portrait/paysage)
- Modes de redimensionnement : **fit**, **cover**, **noResize**
- Extension automatique du board si nécessaire
- Masques de cellule automatiques
- Métriques de performance en temps réel dans les logs

#### 3. **Add Image Names** - Ajout de noms
- Ajout automatique des noms de fichiers sous chaque image
- Police, taille et couleur personnalisables
- Positionnement intelligent selon le type de cellule
- Support des modes Single et Spread

### Installation

#### Prérequis
- GIMP 2.10 ou supérieur
- Python 2.7 (inclus avec GIMP)
- Python 3 (pour le script d'installation)

#### 🚀 Installation rapide (Recommandé)

**macOS / Linux :**
```bash
cd /chemin/vers/OPENBOARD
./install.sh
```

**Windows :**
```cmd
cd C:\chemin\vers\OPENBOARD
install.bat
```

Le programme d'installation va :
- ✓ Vérifier si GIMP est installé (propose le téléchargement sinon)
- ✓ Localiser automatiquement votre dossier de plugins GIMP
- ✓ Copier tous les scripts au bon endroit
- ✓ Définir les permissions appropriées

👉 **Pour des instructions détaillées, voir [INSTALL.md](INSTALL.md)**

#### 📦 Installation manuelle

1. **Téléchargez les scripts** depuis ce dépôt

2. **Copiez les fichiers** dans le dossier des scripts GIMP :
   
   **macOS :**
   ```bash
   ~/Library/Application Support/GIMP/2.10/plug-ins/
   ```
   
   **Linux :**
   ```bash
   ~/.config/GIMP/2.10/plug-ins/
   ```
   
   **Windows :**
   ```
   C:\Users\[VotreNom]\AppData\Roaming\GIMP\2.10\plug-ins\
   ```

3. **Rendez les scripts exécutables** (macOS/Linux) :
   ```bash
   chmod +x createOpenBoard.py
   chmod +x importOpenBoard.py
   chmod +x addImageNames.py
   ```

4. **Redémarrez GIMP**

Les scripts apparaîtront dans le menu : **File → Open Board**

### 🚀 Utilisation

#### Workflow complet

##### 1️⃣ Créer un nouveau board

1. Dans GIMP (fenêtre principale), allez dans : **File → Open Board → Create Board...**

2. Configurez votre board :
   - **Nom du projet** : `MonPortfolio`
   - **Dossier de destination** : Choisissez où sauvegarder
   - **Canvas** : Dimensions et résolution (ex: A3 à 300 DPI)
   - **Grille** : Nombre de lignes et colonnes
   - **Type de cellule** : Single ou Spread
   - **Dimensions des cellules** : Largeur, hauteur, marges
   - **Couleurs** : Fond, bordures, masques
   - **Extras** : Logo, légende, overlays

3. Cliquez sur **OK**

✅ Un fichier `.xcf` et un fichier `.board` sont créés

##### 2️⃣ Importer des images

1. Ouvrez votre board (le fichier `.xcf`)

2. Allez dans : **File → Open Board → Import Images...**

3. Configurez l'import :
   - **Mode d'import** : Folder, Single Image, ou Pattern
   - **Source** : Sélectionnez votre dossier/fichier
   - **Type de cellule** : Doit correspondre à votre board (Single/Spread)
   - **Resize mode** :
     - `fit` : L'image tient entièrement dans la cellule
     - `cover` : L'image remplit la cellule (peut être rognée)
     - `noResize` : Taille originale
   - **Auto-extend** : Ajoute automatiquement des lignes/colonnes si nécessaire
   - **Direction** : Bottom, Right ou Alternate

4. Cliquez sur **OK**

✅ Les images sont placées automatiquement dans les cellules

##### 3️⃣ Ajouter les noms des images (optionnel)

1. Dans votre board ouvert, allez dans : **File → Open Board → Add Image Names...**

2. Configurez le texte :
   - **Police** : Choisissez votre police
   - **Taille** : En pixels
   - **Couleur** : Couleur du texte
   - **Distance** : Espace entre la cellule et le texte

3. Cliquez sur **OK**

✅ Les noms de fichiers apparaissent sous chaque image

### 📁 Structure du projet

```
OpenBoard/
├── src/
│   ├── createOpenBoard.py      # Création de boards
│   ├── importOpenBoard.py      # Import d'images
│   └── addImageNames.py        # Ajout de noms
├── install.py                  # Script d'installation (Python)
├── install.sh                  # Script d'installation (macOS/Linux)
├── install.bat                 # Script d'installation (Windows)
├── README.md                   # Ce fichier
├── INSTALL.md                  # Guide d'installation détaillé
└── LICENSE                     # Licence MIT
```

### 🔧 Format du fichier .board

Les fichiers `.board` sont des fichiers texte contenant :

```
# Board Layout File
#boardName=MonBoard
#nbrCols=3
#nbrRows=4
#cellWidth=800
#cellHeight=600
#cellType=spread
#adjustedMargin=20
1,100,100,100,700,900,700,900,100
2,920,100,920,700,1720,700,1720,100
...
```

Chaque ligne de cellule contient : `index,topLeftX,topLeftY,bottomLeftX,bottomLeftY,bottomRightX,bottomRightY,topRightX,topRightY`

### Cas d'usage

- **Portfolios photographiques** : Créez des planches professionnelles
- **Mood boards** : Organisez vos références visuelles
- **Contact sheets** : Prévisualisations organisées
- **Planches de storyboard** : Pour l'animation ou le cinéma
- **Catalogues produits** : Présentations de collections
- **Planches de personnages** : Pour le design de jeu vidéo

### Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Signaler des bugs
- Proposer de nouvelles fonctionnalités
- Soumettre des pull requests

### Changelog

#### Version 2.0 (Octobre 2025) - Performance & Refactorisation 🚀
- ⚡ **Performance** : Import 10-15x plus rapide avec système de cache de session
- 🔧 **Refactorisation** : Code partagé dans le module `openboard_common.py`
- ✅ **Validation** : Vérification robuste des paramètres avec messages d'erreur clairs
- 📚 **Documentation** : Docstrings complètes pour toutes les fonctions (100%)
- 🐛 **Fiabilité** : Gestion d'erreurs améliorée avec types d'exceptions spécifiques
- 🔍 **Logs** : Métriques de performance dans les logs (temps cache, vitesse import)
- 🧹 **Qualité** : Élimination de ~400 lignes de code dupliqué
- ⚙️ **Défaut** : Extension automatique activée par défaut pour meilleure UX

#### Version 1.0 (2025)
- ✅ Création de boards avec grilles personnalisables
- ✅ Import d'images avec placement automatique
- ✅ Ajout de noms d'images
- ✅ Support des modes Single et Spread
- ✅ Extension automatique de boards
- ✅ Support des overlays
- ✅ Changement d'extension : `.dit` → `.board`
- ✅ Menu unifié : File → Open Board

### Licence

MIT License - voir le fichier LICENSE pour plus de détails

### Auteur

**Yan Senez**

---

**Note** : Ces scripts ont été développés pour GIMP 2.10 avec Python 2.7 (Python-Fu). Ils utilisent l'API GIMP Python-Fu qui n'est pas disponible en dehors de l'environnement GIMP.