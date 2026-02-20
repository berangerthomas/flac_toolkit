# Instructions d'amélioration pour FLAC Toolkit

## Contexte du projet

FLAC Toolkit est un outil Python en ligne de commande pour l'analyse, la réparation et la normalisation ReplayGain de fichiers audio FLAC. Le projet est structuré en modules (analyzer, repair, reporter, replaygain, utils) avec un point d'entrée principal (main.py).

**Architecture actuelle:**
- `analyzer.py` : Analyse structurelle (headers, métadonnées, compatibilité)
- `repair.py` : Réparation par ré-encodage (flac/ffmpeg) et renommage
- `replaygain.py` : Calcul et application de tags ReplayGain 2.0
- `reporter.py` : Affichage formaté des résultats
- `utils.py` : Utilitaires de recherche de fichiers

## 1. Méthodes de réparation FLAC avancées

### 1.1 Réparation granulaire au niveau frame

**Objectif:** Réparer les fichiers corrompus sans ré-encoder entièrement.

**Implémentation suggérée:**

Créer un nouveau module `flac_toolkit/frame_repair.py`:

```python
class FrameRepairer:
    """Répare les frames FLAC corrompues individuellement."""
    
    def analyze_frames(self, file_path: Path) -> List[FrameInfo]:
        """
        Parse toutes les frames et vérifie leur intégrité (CRC16).
        Retourne une liste avec statut de chaque frame.
        """
        pass
    
    def interpolate_corrupted_frame(self, prev_frame: bytes, next_frame: bytes) -> bytes:
        """
        Reconstruit une frame corrompue par interpolation des frames adjacentes.
        Utilise une interpolation linéaire sur les échantillons décodés.
        """
        pass
    
    def repair_selective(self, file_path: Path, corrupted_frames: List[int]) -> Path:
        """
        Répare uniquement les frames identifiées comme corrompues.
        Reconstruction du fichier FLAC avec frames interpolées.
        """
        pass
```

**Intégration dans analyzer.py:**

Ajouter une méthode `_analyze_frame_integrity()` qui:
- Parse chaque frame audio (sync code: 0xFFF8)
- Vérifie les CRC16 de chaque frame
- Identifie les frames avec CRC invalides
- Ajoute des erreurs spécifiques: `"Frame Error: Frame #X has invalid CRC (position: Y)"`

**Intégration dans repair.py:**

Ajouter une action de réparation `'repair_frames'` avant le ré-encodage complet:
```python
def repair_frames(self, file_path: Path, frame_errors: List[int]) -> Path | None:
    """Tente de réparer les frames corrompues sans ré-encoder."""
    pass
```

### 1.2 Validation et correction des checksums

**Objectif:** Recalculer les CRC et MD5 après réparation.

**Implémentation:**

Dans `frame_repair.py`, ajouter:

```python
def recalculate_streaminfo_md5(self, file_path: Path) -> bool:
    """
    Décode l'intégralité du fichier FLAC, calcule le MD5 des échantillons,
    et met à jour le bloc STREAMINFO.
    """
    pass

def verify_frame_crcs(self, file_path: Path) -> Dict[int, bool]:
    """Vérifie tous les CRC16 des frames. Retourne {frame_num: is_valid}."""
    pass
```

**Intégration dans analyzer.py:**

Ajouter dans `_analyze_data_structure()`:
```python
# Vérification MD5
if hasattr(audio_info, 'md5_signature'):
    # Calculer MD5 réel et comparer
    if calculated_md5 != audio_info.md5_signature:
        analysis['errors'].append("MD5 mismatch: file may be corrupted")
```

### 1.3 Réparation des blocs de métadonnées

**Objectif:** Reconstruire les blocs corrompus (STREAMINFO, SEEKTABLE).

**Implémentation dans `metadata_repair.py`:**

```python
class MetadataRepairer:
    def reconstruct_streaminfo(self, file_path: Path) -> bytes:
        """
        Reconstruit un bloc STREAMINFO en analysant toutes les frames.
        Calcule: min/max blocksize, min/max framesize, sample_rate, channels, etc.
        """
        pass
    
    def rebuild_seektable(self, file_path: Path, interval_samples: int = 44100) -> bytes:
        """
        Reconstruit une SEEKTABLE en parsant le fichier.
        Crée des points de recherche à intervalles réguliers.
        """
        pass
    
    def remove_corrupted_blocks(self, file_path: Path, block_types: List[int]) -> Path:
        """Supprime les blocs de métadonnées corrompus spécifiés."""
        pass
```

**Intégration dans analyzer.py:**

Améliorer `_analyze_metadata_blocks()`:
```python
# Détecter STREAMINFO manquant ou corrompu
if not any(b['type'] == 0 for b in blocks):
    errors.append("Critical: STREAMINFO block missing")

# Détecter SEEKTABLE corrompue
for block in blocks:
    if block['type'] == 3:  # SEEKTABLE
        if block['length'] % 18 != 0:
            errors.append("SEEKTABLE has invalid size")
```

## 2. Réparation bas niveau (agnostique du format)

### 2.1 Récupération de fragments (carving)

**Objectif:** Extraire des données FLAC valides d'un fichier partiellement corrompu.

**Créer `flac_toolkit/file_carving.py`:**

```python
class FlacCarver:
    FLAC_SIGNATURE = b'fLaC'
    FRAME_SYNC = b'\xff\xf8'
    
    def find_flac_signatures(self, file_path: Path) -> List[int]:
        """Trouve toutes les occurrences de 'fLaC' dans le fichier."""
        pass
    
    def find_frame_boundaries(self, file_path: Path, start_offset: int) -> List[int]:
        """Identifie les débuts de frames FLAC (sync code)."""
        pass
    
    def extract_valid_fragment(self, file_path: Path, start: int, end: int) -> bytes:
        """Extrait un fragment de fichier entre deux offsets."""
        pass
    
    def reconstruct_from_fragments(self, fragments: List[bytes]) -> Path:
        """
        Tente de reconstruire un fichier FLAC à partir de multiples fragments.
        Réassemble les métadonnées et frames valides.
        """
        pass
```

**Intégration:**

Ajouter un mode `carve` dans `main.py`:
```python
def carve_mode(target_paths: List[Path]):
    """Mode de récupération pour fichiers sévèrement corrompus."""
    carver = FlacCarver()
    for file_path in find_flac_files(target_paths):
        fragments = carver.find_flac_signatures(file_path)
        if len(fragments) > 1:
            # Fichier fragmenté détecté
            recovered = carver.reconstruct_from_fragments(...)
```

### 2.2 Détection et correction de bitflips

**Objectif:** Corriger les erreurs de 1-bit dans les headers/métadonnées.

**Implémentation dans `analyzer.py`:**

```python
def _detect_bitflip_candidates(self, block_header: bytes) -> List[Tuple[int, bytes]]:
    """
    Teste des variations à 1-bit du header pour trouver des valeurs valides.
    Utile pour détecter des corruptions minimales.
    """
    candidates = []
    for byte_pos in range(len(block_header)):
        for bit_pos in range(8):
            # Flip le bit
            modified = bytearray(block_header)
            modified[byte_pos] ^= (1 << bit_pos)
            # Vérifier si le résultat est valide
            if self._is_valid_block_header(bytes(modified)):
                candidates.append((byte_pos * 8 + bit_pos, bytes(modified)))
    return candidates
```

### 2.3 Analyse d'entropie pour zones corrompues

**Créer `flac_toolkit/entropy_analysis.py`:**

```python
import numpy as np

class EntropyAnalyzer:
    def calculate_entropy(self, data: bytes, window_size: int = 1024) -> np.ndarray:
        """
        Calcule l'entropie de Shannon sur des fenêtres glissantes.
        L'entropie anormalement haute/basse indique corruption.
        """
        pass
    
    def detect_corrupted_regions(self, file_path: Path) -> List[Tuple[int, int]]:
        """
        Identifie les régions avec entropie anormale.
        Retourne [(start_offset, end_offset), ...]
        """
        pass
    
    def visualize_entropy(self, file_path: Path, output_png: Path):
        """Génère un graphique de l'entropie le long du fichier."""
        pass
```

## 3. Nouveaux outils et modules

### 3.1 Module de validation stricte

**Créer `flac_toolkit/validator.py`:**

