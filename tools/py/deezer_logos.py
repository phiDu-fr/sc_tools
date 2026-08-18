import requests
import os
import urllib.parse
import sys

# Vérification des arguments
if len(sys.argv) < 2:
    print("Usage : python deezer_logos.py <nom_de_la_radio>")
    sys.exit(1)

# Récupération du paramètre
radio_name = sys.argv[1]

# Définition du chemin de stockage
LOGOS_DIR = '/home/pi/tmp'
# LOGOS_DIR = '/app/www/img/radios' # Dossier physique (quand intégré au projet)

# S'assurer que le dossier existe au démarrage
os.makedirs(LOGOS_DIR, exist_ok=True)

def fetch_deezer_radio_logo(radio_name, size="picture_medium"):
    """
    Cherche le logo d'une radio via les chaînes de Podcasts de Deezer.
    :param size: 'picture_small', 'picture_medium', 'picture_big', 'picture_xl'
    """
    if not radio_name:
        return None

    # Création d'un nom de fichier "propre" (sans espaces ni caractères spéciaux)
    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    frontend_path = f"/img/radios/{file_name}"

    # 1. MISE EN CACHE
    if os.path.exists(local_file_path):
        print(f"[Info] Le logo existe déjà en cache : {local_file_path}")
        return frontend_path

    # 2. RECHERCHE SUR L'API DEEZER (Endpoint Podcast !)
    print(f"[Info] Recherche de '{radio_name}' sur l'API Deezer (Podcasts)...")
    search_query = urllib.parse.quote(radio_name)
    
    # C'est ici que résidait le secret : on cherche dans les podcasts
    url = f"https://api.deezer.com/search/podcast?q={search_query}"

    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()

        if data.get('data') and len(data['data']) > 0:
            # On prend le premier résultat
            podcast_data = data['data'][0]
            image_url = podcast_data.get(size)

            if image_url:
                print(f"[Info] Logo trouvé (via {podcast_data.get('title')}) ! Téléchargement depuis {image_url}...")
                
                # 3. TÉLÉCHARGEMENT ET SAUVEGARDE
                img_data = requests.get(image_url, timeout=5).content
                with open(local_file_path, 'wb') as handler:
                    handler.write(img_data)
                
                print(f"[Succès] Logo sauvegardé physiquement dans : {local_file_path}")
                return frontend_path
            else:
                print("[Erreur] La radio a été trouvée, mais Deezer ne fournit pas de logo.")
        else:
            print("[Erreur] Radio introuvable sur Deezer (aucun podcast associé).")

    except requests.exceptions.RequestException as e:
        print(f"[Deezer API] Erreur réseau pour {radio_name}: {e}")
    except Exception as e:
        print(f"[Deezer API] Erreur inattendue pour {radio_name}: {e}")

    return None

# L'exécution du script en ligne de commande
if __name__ == "__main__":
    # N'hésite pas à tester avec "picture_xl" pour une meilleure qualité sur ton interface web !
    chemin_frontend = fetch_deezer_radio_logo(radio_name, size="picture_xl")
    
    print("\n--- Résultat Final ---")
    if chemin_frontend:
        print(f"Chemin à renvoyer au Frontend : {chemin_frontend}")
    else:
        print("Échec de l'opération.")