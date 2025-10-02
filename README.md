# Open Board - GIMP Scripts

**Open Board** est un ensemble de scripts Python pour GIMP qui permettent de créer, gérer et organiser des planches d'images (boards) de manière professionnelle. Parfait pour les portfolios, les mood boards, les planches de référence ou toute présentation d'images organisée.

![GIMP Version](https://img.shields.io/badge/GIMP-2.10%2B-purple)
![Python](https://img.shields.io/badge/Python-2.7-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 🎯 Fonctionnalités

### 1. **Create Board** - Création de planches
- Création de grilles de cellules personnalisables (colonnes × lignes)
- Support des modes **Single** et **Spread** (double page)
- Redimensionnement automatique pour optimiser l'espace
- Gestion des marges, espacements et bordures
- Support des overlays (masques décoratifs)
- Ajout de logo et légende personnalisables
- Génération automatique de guides
- Création d'un fichier `.board` contenant les métadonnées

### 2. **Import Images** - Import d'images
- Import par dossier (toutes les images)
- Import d'image unique
- Import par pattern (ex: `IMG_*.jpg`)
- Placement automatique dans les cellules vides
- Gestion intelligente de l'orientation (portrait/paysage)
- Modes de redimensionnement : **fit**, **cover**, **noResize**
- Extension automatique du board si nécessaire
- Masques de cellule automatiques

### 3. **Add Image Names** - Ajout de noms
- Ajout automatique des noms de fichiers sous chaque image
- Police, taille et couleur personnalisables
- Positionnement intelligent selon le type de cellule
- Support des modes Single et Spread

## 📦 Installation

### Prérequis
- GIMP 2.10 ou supérieur
- Python 2.7 (inclus avec GIMP)

### Installation des scripts

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

## 🚀 Utilisation

### Workflow complet

#### 1️⃣ Créer un nouveau board

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

#### 2️⃣ Importer des images

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

#### 3️⃣ Ajouter les noms des images (optionnel)

1. Dans votre board ouvert, allez dans : **File → Open Board → Add Image Names...**

2. Configurez le texte :
   - **Police** : Choisissez votre police
   - **Taille** : En pixels
   - **Couleur** : Couleur du texte
   - **Distance** : Espace entre la cellule et le texte

3. Cliquez sur **OK**

✅ Les noms de fichiers apparaissent sous chaque image

## 📁 Structure du projet

```
OpenBoard/
├── src/
│   ├── createOpenBoard.py      # Création de boards
│   ├── importOpenBoard.py      # Import d'images
│   └── addImageNames.py        # Ajout de noms
├── README.md                   # Ce fichier
└── LICENSE                     # Licence MIT
```

## 🔧 Format du fichier .board

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

## 🎨 Cas d'usage

- **Portfolios photographiques** : Créez des planches professionnelles
- **Mood boards** : Organisez vos références visuelles
- **Contact sheets** : Prévisualisations organisées
- **Planches de storyboard** : Pour l'animation ou le cinéma
- **Catalogues produits** : Présentations de collections
- **Planches de personnages** : Pour le design de jeu vidéo

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Signaler des bugs
- Proposer de nouvelles fonctionnalités
- Soumettre des pull requests

## 📝 Changelog

### Version 1.0 (2025)
- ✅ Création de boards avec grilles personnalisables
- ✅ Import d'images avec placement automatique
- ✅ Ajout de noms d'images
- ✅ Support des modes Single et Spread
- ✅ Extension automatique de boards
- ✅ Support des overlays
- ✅ Changement d'extension : `.dit` → `.board`
- ✅ Menu unifié : File → Open Board

## 📄 Licence

MIT License - voir le fichier LICENSE pour plus de détails

## 👤 Auteur

**Yan Senez**

## 🙏 Remerciements

Merci à Claude (Anthropic) pour l'assistance au développement et la conversion depuis les scripts Photoshop originaux.

---

**Note** : Ces scripts ont été développés pour GIMP 2.10 avec Python 2.7 (Python-Fu). Ils utilisent l'API GIMP Python-Fu qui n'est pas disponible en dehors de l'environnement GIMP.

