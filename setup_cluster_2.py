import os
import paramiko
import time

# ===========================
# Configuration et Fichiers
# ===========================
key_path = "my-key-pair.pem"
proxy_ip_file = "public_ip_proxy.txt"
manager_ip_file = "public_ip_manager.txt"
worker1_ip_file = "public_ip_worker1.txt"
worker2_ip_file = "public_ip_worker2.txt"
trust_host_ip_file = "public_ip_trust-host.txt"
gatekeeper_ip_file = "public_ip_gatekeeper.txt"
password_file_path = "PW.txt"

# Fichiers additionnels à transférer
additional_files = [
    key_path,
    proxy_ip_file,
    manager_ip_file,
    worker1_ip_file,
    worker2_ip_file,
    trust_host_ip_file,
    gatekeeper_ip_file,
    password_file_path
]

# Vérification de l'existence des fichiers
def check_file_exists(file_path):
    """
    Vérifie si un fichier existe localement. Lève une erreur si introuvable.
    """
    if not os.path.exists(file_path):
        raise RuntimeError(f"Erreur : Le fichier {file_path} est introuvable.")
    return True

# Validation des fichiers nécessaires
for file in additional_files:
    check_file_exists(file)

# Chargement des adresses IP à partir des fichiers
def read_ip(file_path):
    """
    Lit la première ligne d'un fichier et supprime les espaces inutiles.
    """
    with open(file_path, 'r') as file:
        return file.read().strip()

# Chargement des adresses IP
proxy_ip = read_ip(proxy_ip_file)
manager_ip = read_ip(manager_ip_file)
worker1_ip = read_ip(worker1_ip_file)
worker2_ip = read_ip(worker2_ip_file)
trust_host_ip = read_ip(trust_host_ip_file)
gatekeeper_ip = read_ip(gatekeeper_ip_file)

# ===========================
# Utilitaires pour SSH
# ===========================
def execute_with_retry(ssh, cmd, retries=5, wait=30):
    """
    Exécute une commande avec plusieurs tentatives en cas de verrou APT.
    """
    for attempt in range(retries):
        stdin, stdout, stderr = ssh.exec_command(cmd)
        error = stderr.read().decode()
        if not error or "Could not get lock" not in error:
            return stdout.read().decode(), error
        if attempt < retries - 1:
            print(f"Verrou APT détecté, nouvelle tentative dans {wait} secondes...")
            time.sleep(wait)
        else:
            raise RuntimeError(f"Échec de la commande après {retries} tentatives : {cmd}")

# ===========================
# Classe ServiceDeployer
# ===========================
class ServiceDeployer:
    def __init__(self, key_path):
        """
        Initialise le déployeur avec le chemin de la clé SSH.
        """
        self.key_path = key_path

    def transfer_file(self, sftp, local_path, remote_path):
        """
        Transfère un fichier vers le serveur distant.
        """
        try:
            print(f"Transfert de {local_path} vers {remote_path}...")
            sftp.put(local_path, remote_path)
            print(f"Transfert réussi de {local_path} vers {remote_path}.")
            return True
        except Exception as e:
            print(f"Erreur pendant le transfert : {str(e)}")
            return False

    def create_service_file(self, ssh, service_name, working_dir):
        """
        Crée un fichier systemd pour gérer le service.
        """
        service_content = f'''[Unit]
Description={service_name} service
After=network.target

[Service]
User=ubuntu
WorkingDirectory={working_dir}
ExecStart={working_dir}/start_{service_name}.sh
Environment=PYTHONUNBUFFERED=1
Restart=always

[Install]
WantedBy=multi-user.target
'''
        commands = [
            f'echo "{service_content}" | sudo tee /etc/systemd/system/{service_name}.service',
            'sudo systemctl daemon-reload',
            f'sudo systemctl enable {service_name}',
            f'sudo systemctl restart {service_name}'
        ]
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            if stdout.channel.recv_exit_status() != 0:
                print(f"Erreur lors de la création du fichier de service pour {service_name} : {stderr.read().decode()}")
                return False
        return True

    def deploy_service(self, host, service_name, local_code_path, args, additional_files):
        """
        Déploie un service sur une instance EC2 et transfère les fichiers requis.
        """
        try:
            print(f"\nDéploiement de {service_name} sur {host}...")

            # Connexion SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=host, username='ubuntu', key_filename=self.key_path, timeout=60)

            # Configuration de l'environnement
            setup_commands = [
                'sudo apt-get update -y',
                'sudo apt-get install -y python3-venv',
                'python3 -m venv /home/ubuntu/venv',
                '/home/ubuntu/venv/bin/pip install flask requests mysql-connector-python'
            ]
            for cmd in setup_commands:
                stdout, error = execute_with_retry(ssh, cmd)
                if error:
                    print(f"Erreur pendant la configuration : {error}")
                    return False

            # Connexion SFTP
            sftp = ssh.open_sftp()

            # Transfert du code de service
            remote_code_path = f'/home/ubuntu/{service_name}.py'
            if not self.transfer_file(sftp, local_code_path, remote_code_path):
                return False

            # Transfert des fichiers additionnels
            for file in additional_files:
                remote_file_path = f'/home/ubuntu/{os.path.basename(file)}'
                if not self.transfer_file(sftp, file, remote_file_path):
                    return False

            # Création d'un script de démarrage
            start_script = f'''#!/bin/bash
source /home/ubuntu/venv/bin/activate
python3 {remote_code_path} {' '.join(map(str, args))}
'''
            remote_start_script = f'/home/ubuntu/start_{service_name}.sh'
            with sftp.file(remote_start_script, 'w') as f:
                f.write(start_script)
            ssh.exec_command(f'sudo chmod +x {remote_start_script}')

            # Création et activation du service
            if not self.create_service_file(ssh, service_name, '/home/ubuntu'):
                return False

            # Vérification du statut du service
            stdin, stdout, stderr = ssh.exec_command(f'systemctl is-active {service_name}')
            service_status = stdout.read().decode().strip()
            if service_status != "active":
                print(f"Erreur : Le service {service_name} n'est pas actif. Statut : {service_status}")
                return False

            ssh.close()
            print(f"Service {service_name} déployé avec succès sur {host}.")
            return True

        except Exception as e:
            print(f"Erreur pendant le déploiement de {service_name} : {str(e)}")
            return False

# ===========================
# Main Workflow
# ===========================
def main():
    """
    Fonction principale pour déployer les services Proxy, Trusted Host et Gatekeeper.
    """
    deployer = ServiceDeployer(key_path)

    services = {
        "proxy": {
            "host": proxy_ip,
            "local_code_path": "proxy_app.py",
            "args": [manager_ip, f"{worker1_ip},{worker2_ip}"]
        },
        "trusted_host": {
            "host": trust_host_ip,
            "local_code_path": "trusted_host.py",
            "args": [proxy_ip]
        },
        "gatekeeper": {
            "host": gatekeeper_ip,
            "local_code_path": "gatekeeper_app.py",
            "args": [trust_host_ip]
        }
    }

    for service_name, config in services.items():
        if not deployer.deploy_service(
            host=config["host"],
            service_name=service_name,
            local_code_path=config["local_code_path"],
            args=config["args"],
            additional_files=additional_files
        ):
            print(f"Échec du déploiement pour {service_name}.")
            return

    print("\nTous les services ont été déployés avec succès!")

if __name__ == "__main__":
    main()
