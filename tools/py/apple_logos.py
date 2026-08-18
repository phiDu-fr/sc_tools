import requests
import os
import urllib.parse
import sys

# Vérification des arguments
if len(sys.argv) < 2:
    print("Usage : python radio_logos.py <nom_de_la_radio>")
    sys.exit(1)

radio_name = sys.argv[1]

# Configuration du cache local
LOGOS_DIR = '/home/pi/tmp'
os.makedirs(LOGOS_DIR, exist_ok=True)

def fetch_itunes_radio_logo(radio_name, target_size=600):
    """
    Cherche une station de radio ou sa chaîne officielle sur l'API iTunes
    et télécharge son artwork officiel en haute résolution.
    """
    if not radio_name:
        return None

    # Nom de fichier propre pour le cache
    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    frontend_path = f"/img/radios/{file_name}"

    # 1. Gestion du Cache local
    if os.path.exists(local_file_path):
        print(f"[Cache] Logo déjà présent localement : {local_file_path}")
        return frontend_path

    # 2. Requête sur l'API iTunes
    print(f"[API] Recherche de '{radio_name}' sur iTunes...")
    search_query = urllib.parse.quote(radio_name)
    
    # On cherche dans les catégories "podcast" et "radioStation" combinées pour maximiser le résultat
    url = f"https://itunes.apple.com/search?term={search_query}&media=podcast&limit=5&country=fr"

    try:
        response = requests.get(url, timeout=4)
        response.raise_for_status()
        data = response.json()

        if data.get('resultCount', 0) > 0:
            # On cherche le résultat le plus pertinent
            # Idéalement une chaîne qui correspond bien au nom de la radio
            results = data['results']
            
            # On prend le premier résultat de la liste
            best_match = results[0]
            
            # iTunes fournit des clés comme 'artworkUrl100' ou 'artworkUrl600'
            image_url = best_match.get('artworkUrl600') or best_match.get('artworkUrl100')

            if image_url:
                # Astuce iTunes : On peut modifier dynamiquement la taille dans l'URL pour avoir la résolution exacte voulue
                # Exemple : .../100x100bb.jpg devient .../600x600bb.jpg
                image_url = image_url.replace("100x100", f"{target_size}x{target_size}")
                image_url = image_url.replace("600x600", f"{target_size}x{target_size}")

                print(f"[Match] Trouvé : '{best_match.get('collectionName', radio_name)}'")
                print(f"[Téléchargement] Récupération de l'image haute déf : {image_url}")
                
                # 3. Téléchargement de l'image
                img_response = requests.get(image_url, timeout=5)
                img_response.raise_for_status()
                
                with open(local_file_path, 'wb') as handler:
                    handler.write(img_response.content)
                
                print(f"[Succès] Logo sauvegardé dans : {local_file_path}")
                return frontend_path
        else:
            print("[Erreur] Aucun résultat sur l'API iTunes.")

    except requests.exceptions.RequestException as e:
        print(f"[Erreur Réseau] Impossible de joindre l'API : {e}")
    except Exception as e:
        print(f"[Erreur] Problème inattendu : {e}")

    return None

if __name__ == "__main__":
    # On cible une taille de 600x600 pixels (parfait pour le web, pas trop lourd pour le Raspberry)
    chemin_frontend = fetch_itunes_radio_logo(radio_name, target_size=600)
    print("\n--- Résultat Final ---")
    if chemin_frontend:
        print(f"Chemin pour le Frontend : {chemin_frontend}")
    else:
        print("Échec du téléchargement.")