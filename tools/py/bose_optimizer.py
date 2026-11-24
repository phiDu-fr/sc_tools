import os
import subprocess
import shutil
from pathlib import Path

# Configuration des chemins
SRC_DIR = Path("/home/pi/sc_tools/Music/mp3")
DEST_DIR = Path("/media/Music/mp3")

# Extensions élargies
AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.wma', '.aac', '.aiff', '.alac', '.ogg', '.ape'}

def process_library():
    if not SRC_DIR.exists():
        print(f"Erreur : Le dossier source {SRC_DIR} n'existe pas.")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print("Démarrage de l'analyse récursive avec os.walk...")

    # os.walk force la descente dans chaque sous-dossier, à n'importe quelle profondeur
    for root, dirs, files in os.walk(SRC_DIR, followlinks=True):
        root_path = Path(root)

        # Affiche le dossier actuellement inspecté (très utile pour voir s'il descend bien dans 'disque1')
        dossier_actuel = root_path.relative_to(SRC_DIR) if root_path != SRC_DIR else 'Racine'
        print(f"\n📂 SCAN DU DOSSIER : {dossier_actuel}")

        for file_name in files:
            item = root_path / file_name
            rel_path = item.relative_to(SRC_DIR)
            dest_file = DEST_DIR / rel_path

            # Création immédiate de l'arborescence côté destination
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # 1. Gestion des pochettes
            if item.name.lower() in ['cover.jpg', 'folder.jpg']:
                if not dest_file.exists():
                    shutil.copy2(item, dest_file)
                    print(f"  🖼️  [COPIE IMAGE] {file_name}")
                continue

            # 2. Gestion audio
            if item.suffix.lower() in AUDIO_EXTS:
                dest_audio = dest_file.with_suffix('.mp3')

                # C'est ici que le script précédent était trop silencieux
                if dest_audio.exists():
                    print(f"  ⏭️  [DÉJÀ PRÉSENT] {file_name} (Sauté)")
                    continue

                print(f"  🎵 [TRANSCODAGE] {file_name}")

                # La commande magique FFmpeg optimisée pour Bose SoundTouch avec suppression du blanc final
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', str(item),
                    '-af', 'silenceremove=stop_periods=1:stop_duration=2.0:stop_threshold=-50dB',
                    '-c:a', 'libmp3lame',
                    '-b:a', '320k',
                    '-ar', '44100',
                    '-ac', '2',
                    '-id3v2_version', '3',
                    '-map_metadata', '0',
                    '-map', '0:a',
                    '-map', '0:v?',
                    '-c:v', 'copy',
                    str(dest_audio)
                ]

                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"  ❌ [ERREUR] Impossible de convertir {file_name}")

if __name__ == "__main__":
    process_library()
    print("\n✅ Traitement terminé à 100% !")