```python
class StrictValidator:
    """Validation stricte selon la spécification FLAC."""
    
    def validate_streaminfo(self, streaminfo: bytes) -> List[str]:
        """Vérifie la cohérence des valeurs STREAMINFO."""
        errors = []
        # min_blocksize <= max_blocksize
        # min_framesize <= max_framesize (si != 0)
        # sample_rate valide (1Hz - 655350Hz)
        # channels valide (1-8)
        # bits_per_sample valide (4-32)
        return errors
    
    def validate_vorbis_comments(self, comments: Dict) -> List[str]:
        """Vérifie la validité des tags Vorbis Comment."""
        pass
    
    def validate_picture_block(self, picture_data: bytes) -> List[str]:
        """Vérifie l'intégrité des images embarquées."""
        pass
```

**Intégration:**

Ajouter `--strict` flag pour analyse poussée:
```python
parser.add_argument("--strict", action="store_true", 
                    help="Enable strict FLAC specification validation")
```

### 3.2 Module de métadonnées avancé

**Créer `flac_toolkit/metadata_manager.py`:**

```python
class MetadataManager:
    def export_metadata(self, file_path: Path, output_format: str = 'json') -> Path:
        """Exporte tous les tags dans un fichier (JSON, YAML, CSV)."""
        pass
    
    def import_metadata(self, file_path: Path, metadata_file: Path):
        """Importe des tags depuis un fichier externe."""
        pass
    
    def normalize_tags(self, file_path: Path, rules: Dict):
        """
        Normalise les tags selon des règles:
        - Capitalisation cohérente
        - Suppression d'espaces superflus
        - Conversion de caractères
        """
        pass
    
    def extract_embedded_images(self, file_path: Path, output_dir: Path):
        """Extrait toutes les images PICTURE vers des fichiers."""
        pass
    
    def embed_image(self, file_path: Path, image_path: Path, picture_type: int = 3):
        """Ajoute une image (cover art) au fichier FLAC."""
        pass
```

**Nouveau mode dans main.py:**

```python
def metadata_mode(target_paths: List[Path], args):
    """Mode de gestion des métadonnées."""
    manager = MetadataManager()
    if args.export:
        # Export vers JSON/CSV
    elif args.import_file:
        # Import depuis fichier
    elif args.normalize:
        # Normalisation
```

### 3.3 Module d'analyse qualité audio

**Créer `flac_toolkit/quality_analyzer.py`:**

```python
class QualityAnalyzer:
    def detect_clipping(self, file_path: Path) -> Dict:
        """
        Détecte les échantillons clippés (valeurs max/min).
        Retourne: {'clipped_samples': int, 'percentage': float}
        """
        pass
    
    def calculate_dynamic_range(self, file_path: Path) -> float:
        """
        Calcule le Dynamic Range (DR) selon la méthode EBU R128.
        Utile pour détecter les fichiers sur-compressés.
        """
        pass
    
    def detect_silence(self, file_path: Path, threshold_db: float = -60) -> List[Tuple[float, float]]:
        """
        Identifie les sections silencieuses.
        Retourne [(start_time, end_time), ...]
        """
        pass
    
    def analyze_spectrum(self, file_path: Path) -> Dict:
        """
        Analyse spectrale pour détecter:
        - Coupure de fréquences (lossy transcodes)
        - Contenu ultrasonique suspect
        - Ratio signal/bruit
        """
        pass
    
    def detect_lossy_transcode(self, file_path: Path) -> bool:
        """
        Détecte si le fichier est probablement un transcode depuis un format lossy.
        Cherche des coupures spectrales caractéristiques (16kHz, 18kHz, 20kHz).
        """
        pass
```

**Intégration:**

Ajouter un mode `quality` dans main.py:
```python
def quality_mode(target_paths: List[Path]):
    """Analyse de qualité audio détaillée."""
    analyzer = QualityAnalyzer()
    for file_path in find_flac_files(target_paths):
        clipping = analyzer.detect_clipping(file_path)
        dr = analyzer.calculate_dynamic_range(file_path)
        is_transcode = analyzer.detect_lossy_transcode(file_path)
        # Afficher rapport
```

### 3.4 Module de checksums et vérification

**Créer `flac_toolkit/checksum_manager.py`:**

```python
import hashlib

class ChecksumManager:
    def generate_checksums(self, file_path: Path) -> Dict[str, str]:
        """Génère MD5, SHA256, SHA512 du fichier."""
        pass
    
    def verify_accuraterip(self, file_path: Path, offset: int = 0) -> Dict:
        """
        Calcule le checksum AccurateRip pour vérification CD rip.
        Nécessite connaissance du offset de lecteur.
        """
        pass
    
    def create_checksum_file(self, directory: Path, algorithm: str = 'sha256'):
        """
        Crée un fichier de checksums pour tous les FLAC d'un répertoire.
        Format: <hash> *<filename>
        """
        pass
    
    def verify_checksums(self, checksum_file: Path) -> List[Dict]:
        """
        Vérifie l'intégrité des fichiers contre un fichier de checksums.
        Retourne liste des fichiers avec statut (OK, FAILED, MISSING).
        """
        pass
```

### 3.5 Module de batch processing avancé

**Améliorer `utils.py` ou créer `batch_processor.py`:**

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

class BatchProcessor:
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or (os.cpu_count() or 1)
    
    def process_parallel(self, files: List[Path], operation: callable) -> List[Any]:
        """
        Traite une liste de fichiers en parallèle avec barre de progression.
        """
        results = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(operation, f): f for f in files}
            with tqdm(total=len(files), desc="Processing") as pbar:
                for future in as_completed(futures):
                    results.append(future.result())
                    pbar.update(1)
        return results
    
    def create_processing_queue(self, files: List[Path], priorities: Dict[Path, int]):
        """Crée une file d'attente avec priorités."""
        pass
    
    def resume_from_checkpoint(self, checkpoint_file: Path):
        """Reprend un traitement interrompu."""
        pass
```

**Intégration:**

Ajouter flags dans main.py:
```python
parser.add_argument("--parallel", type=int, metavar="N",
                    help="Process files in parallel using N workers")
parser.add_argument("--checkpoint", type=Path,
                    help="Checkpoint file for resumable operations")
```

### 3.6 Module de conversion et optimisation

**Créer `flac_toolkit/converter.py`:**

```python
class FlacConverter:
    def change_compression_level(self, file_path: Path, level: int = 8) -> Path:
        """
        Re-compresse avec un niveau différent (0-8).
        Aucune perte, juste optimisation de taille.
        """
        pass
    
    def resample(self, file_path: Path, target_rate: int) -> Path:
        """
        Ré-échantillonne vers un sample rate différent.
        Utilise SoX ou ffmpeg avec resampler de qualité.
        """
        pass
    
    def convert_bit_depth(self, file_path: Path, target_bits: int) -> Path:
        """Convertit vers une profondeur de bits différente (16/24/32)."""
        pass
    
    def convert_to_wav(self, file_path: Path) -> Path:
        """Décode vers WAV sans perte."""
        pass
    
    def convert_from_wav(self, wav_path: Path, compression: int = 8) -> Path:
        """Encode un WAV vers FLAC."""
        pass
```

### 3.7 Amélioration du reporter avec exports

**Améliorer `reporter.py`:**

```python
import json
import csv
from datetime import datetime

class Reporter:
    # ... méthodes existantes ...
    
    @staticmethod
    def export_to_json(results: List[Dict], output_file: Path):
        """Export des résultats en JSON."""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def export_to_csv(results: List[Dict], output_file: Path):
        """Export des résultats en CSV."""
        pass
    
    @staticmethod
    def generate_html_report(results: List[Dict], output_file: Path):
        """
        Génère un rapport HTML interactif avec:
        - Statistiques globales
        - Graphiques (avec plotly ou matplotlib)
        - Tableau filtrable des fichiers
        """
        pass
    
    @staticmethod
    def create_repair_log(operations: List[Dict], output_file: Path):
        """
        Crée un log détaillé des opérations de réparation:
        - Timestamp
        - Fichier traité
        - Actions effectuées
        - Résultat
        """
        pass
```

**Intégration:**

```python
parser.add_argument("--export", choices=['json', 'csv', 'html'],
                    help="Export analysis results to file")
parser.add_argument("--output", type=Path, help="Output file path for export")
```

### 3.8 Module de surveillance (watch mode)

**Créer `flac_toolkit/watcher.py`:**

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FlacWatcher(FileSystemEventHandler):
    def __init__(self, action: callable):
        self.action = action
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.flac'):
            self.action(Path(event.src_path))
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.flac'):
            self.action(Path(event.src_path))

def watch_directory(directory: Path, mode: str):
    """
    Surveille un répertoire et applique automatiquement l'action spécifiée
    sur les nouveaux fichiers FLAC.
    """
    pass
```

**Usage:**

```bash
python main.py watch /path/to/downloads --action analyze
python main.py watch /path/to/downloads --action auto-repair
```

### 3.9 Module de visualisation

