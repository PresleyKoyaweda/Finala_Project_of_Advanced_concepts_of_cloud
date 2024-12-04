import paramiko
import os
import time
import logging

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Fichiers requis
key_path = "my-key-pair.pem"
password_file_path = "PW.txt"
manager_ip_file = "public_ip_manager.txt"
worker_ips_file = ["public_ip_worker1.txt", "public_ip_worker2.txt"]

# Vérification des fichiers nécessaires
def check_file_exists(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Erreur : Le fichier {file_path} est introuvable.")
    return True

required_files = [key_path, password_file_path, manager_ip_file] + worker_ips_file
for file in required_files:
    check_file_exists(file)

# Lecture des IPs et du mot de passe MySQL
def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read().strip()

mysql_password = read_file(password_file_path)
manager_ip = read_file(manager_ip_file)
worker_ips = [read_file(worker_file) for worker_file in worker_ips_file]

# Classe pour gérer la configuration MySQL
class MySQLClusterManager:
    def __init__(self, key_path):
        self.key_path = key_path

    def setup_mysql_standalone(self, host, mysql_user, mysql_password):
        """
        Configure MySQL sur une instance autonome spécifiée par l'hôte.
        """
        try:
            logging.info(f"Configuration de MySQL et Sysbench sur {host}...")

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Tentatives de connexion SSH avec retries
            for attempt in range(5):
                try:
                    ssh.connect(
                        hostname=host,
                        username='ubuntu',
                        key_filename=self.key_path,
                        timeout=60
                    )
                    break
                except (paramiko.AuthenticationException, paramiko.SSHException) as auth_error:
                    raise RuntimeError(f"Erreur d'authentification SSH pour {host} : {str(auth_error)}")
                except Exception as e:
                    logging.warning(f"Tentative {attempt + 1}/5 de connexion SSH échouée : {str(e)}")
                    if attempt < 4:
                        time.sleep(15)
                    else:
                        raise RuntimeError(f"Impossible de se connecter à {host} après 5 tentatives.")

            # Commandes de configuration MySQL et Sysbench
            commands = [
                'sudo apt-get update -y && sudo apt-get install -y mysql-server sysbench',
                'sudo systemctl start mysql',
                'sudo systemctl enable mysql',
                f'sudo mysqladmin -u root password "{mysql_password}" || true',
                f'sudo mysql -uroot -p"{mysql_password}" -e "ALTER USER \'root\'@\'localhost\' IDENTIFIED WITH mysql_native_password BY \'{mysql_password}\';"',
                'sudo sed -i "s/^bind-address.*/bind-address = 0.0.0.0/" /etc/mysql/mysql.conf.d/mysqld.cnf',
                'echo "max_connections = 500\nwait_timeout = 600\ninteractive_timeout = 600" | sudo tee -a /etc/mysql/mysql.conf.d/mysqld.cnf',
                'sudo systemctl restart mysql',
                f'sudo mysql -uroot -p"{mysql_password}" -e "CREATE USER IF NOT EXISTS \'{mysql_user}\'@\'%\' IDENTIFIED BY \'{mysql_password}\';"',
                f'sudo mysql -uroot -p"{mysql_password}" -e "GRANT ALL PRIVILEGES ON *.* TO \'{mysql_user}\'@\'%\' WITH GRANT OPTION;"',
                f'sudo mysql -uroot -p"{mysql_password}" -e "FLUSH PRIVILEGES;"',
                'wget -q https://downloads.mysql.com/docs/sakila-db.tar.gz -O sakila-db.tar.gz',
                'tar -xf sakila-db.tar.gz',
                f'sudo mysql -uroot -p"{mysql_password}" -e "CREATE DATABASE IF NOT EXISTS sakila;"',
                f'sudo mysql -uroot -p"{mysql_password}" sakila < sakila-db/sakila-schema.sql',
                f'sudo mysql -uroot -p"{mysql_password}" sakila < sakila-db/sakila-data.sql',
                f'sudo sysbench /usr/share/sysbench/oltp_read_only.lua --mysql-db=sakila --mysql-user={mysql_user} --mysql-password={mysql_password} prepare',
                f'sudo sysbench /usr/share/sysbench/oltp_read_only.lua --mysql-db=sakila --mysql-user={mysql_user} --mysql-password={mysql_password} run'
            ]

            # Exécution des commandes avec gestion d'erreurs
            for cmd in commands:
                logging.info(f"Exécution de : {cmd}")
                stdin, stdout, stderr = ssh.exec_command(cmd)
                exit_status = stdout.channel.recv_exit_status()
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()

                if exit_status == 0:
                    logging.info(output)
                else:
                    if "Could not get lock" in error:
                        logging.warning("En attente du déblocage du verrou apt...")
                        time.sleep(15)
                        continue
                    logging.error(f"Commande échouée : {cmd}\nErreur : {error}")
                    raise RuntimeError(f"Commande échouée : {cmd}\nErreur : {error}")

            ssh.close()
            logging.info(f"Configuration de MySQL et Sysbench terminée sur {host}.")
            return True

        except Exception as e:
            logging.error(f"Erreur lors de la configuration de MySQL et Sysbench sur {host} : {str(e)}")
            return False

# Initialisation et configuration du cluster
cluster_manager = MySQLClusterManager(key_path)

mysql_user = "admin"

# Configurer le manager
if not cluster_manager.setup_mysql_standalone(manager_ip, mysql_user, mysql_password):
    logging.error(f"Échec de la configuration de MySQL et Sysbench sur le Manager : {manager_ip}")

# Configurer les workers
for worker_ip in worker_ips:
    if not cluster_manager.setup_mysql_standalone(worker_ip, mysql_user, mysql_password):
        logging.error(f"Échec de la configuration de MySQL et Sysbench sur le Worker : {worker_ip}")
