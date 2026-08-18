import os
import subprocess
from pathlib import Path

# Configuration des chemins (à adapter selon vos besoins)
#SRC_DIR = Path("/mnt/d1To/mp3")
#DEST_DIR = Path("/mnt/d1To/mp3clean")
SRC_DIR = Path("/mnt/nas/Music/Autres")
DEST_DIR = Path("/mnt/hdd/N_Autres")

# Extensions gérées
AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.wma', '.aac', '.aiff', '.alac', '.ogg', '.ape'}

def process_library():
    if not SRC_DIR.exists():
        print(f"Erreur : Le dossier source {SRC_DIR} n'existe pas.")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print("Démarrage du traitement complet (réparation, ffmpeg, normalisation) sans les dossiers @eaDir...")

    # Analyse récursive des dossiers[cite: 1]
    for root, dirs, files in os.walk(SRC_DIR, followlinks=True):
        
        # ---------------------------------------------------------
        # EXCLUSION DES DOSSIERS SYNONLOGY (@eaDir)
        # ---------------------------------------------------------
        # Retirer '@eaDir' de la liste empêche os.walk de descendre dedans
        if '@eaDir' in dirs:
            dirs.remove('@eaDir')
            
        root_path = Path(root)
        dossier_actuel = root_path.relative_to(SRC_DIR) if root_path != SRC_DIR else 'Racine'
        
        print(f"\n📂 SCAN DU DOSSIER : {dossier_actuel}")

        for file_name in files:
            item = root_path / file_name
            rel_path = item.relative_to(SRC_DIR)
            dest_file = DEST_DIR / rel_path
            
            # Le fichier de destination sera toujours un .mp3[cite: 1]
            dest_audio = dest_file.with_suffix('.mp3')

            if item.suffix.lower() not in AUDIO_EXTS:
                continue

            if dest_audio.exists():
                print(f"  ⏭️  [DÉJÀ PRÉSENT] {file_name} (Sauté)")
                continue

            # Création immédiate de l'arborescence côté destination[cite: 1]
            dest_audio.parent.mkdir(parents=True, exist_ok=True)

            print(f"  ⚙️  [TRAITEMENT] {file_name}")

            # ---------------------------------------------------------
            # 1. RÉPARATION avec mp3val (uniquement sur les .mp3)
            # ---------------------------------------------------------
            if item.suffix.lower() == '.mp3':
                try:
                    # mp3val répare le fichier et crée un .bak[cite: 2]
                    subprocess.run(['mp3val', '-f', str(item)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    
                    # Nettoyage immédiat du fichier de sauvegarde .bak[cite: 2]
                    bak_file = item.with_suffix('.mp3.bak')
                    if bak_file.exists():
                        bak_file.unlink()
                except Exception:
                    print(f"      ⚠️ Échec mp3val sur {file_name}")

            # ---------------------------------------------------------
            # 2. TRANSCODAGE FFmpeg (Suppression silence + pochette)
            # ---------------------------------------------------------
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
                '-map', '0:a',  # Ne mappe que le flux audio[cite: 1]
                '-vn',          # INTERDIT LA VIDÉO/POCHETTE
                str(dest_audio)
            ]

            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                
                # ---------------------------------------------------------
                # 3. NORMALISATION DU VOLUME avec mp3gain
                # ---------------------------------------------------------
                # mp3gain s'applique sur le fichier MP3 final pour éviter la saturation[cite: 2]
                subprocess.run(['mp3gain', '-r', '-k', str(dest_audio)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                
                print(f"  ✅  [SUCCÈS] {file_name}")
                
            except subprocess.CalledProcessError:
                print(f"  ❌  [ERREUR] Impossible de traiter {file_name}")

if __name__ == "__main__":
    process_library()
    print("\n✅ Traitement terminé à 100% !")