**Créer `flac_toolkit/visualizer.py`:**

```python
import matplotlib.pyplot as plt
import numpy as np

class FlacVisualizer:
    def plot_waveform(self, file_path: Path, output_path: Path):
        """Génère un graphique de la forme d'onde."""
        pass
    
    def plot_spectrogram(self, file_path: Path, output_path: Path):
        """Génère un spectrogramme."""
        pass
    
    def plot_file_structure(self, file_path: Path, output_path: Path):
        """
        Visualise la structure du fichier:
        - Blocs de métadonnées (proportionnels à leur taille)
        - Données audio
        - Zones corrompues identifiées
        """
        pass
    
    def plot_library_statistics(self, results: List[Dict], output_path: Path):
        """
        Génère des graphiques de statistiques:
        - Distribution des sample rates
        - Distribution des bit depths
        - Tailles de fichiers
        - États de santé
        """
        pass
```

## 4. Améliorations de l'architecture existante

### 4.1 Amélioration de l'analyzer

**Dans `analyzer.py`, ajouter:**

```python
def _analyze_cue_sheet(self, audio: FLAC) -> List[str]:
    """Analyse les blocs CUESHEET si présents."""
    warnings = []
    # Vérifier cohérence des timestamps
    # Valider le format CUESHEET
    return warnings

def _analyze_application_blocks(self, blocks: List[Dict]) -> List[str]:
    """Analyse les blocs APPLICATION pour détecter corruptions."""
    pass

def _check_file_truncation(self, file_path: Path, audio_info) -> bool:
    """
    Détecte si le fichier semble tronqué:
    - Comparer taille attendue vs réelle
    - Vérifier présence de frame finale valide
    """
    pass

def _deep_scan_audio_frames(self, file_path: Path) -> Dict:
    """
    Parse et valide chaque frame audio:
    - Vérification CRC16
    - Cohérence des headers de frame
    - Détection de frames manquantes
    """
    pass
```

**Améliorer la détection de problèmes:**

```python
# Dans _check_android_compatibility, ajouter plus de cas:
if audio_info.bits_per_sample == 32:
    warnings.append("Android: 32-bit depth rarely supported")

# Ajouter vérification de paramètres exotiques
if audio_info.sample_rate not in [44100, 48000, 88200, 96000, 176400, 192000]:
    warnings.append(f"Non-standard sample rate: {audio_info.sample_rate}Hz")
```

### 4.2 Amélioration du repairer

**Dans `repair.py`, ajouter:**

```python
def verify_repair(self, original: Path, repaired: Path) -> Dict:
    """
    Vérifie que la réparation a fonctionné:
    - Compare durées
    - Vérifie lecture sans erreur
    - Compare spectres (optionnel)
    """
    verification = {'success': False, 'errors': []}
    try:
        orig_audio = FLAC(original)
        rep_audio = FLAC(repaired)
        
        # Vérifier durée
        duration_diff = abs(orig_audio.info.length - rep_audio.info.length)
        if duration_diff > 0.1:
            verification['errors'].append(f"Duration mismatch: {duration_diff}s")
        
        # Vérifier paramètres audio
        if (orig_audio.info.sample_rate != rep_audio.info.sample_rate or
            orig_audio.info.channels != rep_audio.info.channels):
            verification['errors'].append("Audio parameters changed")
        
        if not verification['errors']:
            verification['success'] = True
    except Exception as e:
        verification['errors'].append(str(e))
    
    return verification

def create_backup(self, file_path: Path) -> Path:
    """Crée une backup avant réparation."""
    backup_path = file_path.with_suffix('.flac.backup')
    shutil.copy2(file_path, backup_path)
    return backup_path

def rollback_repair(self, original_backup: Path):
    """Restaure depuis backup en cas d'échec."""
    original_path = Path(str(original_backup).replace('.flac.backup', '.flac'))
    shutil.move(original_backup, original_path)
```

**Ajouter flag de sécurité:**

```python
parser.add_argument("--backup", action="store_true",
                    help="Create backups before repair")
parser.add_argument("--verify", action="store_true",
                    help="Verify repairs after completion")
```

### 4.3 Amélioration du ReplayGain

**Dans `replaygain.py`, ajouter:**

```python
def remove_replaygain_tags(self, file_path: Path):
    """Supprime tous les tags ReplayGain existants."""
    pass

def calculate_r128_loudness(self, file_path: Path) -> Dict:
    """
    Calcule loudness selon EBU R128 (plus complet que LUFS simple):
    - Integrated loudness
    - Loudness range (LRA)
    - True peak
    """
    pass

def apply_r128_tags(self, file_path: Path, r128_data: Dict):
    """Applique les tags R128 (norme moderne)."""
    pass

def validate_existing_replaygain(self, file_path: Path) -> Dict:
    """
    Vérifie si les tags ReplayGain existants sont cohérents:
    - Recalcule et compare
    - Détecte tags incorrects
    """
    pass
```

**Mode supplémentaire:**

```python
parser.add_argument("--remove-rg", action="store_true",
                    help="Remove existing ReplayGain tags")
parser.add_argument("--r128", action="store_true",
                    help="Use EBU R128 instead of ReplayGain 2.0")
parser.add_argument("--verify-rg", action="store_true",
                    help="Verify existing ReplayGain tags")
```

## 5. Dépendances Python supplémentaires

Ajouter dans `pyproject.toml` ou `requirements.txt`:

```
# Existantes
mutagen
unidecode
soundfile
pyloudnorm
numpy

# Nouvelles suggérées
tqdm              # Barres de progression
watchdog          # Surveillance de répertoires
matplotlib        # Visualisations
scipy             # Traitement du signal (interpolation, etc.)
acoustid          # Fingerprinting audio (nécessite fpcalc)
pyyaml            # Export YAML
jinja2            # Templates HTML pour rapports
plotly            # Graphiques interactifs HTML
colorama          # Couleurs dans terminal
click             # Alternative à argparse (plus moderne)
pydub             # Manipulation audio additionnelle
librosa           # Analyse audio avancée (spectrogrammes, etc.)
```

## 6. Structure de projet améliorée

```
flac_toolkit/
├── __init__.py
├── analyzer.py              # Existant, à améliorer
├── repair.py                # Existant, à améliorer
├── replaygain.py            # Existant, à améliorer
├── reporter.py              # Existant, à améliorer
├── utils.py                 # Existant, à améliorer
├── frame_repair.py          # NOUVEAU: réparation granulaire
├── metadata_repair.py       # NOUVEAU: réparation métadonnées
├── file_carving.py          # NOUVEAU: récupération fragments
├── entropy_analysis.py      # NOUVEAU: analyse entropie
├── validator.py             # NOUVEAU: validation stricte
├── metadata_manager.py      # NOUVEAU: gestion métadonnées
├── quality_analyzer.py      # NOUVEAU: analyse qualité
├── checksum_manager.py      # NOUVEAU: checksums
├── batch_processor.py       # NOUVEAU: traitement parallèle
├── converter.py             # NOUVEAU: conversions
├── watcher.py               # NOUVEAU: surveillance
├── visualizer.py            # NOUVEAU: visualisations
└── config.py                # NOUVEAU: configuration centralisée

main.py                      # À étendre avec nouveaux modes
tests/                       # À créer: tests unitaires
├── test_analyzer.py
├── test_repair.py
├── test_frame_repair.py
└── fixtures/                # Fichiers FLAC de test
docs/                        # Documentation
└── usage_examples.md
```

## 7. Configuration centralisée

**Créer `flac_toolkit/config.py`:**

```python
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class FlacToolkitConfig:
    # Chemins d'outils externes
    flac_binary: str = "flac"
    ffmpeg_binary: str = "ffmpeg"
    sox_binary: str = "sox"
    
    # Paramètres de réparation
    default_compression_level: int = 8
    create_backups: bool = True
    verify_repairs: bool = True
    
    # Paramètres ReplayGain
    replaygain_target_loudness: float = -18.0
    use_r128: bool = False
    
    # Paramètres d'analyse
    strict_validation: bool = False
    deep_frame_scan: bool = False
    calculate_checksums: bool = False
    
    # Paramètres de traitement parallèle
    max_workers: int = None  # None = auto-detect
    enable_progress_bars: bool = True
    
    # Paramètres de sortie
    default_export_format: str = "text"  # text, json, csv, html
    colorize_output: bool = True
    verbose_level: int = 1  # 0=quiet, 1=normal, 2=verbose, 3=debug
    
    @classmethod
    def load_from_file(cls, config_path: Path) -> 'FlacToolkitConfig':
        """Charge configuration depuis un fichier YAML."""
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
                return cls(**data)
        return cls()
    
    def save_to_file(self, config_path: Path):
        """Sauvegarde la configuration dans un fichier YAML."""
        with open(config_path, 'w') as f:
            yaml.dump(self.__dict__, f, default_flow_style=False)

# Configuration globale par défaut
DEFAULT_CONFIG = FlacToolkitConfig()
```

