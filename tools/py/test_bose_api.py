import requests
import unittest
import xml.etree.ElementTree as ET
import logging
import sys

# Configuration de l'environnement de test
# À adapter avec l'IP statique de l'enceinte SoundTouch cible sur le réseau local
BOSE_IP = "192.168.1.65" 
PORT = "8090"
BASE_URL = f"http://{BOSE_IP}:{PORT}"

# Configuration du logging pour un suivi professionnel de l'exécution
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

class TestBoseSoundTouchAPI(unittest.TestCase):
    """
    Table de test complète pour l'API locale Bose SoundTouch.
    Valide le fonctionnement des requêtes HTTP GET/POST et l'intégrité des payloads XML.
    """

    @classmethod
    def setUpClass(cls):
        logging.info(f"Initialisation de la suite de tests sur {BASE_URL}")
        cls.session = requests.Session()
        cls.timeout = 5

    def test_01_endpoint_info(self):
        """Valide la récupération des informations matérielles de l'appareil."""
        url = f"{BASE_URL}/info"
        response = self.session.get(url, timeout=self.timeout)
        
        self.assertEqual(response.status_code, 200, f"Échec de connexion à {url}")
        
        root = ET.fromstring(response.text)
        self.assertEqual(root.tag, "info", "La racine XML retournée n'est pas <info>")
        
        device_id = root.attrib.get('deviceID')
        self.assertIsNotNone(device_id, "L'attribut deviceID est manquant dans la réponse")
        logging.info(f"Test Info OK - DeviceID: {device_id}")

    def test_02_endpoint_now_playing(self):
        """Valide la lecture du statut actuel de l'enceinte."""
        url = f"{BASE_URL}/now_playing"
        response = self.session.get(url, timeout=self.timeout)
        
        self.assertEqual(response.status_code, 200)
        
        root = ET.fromstring(response.text)
        self.assertEqual(root.tag, "nowPlaying", "La racine XML retournée n'est pas <nowPlaying>")
        
        source = root.attrib.get('source')
        self.assertIsNotNone(source, "L'attribut source est introuvable")
        logging.info(f"Test NowPlaying OK - Source actuelle: {source}")

    def test_03_endpoint_volume_read_write(self):
        """Valide la capacité à lire et à écrire une nouvelle valeur de volume."""
        url = f"{BASE_URL}/volume"

        # Lecture du volume
        response_get = self.session.get(url, timeout=self.timeout)
        self.assertEqual(response_get.status_code, 200)
        
        root = ET.fromstring(response_get.text)
        current_volume_node = root.find('targetvolume')
        self.assertIsNotNone(current_volume_node, "Nœud <targetvolume> introuvable")
        
        current_volume = int(current_volume_node.text)
        self.assertTrue(0 <= current_volume <= 100, "Le volume lu est hors limites (0-100)")
        logging.info(f"Volume actuel lu: {current_volume}")

        # Écriture du volume (test idempotent en réinjectant la même valeur)
        payload = f"<volume>{current_volume}</volume>"
        response_post = self.session.post(url, data=payload, timeout=self.timeout)
        self.assertEqual(response_post.status_code, 200, "L'API a refusé la modification du volume")
        logging.info("Test écriture Volume OK")

    def test_04_endpoint_presets(self):
        """Valide la structure des presets configurés sur l'appareil."""
        url = f"{BASE_URL}/presets"
        response = self.session.get(url, timeout=self.timeout)
        
        self.assertEqual(response.status_code, 200)
        
        root = ET.fromstring(response.text)
        self.assertEqual(root.tag, "presets", "La racine XML retournée n'est pas <presets>")
        
        presets = root.findall('preset')
        logging.info(f"Test Presets OK - {len(presets)} preset(s) trouvé(s)")

    def test_05_invalid_endpoint(self):
        """Valide le comportement de l'API face à une route inexistante."""
        url = f"{BASE_URL}/endpoint_inexistant_sc_tools"
        response = self.session.get(url, timeout=self.timeout)
        self.assertEqual(response.status_code, 404, "L'API doit retourner une erreur 404 pour une route invalide")
        logging.info("Test gestion d'erreur 404 OK")

if __name__ == "__main__":
    # Exécution avec un niveau de verbosité élevé pour un débogage précis
    unittest.main(verbosity=2)