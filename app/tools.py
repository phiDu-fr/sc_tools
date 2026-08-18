from flask import Blueprint, request, render_template_string
import os
import subprocess
import configparser
import time

import shared

tools_bp = Blueprint('tools_bp', __name__)
TTYD_PORT = 8081  # Port dédié à ttyd (évite le conflit avec le WS Bose 8080)

@tools_bp.route('/tools')
def tools_dashboard():
    config = configparser.ConfigParser()
    config.read(shared.TOOLS_CONFIG_PATH)
    sections = {s: dict(config.items(s)) for s in config.sections()}
    
    # Chemin absolu adapté à ton montage Docker (./www monté dans /app/www)
    html_path = os.path.join(os.path.dirname(__file__), 'www', 'tools.html')
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    return render_template_string(html_content, config=sections)

@tools_bp.route('/run_tool', methods=['POST'])
def run_tool():
    section = request.form.get('section')
    config = configparser.ConfigParser()
    config.read(shared.TOOLS_CONFIG_PATH)
    
    if section not in config: 
        return "Erreur", 400
        
    script_path = config[section]['script']
    args = []
    for i in range(1, 4):
        if f'arg{i}_label' in config[section]: 
            args.append(request.form.get(f'arg{i}', ''))

    # 1. On tue violemment l'ancien processus
    os.system("pkill -9 ttyd")
    time.sleep(0.5)
    
    # 2. Construction de la commande : on lance le script, puis on reste dans un shell (exec bash)
    # On transforme la liste args en chaîne de caractères pour le bash -c
    full_args = " ".join(args)
    cmd = f"{script_path} {full_args}; exec bash"
    
    # 3. Lancement avec bash -c pour maintenir la session ouverte
    subprocess.Popen(["ttyd", "-W", "-p", str(TTYD_PORT), "-i", "0.0.0.0", "bash", "-c", cmd])
    
    # 4. On attend 1 seconde pour que ttyd ait le temps d'écouter
    time.sleep(1.0)
    
    return f"<script>window.location.href = 'http://{request.host.split(':')[0]}:{TTYD_PORT}';</script>"