## 8. Tests unitaires

**Créer une structure de tests complète:**

```python
# tests/test_analyzer.py
import pytest
from pathlib import Path
from flac_toolkit.analyzer import FlacAnalyzer

class TestFlacAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return FlacAnalyzer()
    
    @pytest.fixture
    def valid_flac(self):
        """Retourne le chemin vers un fichier FLAC valide de test."""
        return Path("tests/fixtures/valid.flac")
    
    @pytest.fixture
    def corrupted_flac(self):
        """Retourne le chemin vers un fichier FLAC corrompu de test."""
        return Path("tests/fixtures/corrupted.flac")
    
    def test_valid_file_detection(self, analyzer, valid_flac):
        result = analyzer.analyze_flac_comprehensive(valid_flac)
        assert result['status'] == 'VALID'
        assert len(result['errors']) == 0
    
    def test_corrupted_file_detection(self, analyzer, corrupted_flac):
        result = analyzer.analyze_flac_comprehensive(corrupted_flac)
        assert result['status'] == 'INVALID'
        assert len(result['errors']) > 0
    
    def test_header_parsing(self, analyzer, valid_flac):
        header = analyzer._check_file_header_manually(valid_flac)
        assert header['is_flac'] == True
        assert len(header['metadata_blocks']) > 0
        assert header['metadata_blocks'][0]['type'] == 0  # STREAMINFO
    
    def test_oversized_padding_detection(self, analyzer):
        """Teste la détection de blocs PADDING anormalement grands."""
        blocks = [{'type': 1, 'length': 200000}]  # 200KB PADDING
        errors = analyzer._analyze_metadata_blocks(blocks)
        assert any('PADDING' in e for e in errors)
    
    def test_android_compatibility_check(self, analyzer, valid_flac):
        from mutagen.flac import FLAC
        audio = FLAC(valid_flac)
        warnings = analyzer._check_android_compatibility(audio.info)
        # Vérifie que la méthode retourne une liste
        assert isinstance(warnings, list)

# tests/test_repair.py
import pytest
from pathlib import Path
from flac_toolkit.repair import FlacRepairer

class TestFlacRepairer:
    @pytest.fixture
    def repairer(self):
        return FlacRepairer([])
    
    def test_filename_repair_special_chars(self, repairer, tmp_path):
        """Teste le nettoyage de caractères spéciaux."""
        test_file = tmp_path / "test<file>:name?.flac"
        test_file.touch()
        repaired = repairer.repair_filename(test_file)
        assert '<' not in repaired.name
        assert '>' not in repaired.name
        assert ':' not in repaired.name
    
    def test_filename_length_truncation(self, repairer, tmp_path):
        """Teste la troncature de noms trop longs."""
        long_name = "a" * 300 + ".flac"
        test_file = tmp_path / long_name
        test_file.touch()
        repaired = repairer.repair_filename(test_file)
        assert len(repaired.name) <= 205  # 200 + ".flac"
    
    def test_backup_creation(self, repairer, tmp_path):
        """Teste la création de backups."""
        test_file = tmp_path / "test.flac"
        test_file.write_text("fake flac content")
        backup = repairer.create_backup(test_file)
        assert backup.exists()
        assert backup.suffix == '.backup'

# tests/test_frame_repair.py (nouveau)
import pytest
from flac_toolkit.frame_repair import FrameRepairer

class TestFrameRepairer:
    def test_frame_crc_validation(self):
        """Teste la validation des CRC de frames."""
        # Implémenter avec des frames FLAC réelles ou mockées
        pass
    
    def test_frame_interpolation(self):
        """Teste l'interpolation de frames corrompues."""
        pass

# tests/test_replaygain.py
import pytest
from pathlib import Path
from flac_toolkit.replaygain import ReplayGainApplicator

class TestReplayGainApplicator:
    @pytest.fixture
    def applicator(self):
        return ReplayGainApplicator()
    
    def test_loudness_calculation(self, applicator):
        """Teste le calcul de loudness."""
        # Nécessite un fichier de test
        pass
    
    def test_peak_detection(self, applicator):
        """Teste la détection de peak."""
        pass
    
    def test_tag_application(self, applicator, tmp_path):
        """Teste l'application des tags ReplayGain."""
        pass

# tests/conftest.py
import pytest
from pathlib import Path
import shutil

@pytest.fixture(scope="session")
def test_data_dir():
    """Répertoire contenant les fichiers de test."""
    return Path("tests/fixtures")

@pytest.fixture
def temp_flac_file(tmp_path):
    """Crée un fichier FLAC temporaire pour tests."""
    # Copier un fichier de référence ou en générer un
    pass

# Configuration pytest
# tests/pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --tb=short
    --cov=flac_toolkit
    --cov-report=html
    --cov-report=term-missing
```

## 9. Documentation et exemples d'usage

**Créer `docs/usage_examples.md`:**

```markdown
# FLAC Toolkit - Guide d'utilisation avancé

## Installation

```bash
git clone https://github.com/berangerthomas/flac_toolkit.git
cd flac_toolkit
pip install -e .
# ou avec uv:
uv sync
```

## Exemples d'utilisation

### Analyse basique

```bash
# Analyser un fichier
python main.py analyze song.flac

# Analyser récursivement un répertoire
python main.py analyze /path/to/music/

# Analyse stricte (validation complète)
python main.py analyze --strict /path/to/music/

# Export des résultats en JSON
python main.py analyze /path/to/music/ --export json --output report.json
```

### Réparation

```bash
# Réparation automatique (seulement fichiers problématiques)
python main.py repair /path/to/music/

# Réparation forcée (ré-encode tous les fichiers)
python main.py repair --force /path/to/music/

# Avec création de backups
python main.py repair --backup /path/to/music/

# Avec vérification post-réparation
python main.py repair --verify /path/to/music/

# Traitement parallèle (4 workers)
python main.py repair --parallel 4 /path/to/music/
```

### ReplayGain

```bash
# Calcul par album (selon métadonnées)
python main.py replaygain /path/to/album/

# Forcer traitement comme un seul album
python main.py replaygain --assume-album /path/to/files/

# Utiliser EBU R128 au lieu de ReplayGain 2.0
python main.py replaygain --r128 /path/to/music/

# Supprimer les tags existants
python main.py replaygain --remove-rg /path/to/music/

# Vérifier les tags existants
python main.py replaygain --verify-rg /path/to/music/
```

### Gestion des métadonnées

```bash
# Exporter les métadonnées
python main.py metadata export /path/to/music/ --format json

# Normaliser les tags
python main.py metadata normalize /path/to/music/ --rules capitalization

# Extraire les images embarquées
python main.py metadata extract-images /path/to/music/ --output covers/

# Ajouter une image
python main.py metadata embed-image song.flac cover.jpg --type 3
```

### Analyse de qualité

```bash
# Analyse de qualité audio
python main.py quality /path/to/music/

# Détecter les transcodes lossy
python main.py quality --check-transcode /path/to/music/

# Détecter le clipping
python main.py quality --check-clipping /path/to/music/

# Calculer le Dynamic Range
python main.py quality --calculate-dr /path/to/music/
```

### Récupération avancée

```bash
# Mode carving pour fichiers sévèrement corrompus
python main.py carve /path/to/corrupted.flac

# Réparation granulaire (au niveau frame)
python main.py repair-frames /path/to/music/

# Reconstruction des métadonnées
python main.py rebuild-metadata /path/to/music/
```

### Conversion et optimisation

```bash
# Changer le niveau de compression
python main.py convert --compression 8 /path/to/music/

# Ré-échantillonnage
python main.py convert --resample 48000 /path/to/music/

# Conversion de bit depth
python main.py convert --bit-depth 16 /path/to/music/
```

### Surveillance

```bash
# Surveiller un répertoire et analyser automatiquement
python main.py watch /path/to/downloads/ --action analyze

# Surveiller et réparer automatiquement
python main.py watch /path/to/downloads/ --action auto-repair
```

### Checksums et intégrité

```bash
# Générer fichier de checksums
python main.py checksum create /path/to/music/ --algorithm sha256

# Vérifier intégrité
python main.py checksum verify checksums.txt

# Vérification AccurateRip (CD rips)
python main.py checksum accuraterip /path/to/cd_rip/ --offset 102
```

### Visualisation

```bash
# Générer spectrogrammes
python main.py visualize spectrogram song.flac --output spectrum.png

