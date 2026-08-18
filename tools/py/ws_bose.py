import websocket
import threading
import time
import sys

# --- GESTION DES ARGUMENTS VIA LIGNE DE COMMANDE ---
ip_suffix = "100"
debug_mode = False

# Argument 1 : Suffixe IP
if len(sys.argv) > 1:
    ip_suffix = sys.argv[1]

# Argument 2 : Mode Debug
if len(sys.argv) > 2:
    if sys.argv[2].lower() == "debug":
        debug_mode = True

# Reconstitution de l'adresse IP complète
SPEAKER_IP = f"192.168.1.{ip_suffix}"

def on_message(ws, message):
    print(f"\n--- [NOUVEAU MESSAGE XML DE L'ENCEINTE] {ip_suffix} ---")
    print(message)

def on_error(ws, error):
    print(f"\n[ERREUR] : {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"\n[CONNEXION FERMÉE {ip_suffix}] L'enceinte a coupé le flux.")

def on_open(ws):
    print(f"\n[SUCCÈS] Connecté au WebSocket de l'enceinte {SPEAKER_IP} !")
    print("En attente des événements en temps réel (change le volume ou de piste sur l'enceinte pour tester)...")

    # On peut aussi lui envoyer des ordres dans ce tunnel !
    # (Exemple : simuler un appui sur le bouton PLAY/PAUSE)
    # ws.send('<key state="press" sender="Gabbo">PLAY_PAUSE</key>')
    # ws.send('<key state="release" sender="Gabbo">PLAY_PAUSE</key>')

def start_listening(enable_debug):
    # Activation du debug réseau selon l'argument 2
    websocket.enableTrace(enable_debug) 
    ws_url = f"ws://{SPEAKER_IP}:8080/"
    
    # Clé secrète Bose (gabbo)
    custom_headers = ["Sec-WebSocket-Protocol: gabbo"]
    
    ws = websocket.WebSocketApp(
        ws_url,
        header=custom_headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Lancement du client
    ws.run_forever()

if __name__ == "__main__":
    mode_text = " (Mode DEBUG activé)" if debug_mode else ""
    print(f"Tentative de connexion à {SPEAKER_IP}{mode_text}...")
    start_listening(debug_mode)