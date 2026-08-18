import socket
import time
import logging
from typing import List, Dict, Optional, Tuple

# Constantes d'injection et de pare-feu
REMOTE_SERVICES_INJECTION = ";touch /tmp/remote_services;/etc/init.d/sshd start"
FW_SCRIPT = "/etc/init.d/Firewalls/update_iptables"
BLOCK_17000_MARKER = "# Block 17000 (added by AfterTouch)"

class DefaultTelnetURLs:
    """Structure factice pour remplacer l'appel manquant defaultTelnetURLs du Go"""
    def __init__(self, service_url: str):
        self.bmx_registry = f"{service_url}/bmx"
        self.stats = f"{service_url}/stats"
        self.sw_update = f"{service_url}/update"

class Manager:
    def __init__(self, telnet_client=None, ssh_client=None):
        # En Python, on injecterait probablement des instances ou des fabriques 
        # (factories) pour gérer les connexions Telnet et SSH.
        self.telnet_client = telnet_client
        self.ssh_client = ssh_client

    def enable_ssh_via_telnet(self, device_ip: str, service_url: str) -> str:
        """
        Amorce le SSH sur une enceinte via son shell sur le port 17000.
        """
        marge_injected = service_url + REMOTE_SERVICES_INJECTION
        sw_update = service_url + "/update"
        return self.set_bose_urls_via_telnet(device_ip, marge_injected, sw_update)

    def reset_bose_urls(self, device_ip: str, service_url: str) -> str:
        """
        Restaure des boseurls propres après l'activation de SSH.
        """
        return self.set_bose_urls_via_telnet(device_ip, service_url, service_url + "/update")

    def enable_ssh_via_telnet_full_config(self, device_ip: str, service_url: str) -> str:
        """
        Variante pour les appareils où l'injection simple est acceptée mais où sshd ne démarre pas.
        """
        u = DefaultTelnetURLs(service_url)
        marge_injected = service_url + REMOTE_SERVICES_INJECTION

        cmds = [
            f'sys configuration bmxRegistryUrl "{u.bmx_registry}"',
            f'sys configuration statsServerUrl "{u.stats}"',
            f'sys configuration margeServerUrl "{marge_injected}"',
            f'sys configuration swUpdateUrl "{u.sw_update}"',
            f'envswitch boseurls set "{marge_injected}" "{u.sw_update}"',
        ]

        return self._run_telnet_injection(device_ip, [service_url, u.sw_update], cmds)

    def _run_telnet_injection(self, device_ip: str, forbid_quote: List[str], cmds: List[str]) -> str:
        """
        Ouvre le shell 17000 et exécute une liste ordonnée de commandes.
        """
        if not self.telnet_client:
            raise ValueError("telnet not configured: Manager.telnet_client is None")

        for v in forbid_quote:
            if '"' in v:
                raise ValueError("boseurls values must not contain a double quote")

        logs = []

        try:
            # Implémentation théorique du client Telnet
            self.telnet_client.dial(device_ip, 17000)
            
            banner = self.telnet_client.probe()
            if banner:
                logs.append(f'Telnet banner: "{banner.strip()}"')

            for cmd in cmds:
                resp = self.telnet_client.send_command(cmd)
                logs.append(f"→ {cmd}\n{resp.rstrip()}")

                if self._is_command_not_found(resp):
                    raise RuntimeError(f'device rejected "{cmd}" (firmware does not expose this command)')

            try:
                verify = self.telnet_client.send_command("getpdo CurrentSystemConfiguration")
                logs.append(f"→ getpdo CurrentSystemConfiguration\n{verify.rstrip()}")
            except Exception:
                pass # Erreur tolérée selon la philosophie "forgiving" du code Go

        except Exception as e:
            raise RuntimeError(f"Telnet injection failed on {device_ip}: {e}") from e
        finally:
            self.telnet_client.close()

        return "\n".join(logs) + "\n"

    def set_bose_urls_via_telnet(self, device_ip: str, marge: str, sw_update: str) -> str:
        """
        Exécute la commande `envswitch boseurls set` via Telnet.
        """
        if not self.telnet_client:
            raise ValueError("telnet not configured: Manager.telnet_client is None")

        if '"' in marge or '"' in sw_update:
            raise ValueError("boseurls values must not contain a double quote")

        logs = []

        try:
            self.telnet_client.dial(device_ip, 17000)
            
            banner = self.telnet_client.probe()
            if banner:
                logs.append(f'Telnet banner: "{banner.strip()}"')

            cmd = f'envswitch boseurls set "{marge}" "{sw_update}"'
            resp = self.telnet_client.send_command(cmd)
            
            logs.append(f"→ {cmd}\n{resp.rstrip()}")

            if self._is_command_not_found(resp):
                raise RuntimeError(f'device rejected "{cmd}" (firmware does not expose envswitch)')

        except Exception as e:
            raise RuntimeError(f"Telnet dial or command failed on {device_ip}: {e}") from e
        finally:
            self.telnet_client.close()

        return "\n".join(logs) + "\n"

    def close_17000(self, device_ip: str) -> str:
        """
        Bloque l'accès LAN au shell de diagnostic port-17000 via SSH.
        """
        if not self.ssh_client:
            raise ValueError("ssh not configured: Manager.ssh_client is None")

        persist = (
            f"grep -q '{BLOCK_17000_MARKER}' {FW_SCRIPT} 2>/dev/null || cat >> {FW_SCRIPT} <<'AFTEREOF'\n\n"
            f"{BLOCK_17000_MARKER}\n"
            "iptables -I INPUT -p tcp --dport 17000 -j DROP\n"
            "iptables -I INPUT -p tcp --dport 17000 -i lo -j ACCEPT\n"
            "AFTEREOF"
        )

        steps = [
            {"desc": "remount / read-write", "cmd": "mount / -o rw,remount"},
            {"desc": "persist firewall rule", "cmd": persist},
            {"desc": "apply firewall rule now", "cmd": "iptables -I INPUT -p tcp --dport 17000 -j DROP; iptables -I INPUT -p tcp --dport 17000 -i lo -j ACCEPT"},
        ]

        return self._run_ssh_steps(device_ip, steps)

    def install_authorized_key(self, device_ip: str, public_key: str) -> str:
        """
        Installe une clé publique SSH pour l'utilisateur root.
        """
        if not self.ssh_client:
            raise ValueError("ssh not configured: Manager.ssh_client is None")

        key = public_key.strip()
        if not key:
            raise ValueError("public key is empty")

        logs = []
        try:
            # Création du dossier .ssh
            out = self.ssh_client.run(device_ip, "mount / -o rw,remount && mkdir -p -m 700 /home/root/.ssh")
            logs.append(f"→ prepare /home/root/.ssh\n{out.strip()}")

            # Upload de la clé (Nécessitera une méthode SFTP/SCP dans votre client SSH)
            self.ssh_client.upload_content(device_ip, f"{key}\n".encode('utf-8'), "/home/root/.ssh/authorized_keys")

            # Changement des droits
            out = self.ssh_client.run(device_ip, "chmod 600 /home/root/.ssh/authorized_keys")
            logs.append(f"→ chmod authorized_keys\n{out.strip()}")

            logs.append("Installed authorized_keys for root.")
        except Exception as e:
            raise RuntimeError(f"Failed to install authorized key: {e}") from e

        return "\n".join(logs) + "\n"

    def _run_ssh_steps(self, device_ip: str, steps: List[Dict[str, str]]) -> str:
        """
        Exécute une liste ordonnée de commandes shell via SSH.
        """
        logs = []
        for step in steps:
            try:
                out = self.ssh_client.run(device_ip, step["cmd"])
                logs.append(f"→ {step['desc']}\n{out.strip()}")
            except Exception as e:
                raise RuntimeError(f"{step['desc']}: {e}") from e

        return "\n".join(logs) + "\n"

    @staticmethod
    def _is_command_not_found(resp: str) -> bool:
        """Vérifie si la réponse indique que la commande est introuvable."""
        # À adapter selon le comportement exact du shell Bose
        return "not found" in resp.lower() or "unknown command" in resp.lower()


def wait_for_ssh_port(device_ip: str, timeout_seconds: int) -> None:
    """
    Sonde le port TCP 22 sur l'enceinte jusqu'à acceptation ou timeout.
    """
    deadline = time.time() + timeout_seconds

    while True:
        try:
            # Tente de se connecter avec un timeout court
            conn = socket.create_connection((device_ip, 22), timeout=3)
            conn.close()
            return  # Connexion réussie
        except (socket.timeout, ConnectionRefusedError, OSError):
            if time.time() > deadline:
                raise TimeoutError(f"ssh (:22) on {device_ip} not reachable within {timeout_seconds}s")
            
            time.sleep(3)