# Visualiser structure du fichier
python main.py visualize structure song.flac --output structure.png

# Statistiques de bibliothèque
python main.py visualize library-stats /path/to/music/ --output stats.html
```

### Batch processing avec checkpoint

```bash
# Traitement long avec reprise possible
python main.py repair /path/to/huge/library/ --checkpoint repair.chk --parallel 8

# Si interrompu, reprendre:
python main.py repair /path/to/huge/library/ --resume repair.chk
```

## Configuration

Créer un fichier `~/.flac_toolkit_config.yaml`:

```yaml
flac_binary: /usr/local/bin/flac
ffmpeg_binary: /usr/bin/ffmpeg
default_compression_level: 8
create_backups: true
verify_repairs: true
max_workers: 4
colorize_output: true
verbose_level: 1
```

## Intégration dans scripts

```python
from pathlib import Path
from flac_toolkit.analyzer import FlacAnalyzer
from flac_toolkit.repair import FlacRepairer
from flac_toolkit.replaygain import ReplayGainApplicator

# Analyse programmatique
analyzer = FlacAnalyzer()
result = analyzer.analyze_flac_comprehensive(Path("song.flac"))
if result['status'] == 'INVALID':
    print(f"Fichier corrompu: {result['errors']}")

# Réparation programmatique
repairer = FlacRepairer([])
repaired = repairer.reencode_flac(Path("corrupted.flac"))

# ReplayGain programmatique
applicator = ReplayGainApplicator()
album_files = [Path("track1.flac"), Path("track2.flac")]
applicator.process_album(album_files)
```
```

## 10. Améliorations CLI et UX

**Améliorer `main.py` pour meilleure expérience utilisateur:**

```python
#!/usr/bin/env python3
"""
FLAC Toolkit - Advanced FLAC Diagnosis, Repair, and ReplayGain Tool
"""

import sys
import argparse
from pathlib import Path
from typing import List
import logging

# Imports conditionnels pour colorisation
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Fallback si colorama non installé
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

from flac_toolkit.config import FlacToolkitConfig, DEFAULT_CONFIG
from flac_toolkit.analyzer import FlacAnalyzer
from flac_toolkit.repair import FlacRepairer
from flac_toolkit.reporter import Reporter
from flac_toolkit.utils import find_flac_files
from flac_toolkit.replaygain import ReplayGainApplicator

# Configuration du logging
def setup_logging(verbose_level: int):
    """Configure le logging selon le niveau de verbosité."""
    levels = {
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
        3: logging.DEBUG
    }
    level = levels.get(verbose_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def print_banner():
    """Affiche une bannière stylée."""
    banner = """
    ╔═══════════════════════════════════════════════════════╗
    ║          FLAC TOOLKIT - Advanced Edition              ║
    ║    Analysis • Repair • ReplayGain • Quality Check     ║
    ╚═══════════════════════════════════════════════════════╝
    """
    if HAS_COLOR:
        print(Fore.CYAN + Style.BRIGHT + banner)
    else:
        print(banner)

def print_success(message: str):
    """Affiche un message de succès."""
    if HAS_COLOR:
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} {message}")
    else:
        print(f"✓ {message}")

def print_error(message: str):
    """Affiche un message d'erreur."""
    if HAS_COLOR:
        print(f"{Fore.RED}✗{Style.RESET_ALL} {message}", file=sys.stderr)
    else:
        print(f"✗ {message}", file=sys.stderr)

def print_warning(message: str):
    """Affiche un avertissement."""
    if HAS_COLOR:
        print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} {message}")
    else:
        print(f"⚠ {message}")

def print_info(message: str):
    """Affiche une information."""
    if HAS_COLOR:
        print(f"{Fore.BLUE}ℹ{Style.RESET_ALL} {message}")
    else:
        print(f"ℹ {message}")

# Modes existants améliorés avec gestion d'erreurs et progression

def analyze_mode(target_paths: List[Path], config: FlacToolkitConfig, args):
    """Mode analyse amélioré."""
    print_info("Starting comprehensive analysis...")
    
    files = list(find_flac_files(target_paths))
    if not files:
        print_error("No FLAC files found.")
        return 1
    
    print_info(f"Found {len(files)} FLAC file(s) to analyze")
    
    analyzer = FlacAnalyzer(config)
    results = []
    
    # Avec barre de progression si tqdm disponible
    try:
        from tqdm import tqdm
        iterator = tqdm(files, desc="Analyzing", unit="file")
    except ImportError:
        iterator = files
        print_info("Install tqdm for progress bars: pip install tqdm")
    
    for file_path in iterator:
        try:
            result = analyzer.analyze_flac_comprehensive(file_path)
            results.append(result)
        except Exception as e:
            print_error(f"Failed to analyze {file_path}: {e}")
            logging.exception(e)
    
    # Affichage des résultats
    if args.export:
        output_file = args.output or Path(f"analysis_report.{args.export}")
        Reporter.export_results(results, output_file, args.export)
        print_success(f"Report exported to {output_file}")
    else:
        for result in results:
            Reporter.print_analysis_result(result)
        Reporter.print_summary(results)
    
    return 0

def repair_mode(target_paths: List[Path], config: FlacToolkitConfig, args):
    """Mode réparation amélioré."""
    # ... similaire avec messages colorés et gestion d'erreurs
    pass

# Nouveaux modes

def quality_mode(target_paths: List[Path], config: FlacToolkitConfig, args):
    """Mode analyse de qualité."""
    from flac_toolkit.quality_analyzer import QualityAnalyzer
    
    print_info("Starting quality analysis...")
    files = list(find_flac_files(target_paths))
    
    if not files:
        print_error("No FLAC files found.")
        return 1
    
    analyzer = QualityAnalyzer()
    
    for file_path in files:
        print(f"\n{'='*70}")
        print(f"File: {file_path.name}")
        print('='*70)
        
        # Clipping
        if args.check_clipping or args.all_checks:
            clipping = analyzer.detect_clipping(file_path)
            if clipping['clipped_samples'] > 0:
                print_warning(f"Clipping detected: {clipping['percentage']:.2f}%")
            else:
                print_success("No clipping detected")
        
        # Dynamic Range
        if args.calculate_dr or args.all_checks:
            dr = analyzer.calculate_dynamic_range(file_path)
            print_info(f"Dynamic Range: DR{dr:.0f}")
        
        # Transcode detection
        if args.check_transcode or args.all_checks:
            is_transcode = analyzer.detect_lossy_transcode(file_path)
            if is_transcode:
                print_error("Likely lossy transcode (frequency cutoff detected)")
            else:
                print_success("Appears to be genuine lossless")
    
    return 0

def metadata_mode(target_paths: List[Path], config: FlacToolkitConfig, args):
    """Mode gestion des métadonnées."""
    from flac_toolkit.metadata_manager import MetadataManager
    
    manager = MetadataManager()
    files = list(find_flac_files(target_paths))
    
    if args.metadata_action == 'export':
        for file_path in files:
            output = manager.export_metadata(file_path, args.format)
            print_success(f"Metadata exported: {output}")
    
    elif args.metadata_action == 'normalize':
        for file_path in files:
            manager.normalize_tags(file_path, args.rules)
            print_success(f"Normalized: {file_path.name}")
    
    elif args.metadata_action == 'extract-images':
        output_dir = args.output or Path("extracted_covers")
        output_dir.mkdir(exist_ok=True)
        for file_path in files:
            manager.extract_embedded_images(file_path, output_dir)
    
    return 0

def watch_mode(directory: Path, config: FlacToolkitConfig, args):
    """Mode surveillance."""
    from flac_toolkit.watcher import watch_directory
    
    print_info(f"Watching directory: {directory}")
    print_info(f"Action on new files: {args.watch_action}")
    print_warning("Press Ctrl+C to stop")
    
    try:
        watch_directory(directory, args.watch_action)
    except KeyboardInterrupt:
        print_info("\nStopping watcher...")
    
    return 0

def checksum_mode(target_paths: List[Path], config: FlacToolkitConfig, args):
    """Mode checksums."""
    from flac_toolkit.checksum_manager import ChecksumManager
    
    manager = ChecksumManager()
    
    if args.checksum_action == 'create':
        for target in target_paths:
            if target.is_dir():
                output = target / f"checksums_{args.algorithm}.txt"
                manager.create_checksum_file(target, args.algorithm)
                print_success(f"Checksums created: {output}")
    
    elif args.checksum_action == 'verify':
        results = manager.verify_checksums(args.checksum_file)
        for result in results:
            if result['status'] == 'OK':
                print_success(f"{result['file']}: OK")
            elif result['status'] == 'FAILED':
                print_error(f"{result['file']}: FAILED")
            else:
                print_warning(f"{result['file']}: MISSING")
    
    return 0

def convert_mode(target_paths: List[Path], config: FlacToolkitConfig, args):
    """Mode conversion."""
    from flac_toolkit.converter import FlacConverter
    
    converter = FlacConverter()
    files = list(find_flac_files(target_paths))
    
    for file_path in files:
        if args.compression:
            output = converter.change_compression_level(file_path, args.compression)
            print_success(f"Recompressed: {output.name}")
        
        if args.resample:
            output = converter.resample(file_path, args.resample)
            print_success(f"Resampled to {args.resample}Hz: {output.name}")
        
        if args.bit_depth:
            output = converter.convert_bit_depth(file_path, args.bit_depth)
            print_success(f"Converted to {args.bit_depth}-bit: {output.name}")
    
    return 0

def visualize_mode(target_paths: List[Path], config: FlacToolkitConfig, args):
    """Mode visualisation."""
    from flac_toolkit.visualizer import FlacVisualizer
    
    visualizer = FlacVisualizer()
    files = list(find_flac_files(target_paths))
    
    if args.viz_type == 'spectrogram':
        for file_path in files:
            output = args.output or file_path.with_suffix('.png')
            visualizer.plot_spectrogram(file_path, output)
            print_success(f"Spectrogram saved: {output}")
    
    elif args.viz_type == 'waveform':
        for file_path in files:
            output = args.output or file_path.with_suffix('.png')
            visualizer.plot_waveform(file_path, output)
            print_success(f"Waveform saved: {output}")
    
    elif args.viz_type == 'structure':
        for file_path in files:
            output = args.output or file_path.with_name(f"{file_path.stem}_structure.png")
            visualizer.plot_file_structure(file_path, output)
            print_success(f"Structure visualization saved: {output}")
    
    elif args.viz_type == 'library-stats':
        output = args.output or Path("library_stats.html")
        analyzer = FlacAnalyzer()
        results = [analyzer.analyze_flac_comprehensive(f) for f in files]
        visualizer.plot_library_statistics(results, output)
        print_success(f"Library statistics saved: {output}")
    
    return 0

def main():
    """Point d'entrée principal avec CLI enrichi."""
    
    # Parser principal
    parser = argparse.ArgumentParser(
        prog='flac_toolkit',
        description='FLAC Toolkit - Comprehensive FLAC analysis, repair, and management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analyze /path/to/music/
  %(prog)s repair --force --backup /path/to/music/
  %(prog)s replaygain --assume-album /path/to/album/
  %(prog)s quality --check-transcode /path/to/music/
  %(prog)s watch /downloads/ --action auto-repair

For detailed help on a specific mode:
  %(prog)s analyze --help
  %(prog)s repair --help
        """
    )
    
    # Arguments globaux
    parser.add_argument('--version', action='version', version='FLAC Toolkit 2.0.0')
    parser.add_argument('--config', type=Path, help='Path to configuration file')
    parser.add_argument('-v', '--verbose', action='count', default=1,
                       help='Increase verbosity (-v, -vv, -vvv)')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Suppress all output except errors')
    parser.add_argument('--no-color', action='store_true',
                       help='Disable colored output')
    
    # Sous-commandes
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    
    # ===== ANALYZE =====
    analyze_parser = subparsers.add_parser('analyze', help='Analyze FLAC files')
    analyze_parser.add_argument('target_paths', type=Path, nargs='+',
                               help='Files or directories to analyze')
    analyze_parser.add_argument('--strict', action='store_true',
                               help='Enable strict FLAC specification validation')
    analyze_parser.add_argument('--deep', action='store_true',
                               help='Deep scan including frame-level analysis')
    analyze_parser.add_argument('--export', choices=['json', 'csv', 'html'],
                               help='Export results to file')
    analyze_parser.add_argument('--output', type=Path,
                               help='Output file for export')
    analyze_parser.add_argument('--parallel', type=int, metavar='N',
                               help='Number of parallel workers')
    
    # ===== REPAIR =====
    repair_parser = subparsers.add_parser('repair', help='Repair FLAC files')
    repair_parser.add_argument('target_paths', type=Path, nargs='+',
                              help='Files or directories to repair')
    repair_parser.add_argument('--force', action='store_true',
                              help='Force re-encoding of all files')
    repair_parser.add_argument('--backup', action='store_true',
                              help='Create backups before repair')
    repair_parser.add_argument('--verify', action='store_true',
                              help='Verify repairs after completion')
    repair_parser.add_argument('--parallel', type=int, metavar='N',
                              help='Number of parallel workers')
    repair_parser.add_argument('--checkpoint', type=Path,
                              help='Checkpoint file for resumable operations')
    repair_parser.add_argument('--resume', type=Path,
                              help='Resume from checkpoint file')
    
    # ===== REPLAYGAIN =====
    rg_parser = subparsers.add_parser('replaygain', help='Calculate and apply ReplayGain')
    rg_parser.add_argument('target_paths', type=Path, nargs='+',
                          help='Files or directories to process')
    rg_parser.add_argument('--assume-album', action='store_true',
                          help='Treat all files as one album')
    rg_parser.add_argument('--r128', action='store_true',
                          help='Use EBU R128 instead of ReplayGain 2.0')
    rg_parser.add_argument('--remove-rg', action='store_true',
                          help='Remove existing ReplayGain tags')
    rg_parser.add_argument('--verify-rg', action='store_true',
                          help='Verify existing ReplayGain tags')
    
    # ===== QUALITY =====
    quality_parser = subparsers.add_parser('quality', help='Analyze audio quality')
    quality_parser.add_argument('target_paths', type=Path, nargs='+',
                               help='Files or directories to analyze')
    quality_parser.add_argument('--check-clipping', action='store_true',
                               help='Check for clipping')
    quality_parser.add_argument('--calculate-dr', action='store_true',
                               help='Calculate Dynamic Range')
    quality_parser.add_argument('--check-transcode', action='store_true',
                               help='Detect lossy transcodes')
    quality_parser.add_argument('--all-checks', action='store_true',
                               help='Run all quality checks')
    quality_parser.add_argument('--export', choices=['json', 'csv', 'html'],
                               help='Export results to file')
    
    # ===== METADATA =====
    metadata_parser = subparsers.add_parser('metadata', help='Manage metadata')
    metadata_parser.add_argument('target_paths', type=Path, nargs='+',
                                help='Files or directories to process')
    metadata_parser.add_argument('action', choices=['export', 'import', 'normalize', 
                                                     'extract-images', 'embed-image'],
                                help='Metadata action')
    metadata_parser.add_argument('--format', choices=['json', 'yaml', 'csv'],
                                default='json', help='Export/import format')
    metadata_parser.add_argument('--metadata-file', type=Path,
                                help='Metadata file for import')
    metadata_parser.add_argument('--rules', nargs='+',
                                help='Normalization rules')
    metadata_parser.add_argument('--image', type=Path,
                                help='Image file to embed')
    metadata_parser.add_argument('--output', type=Path,
                                help='Output directory or file')
    
    # ===== WATCH =====
    watch_parser = subparsers.add_parser('watch', help='Watch directory for changes')
    watch_parser.add_argument('directory', type=Path,
                             help='Directory to watch')
    watch_parser.add_argument('--action', choices=['analyze', 'auto-repair', 'replaygain'],
                             default='analyze', help='Action on new files')
    
    # ===== CHECKSUM =====
    checksum_parser = subparsers.add_parser('checksum', help='Manage checksums')
    checksum_parser.add_argument('action', choices=['create', 'verify', 'accuraterip'],
                                help='Checksum action')
    checksum_parser.add_argument('target_paths', type=Path, nargs='*',
                                help='Files or directories')
    checksum_parser.add_argument('--algorithm', choices=['md5', 'sha256', 'sha512'],
                                default='sha256', help='Hash algorithm')
    checksum_parser.add_argument('--checksum-file', type=Path,
                                help='Checksum file to verify')
    checksum_parser.add_argument('--offset', type=int, default=0,
                                help='Drive offset for AccurateRip')
    
    # ===== CONVERT =====
    convert_parser = subparsers.add_parser('convert', help='Convert/optimize FLAC files')
    convert_parser.add_argument('target_paths', type=Path, nargs='+',
                               help='Files or directories to convert')
    convert_parser.add_argument('--compression', type=int, choices=range(0, 9),
                               help='Compression level (0-8)')
    convert_parser.add_argument('--resample', type=int,
                               help='Target sample rate (Hz)')
    convert_parser.add_argument('--bit-depth', type=int, choices=[16, 24, 32],
                               help='Target bit depth')
    convert_parser.add_argument('--to-wav', action='store_true',
                               help='Convert to WAV')
    
    # ===== VISUALIZE =====
    viz_parser = subparsers.add_parser('visualize', help='Create visualizations')
    viz_parser.add_argument('target_paths', type=Path, nargs='+',
                           help='Files or directories')
    viz_parser.add_argument('type', choices=['spectrogram', 'waveform', 'structure', 
                                             'library-stats'],
                           help='Visualization type')
    viz_parser.add_argument('--output', type=Path,
                           help='Output file')
    
    # ===== CARVE =====
    carve_parser = subparsers.add_parser('carve', help='Recover data from corrupted files')
    carve_parser.add_argument('target_paths', type=Path, nargs='+',
                             help='Corrupted files to recover')
    carve_parser.add_argument('--output-dir', type=Path,
                             help='Directory for recovered files')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Gestion du mode quiet
    if args.quiet:
        args.verbose = 0
    
    # Configuration du logging
    setup_logging(args.verbose)
    
    # Chargement de la configuration
    if args.config and args.config.exists():
        config = FlacToolkitConfig.load_from_file(args.config)
    else:
        config = DEFAULT_CONFIG
    
    # Désactivation des couleurs si demandé
    if args.no_color:
        global HAS_COLOR
        HAS_COLOR = False
    
    # Affichage de la bannière (sauf en mode quiet)
    if args.verbose > 0:
        print_banner()
    
    # Validation du mode
    if not args.mode:
        parser.print_help()
        return 1
    
    # Dispatch vers le mode approprié
    try:
        if args.mode == 'analyze':
            return analyze_mode(args.target_paths, config, args)
        elif args.mode == 'repair':
            return repair_mode(args.target_paths, config, args)
        elif args.mode == 'replaygain':
            return replaygain_mode(args.target_paths, config, args)
        elif args.mode == 'quality':
            return quality_mode(args.target_paths, config, args)
        elif args.mode == 'metadata':
            return metadata_mode(args.target_paths, config, args)
        elif args.mode == 'watch':
            return watch_mode(args.directory, config, args)
        elif args.mode == 'checksum':
            return checksum_mode(args.target_paths, config, args)
        elif args.mode == 'convert':
            return convert_mode(args.target_paths, config, args)
        elif args.mode == 'visualize':
            return visualize_mode(args.target_paths, config, args)
        elif args.mode == 'carve':
            return carve_mode(args.target_paths, config, args)
        else:
            print_error(f"Unknown mode: {args.mode}")
            return 1
    except KeyboardInterrupt:
        print_warning("\nOperation interrupted by user")
        return 130
    except Exception as e:
        print_error(f"Fatal error: {e}")
        if args.verbose >= 3:
            logging.exception(e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

## 11. Gestion des erreurs et résilience

**Créer `flac_toolkit/exceptions.py`:**

```python
"""Exceptions personnalisées pour FLAC Toolkit."""

class FlacToolkitError(Exception):
    """Classe de base pour toutes les exceptions du toolkit."""
    pass

class CorruptedFileError(FlacToolkitError):
    """Levée quand un fichier est détecté comme corrompu."""
    pass

class RepairFailedError(FlacToolkitError):
    """Levée quand une réparation échoue."""
    pass

class MetadataError(FlacToolkitError):
    """Levée lors d'erreurs de métadonnées."""
    pass

class ValidationError(FlacToolkitError):
    """Levée lors d'échecs de validation."""
    pass

class ToolNotFoundError(FlacToolkitError):
    """Levée quand un outil externe requis n'est pas trouvé."""
    pass

class ChecksumMismatchError(FlacToolkitError):
    """Levée quand un checksum ne correspond pas."""
    pass
```

**Améliorer la gestion d'erreurs dans repair.py:**

```python
from flac_toolkit.exceptions import RepairFailedError, ToolNotFoundError

class FlacRepairer:
    def __init__(self, repair_log: List[str]):
        self.repair_log = repair_log
        self._verify_tools()
    
    def _verify_tools(self):
        """Vérifie la disponibilité des outils externes."""
        self.has_flac = shutil.which('flac') is not None
        self.has_ffmpeg = shutil.which('ffmpeg') is not None
        
        if not self.has_flac and not self.has_ffmpeg:
            raise ToolNotFoundError(
                "Neither 'flac' nor 'ffmpeg' found. "
                "Please install at least one of them."
            )
    
    def reencode_flac(self, input_path: Path, 
                     compression_level: int = 8,
                     max_retries: int = 3) -> Path | None:
        """
        Ré-encode un fichier FLAC avec gestion d'erreurs et retry.
        """
        output_path = input_path.with_stem(f"{input_path.stem}_repaired")
        
        for attempt in range(max_retries):
            try:
                if self.has_flac:
                    return self._reencode_with_flac(
                        input_path, output_path, compression_level
                    )
                elif self.has_ffmpeg:
                    return self._reencode_with_ffmpeg(input_path, output_path)
            except Exception as e:
                if attempt < max_retries - 1:
                    self.repair_log.append(
                        f"  ⚠ Attempt {attempt + 1} failed: {e}. Retrying..."
                    )
                    continue
                else:
                    raise RepairFailedError(
                        f"Failed to re-encode after {max_retries} attempts: {e}"
                    )
        
        return None
    
    def _reencode_with_flac(self, input_path: Path, output_path: Path, 
                           compression: int) -> Path:
        """Ré-encode avec l'outil flac."""
        cmd = [
            'flac', 
            f'-{compression}',  # Niveau de compression
            '--verify',          # Vérifier après encodage
            '--force',           # Écraser si existe
            '-o', str(output_path),
            str(input_path)
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='ignore',
            timeout=300  # Timeout de 5 minutes
        )
        
        if result.returncode != 0:
            raise RepairFailedError(f"flac failed: {result.stderr.strip()}")
        
        self.repair_log.append(f"✓ Re-encoded (flac): {output_path.name}")
        self._copy_metadata(input_path, output_path)
        return output_path
    
    def _reencode_with_ffmpeg(self, input_path: Path, output_path: Path) -> Path:
        """Ré-encode avec ffmpeg."""
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-acodec', 'flac',
            '-compression_level', '8',
            '-y',  # Écraser sans demander
            str(output_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=300
        )
        
        if result.returncode != 0:
            raise RepairFailedError(f"ffmpeg failed: {result.stderr.strip()}")
        
        self.repair_log.append(f"✓ Re-encoded (ffmpeg): {output_path.name}")
        return output_path
```

## 12. Performance et optimisation

**Créer `flac_toolkit/performance.py`:**

```python
"""Utilitaires de performance et profiling."""

import time
import functools
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

def timeit(func: Callable) -> Callable:
    """Décorateur pour mesurer le temps d'exécution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.debug(f"{func.__name__} took {elapsed:.3f}s")
        return result
    return wrapper

def memory_efficient_file_reader(file_path: Path, chunk_size: int = 1024 * 1024):
    """
    Lit un fichier par chunks pour éviter de charger tout en mémoire.
    Utile pour les très gros fichiers.
    """
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

class ProgressCache:
    """Cache pour éviter de re-traiter les fichiers déjà analysés."""
    
    def __init__(self, cache_file: Path = Path(".flac_toolkit_cache.json")):
        self.cache_file = cache_file
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """Charge le cache depuis le disque."""
        if self.cache_file.exists():
            import json
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_cache(self):
        """Sauvegarde le cache sur disque."""
        import json
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def is_cached(self, file_path: Path) -> bool:
        """Vérifie si un fichier est en cache et non modifié."""
        key = str(file_path)
        if key not in self.cache:
            return False
        
        cached_mtime = self.cache[key].get('mtime')
        current_mtime = file_path.stat().st_mtime
        
        return cached_mtime == current_mtime
    
    def get(self, file_path: Path) -> dict | None:
        """Récupère les données cachées pour un fichier."""
        key = str(file_path)
        if self.is_cached(file_path):
            return self.cache[key].get('data')
        return None
    
    def set(self, file_path: Path, data: dict):
        """Met en cache les données pour un fichier."""
        key = str(file_path)
        self.cache[key] = {
            'mtime': file_path.stat().st_mtime,
            'data': data
        }
```

## 13. Documentation API

**Créer `docs/api_reference.md`:**

```markdown
# FLAC Toolkit - API Reference

## FlacAnalyzer

Classe principale pour l'analyse de fichiers FLAC.

### Méthodes

#### `analyze_flac_comprehensive(file_path: Path) -> Dict[str, Any]`

Effectue une analyse complète d'un fichier FLAC.

**Paramètres:**
- `file_path`: Chemin vers le fichier FLAC à analyser

**Retourne:**
Dictionnaire contenant:
- `file` (str): Chemin du fichier
- `status` (str): 'VALID', 'VALID (with warnings)', ou 'INVALID'
- `errors` (List[str]): Liste des erreurs détectées
- `warnings` (List[str]): Liste des avertissements
- `info` (Dict): Informations audio (durée, sample rate, etc.)
- `header_analysis` (Dict): Analyse des headers FLAC
- `data_structure_analysis` (Dict): Analyse de la structure des données
- `repair_suggestions` (List[Dict]): Suggestions de réparation

**Exemple:**
```python
from pathlib import Path
from flac_toolkit.analyzer import FlacAnalyzer

analyzer = FlacAnalyzer()
result = analyzer.analyze_flac_comprehensive(Path("song.flac"))

if result['status'] == 'INVALID':
    print(f"Erreurs détectées: {result['errors']}")
    for suggestion in result['repair_suggestions']:
        print(f"Action recommandée: {suggestion['action']}")
```

## FlacRepairer

Classe pour la réparation de fichiers FLAC.

### Méthodes

#### `reencode_flac(input_path: Path, compression_level: int = 8) -> Path | None`

Ré-encode un fichier FLAC.

**Paramètres:**
- `input_path`: Fichier source
- `compression_level`: Niveau de compression (0-8, défaut: 8)

**Retourne:**
Chemin du fichier réparé ou None en cas d'échec

**Exemple:**
```python
from flac_toolkit.repair import FlacRepairer

repairer = FlacRepairer([])
repaired_file = repairer.reencode_flac(Path("corrupted.flac"))
if repaired_file:
    print(f"Réparation réussie: {repaired_file}")
```

## ReplayGainApplicator

Classe pour le calcul et l'application de ReplayGain.

### Méthodes

#### `process_album(album_files: List[Path])`

Calcule et applique ReplayGain pour un album.

**Paramètres:**
- `album_files`: Liste des fichiers de l'album

**Exemple:**
```python
from pathlib import Path
from flac_toolkit.replaygain import ReplayGainApplicator

applicator = ReplayGainApplicator()
album = [Path(f"track{i}.flac") for i in range(1, 11)]
applicator.process_album(album)
```

## FrameRepairer (nouveau)

Classe pour la réparation granulaire au niveau frame.

### Méthodes

#### `analyze_frames(file_path: Path) -> List[FrameInfo]`

Analyse toutes les frames et vérifie leur intégrité.

#### `repair_selective(file_path: Path, corrupted_frames: List[int]) -> Path`

Répare uniquement les frames spécifiées.

## MetadataManager (nouveau)

Classe pour la gestion avancée des métadonnées.

### Méthodes

#### `export_metadata(file_path: Path, output_format: str = 'json') -> Path`

Exporte les métadonnées dans un fichier.

#### `normalize_tags(file_path: Path, rules: Dict)`

Normalise les tags selon des règles spécifiées.

## QualityAnalyzer (nouveau)

Classe pour l'analyse de qualité audio.

### Méthodes

#### `detect_clipping(file_path: Path) -> Dict`

Détecte le clipping audio.

#### `calculate_dynamic_range(file_path: Path) -> float`

Calcule le Dynamic Range.

#### `detect_lossy_transcode(file_path: Path) -> bool`

Détecte si le fichier est probablement un transcode lossy.
```

## 14. Roadmap et priorités

**Créer `docs/ROADMAP.md`:**

```markdown
# FLAC Toolkit - Roadmap de développement

## Phase 1: Réparation avancée (Priorité HAUTE)

### 1.1 Réparation granulaire
- [ ] Implémentation du parser de frames FLAC
- [ ] Validation CRC16 de chaque frame
- [ ] Algorithme d'interpolation pour frames corrompues
- [ ] Reconstruction sélective de fichiers

### 1.2 Réparation des métadonnées
- [ ] Reconstruction du bloc STREAMINFO
- [ ] Régénération de SEEKTABLE
- [ ] Suppression de blocs corrompus
- [ ] Recalcul des MD5

**Estimation:** 2-3 semaines
**Dépendances:** Connaissance approfondie du format FLAC

## Phase 2: Analyse de qualité (Priorité HAUTE)

### 2.1 Détection de transcodes
- [ ] Analyse spectrale
- [ ] Détection de coupures de fréquences
- [ ] Heuristiques pour différents formats source (MP3, AAC, Opus)

### 2.2 Métriques audio
- [ ] Détection de clipping
- [ ] Calcul Dynamic Range
- [ ] Analyse de silences
- [ ] True Peak detection

**Estimation:** 2 semaines
**Dépendances:** librosa ou scipy

## Phase 3: Outils de gestion (Priorité MOYENNE)

### 3.1 Métadonnées
- [ ] Export/import (JSON, YAML, CSV)
- [ ] Normalisation automatique
- [ ] Gestion d'images embarquées
- [ ] Édition batch

### 3.2 Checksums et intégrité
- [ ] Génération de checksums multiples
- [ ] Vérification batch
- [ ] Support AccurateRip
- [ ] Détection de fichiers dupliqués

**Estimation:** 2 semaines

## Phase 4: Performance et UX (Priorité MOYENNE)

### 4.1 Optimisations
- [ ] Traitement parallèle multi-core
- [ ] Système de cache
- [ ] Checkpoints pour opérations longues
- [ ] Mode streaming pour gros fichiers

### 4.2 Interface
- [ ] CLI amélioré avec couleurs
- [ ] Barres de progression
- [ ] Mode watch
- [ ] Exports HTML interactifs

**Estimation:** 1-2 semaines

## Phase 5: Visualisation (Priorité BASSE)

- [ ] Spectrogrammes
- [ ] Forme d'onde
- [ ] Structure de fichier
- [ ] Statistiques de bibliothèque

**Estimation:** 1 semaine
**Dépendances:** matplotlib, plotly

## Phase 6: Récupération avancée (Priorité BASSE)

- [ ] File carving
- [ ] Détection de bitflips
- [ ] Analyse d'entropie
- [ ] Récupération multi-sources

**Estimation:** 2-3 semaines
**Complexité:** Élevée

## Tests et Documentation

- [ ] Tests unitaires (coverage > 80%)
- [ ] Tests d'intégration
- [ ] Documentation API complète
- [ ] Tutoriels et exemples
- [ ] CI/CD (GitHub Actions)

**Continu**
```

## 15. Intégration Continue

**Créer `.github/workflows/tests.yml`:**

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Install system dependencies (Linux)
      if: runner.os == 'Linux'
      run: |
        sudo apt-get update
        sudo apt-get install -y flac ffmpeg
    
    - name: Install system dependencies (macOS)
      if: runner.os == 'macOS'
      run: |
        brew install flac ffmpeg
    
    - name: Install system dependencies (Windows)
      if: runner.os == 'Windows'
      run: |
        choco install flac ffmpeg
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=flac_toolkit --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Run linting
      run: |
        flake8 flac_toolkit/ --max-line-length=100
        black --check flac_toolkit/
        mypy flac_toolkit/
```

## Résumé des priorités d'implémentation

### Priorité CRITIQUE (à implémenter en premier)
1. **Réparation granulaire au niveau frame** - Le cœur de l'amélioration
2. **Analyse de qualité** (détection transcodes, clipping) - Très demandé
3. **Tests unitaires** - Pour assurer la stabilité

### Priorité HAUTE
4. **Gestion avancée des métadonnées** - Fonctionnalité utile au quotidien
5. **Traitement parallèle** - Amélioration significative de performance
6. **Système de cache** - Évite les analyses redondantes

### Priorité MOYENNE
7. **Checksums et intégrité** - Pour les archivistes
8. **Mode watch** - Automatisation pratique
9. **Exports multiples formats** - Intégration avec d'autres outils

### Priorité BASSE
10. **Visualisations** - Nice to have
11. **File carving** - Cas d'usage rare mais intéressant
12. **Interface web** (optionnelle) - Pour utilisateurs non-CLI

## Notes finales pour l'implémentation

1. **Maintenez la compatibilité**: Toutes les nouvelles fonctionnalités doivent être rétrocompatibles
2. **Tests d'abord**: Écrivez les tests avant d'implémenter les fonctionnalités complexes
3. **Documentation au fur et à mesure**: Documentez chaque nouvelle fonctionnalité immédiatement
4. **Gestion d'erreurs robuste**: Utilisez les exceptions personnalisées et gérez tous les cas d'erreur
5. **Performance**: Profilez le code et optimisez les points chauds
6. **Modularité**: Chaque module doit être indépendant et testable séparément