import os
from flask import Flask, request, jsonify
import mysql.connector
import time
import random
import logging
from enum import Enum

# ===========================
# Configuration de l'application Flask et des logs
# ===========================
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("proxy.log"),  # Log to a file
        logging.StreamHandler()  # Log to console
    ]
)
logger = logging.getLogger(__name__)

# ===========================
# Vérification des fichiers requis
# ===========================
key_path = "my-key-pair.pem"
password_file_path = "PW.txt"
manager_ip_file = "public_ip_manager.txt"
worker_ips_files = ["public_ip_worker1.txt", "public_ip_worker2.txt"]

required_files = [key_path, password_file_path, manager_ip_file] + worker_ips_files
for file in required_files:
    if not os.path.exists(file):
        logger.error(f"Error: {file} is missing.")
        raise FileNotFoundError(f"Error: {file} is missing.")

# ===========================
# Chargement des mots de passe et adresses IP
# ===========================
def load_file_content(file_path):
    with open(file_path, 'r') as f:
        content = f.read().strip()
        if not content:
            raise ValueError(f"File {file_path} is empty.")
        return content

MYSQL_PASSWORD = load_file_content(password_file_path)
MANAGER_IP = load_file_content(manager_ip_file)
WORKERS = [load_file_content(worker_file) for worker_file in worker_ips_files]
MYSQL_USER = os.getenv("MYSQL_USER", "admin")
MYSQL_DB = os.getenv("MYSQL_DB", "sakila")

# ===========================
# Enumération des stratégies
# ===========================
class Strategy(Enum):
    DIRECT = "direct"
    RANDOM = "random"
    CUSTOMIZED = "customized"

# ===========================
# Port associé aux stratégies
# ===========================
STRATEGY_PORTS = {
    Strategy.DIRECT.value: 3306,
    Strategy.RANDOM.value: 3306,
    Strategy.CUSTOMIZED.value: 3306
}

# ===========================
# Classe ProxyManager
# ===========================
class ProxyManager:
    def __init__(self, manager_host, worker_hosts, mysql_user, mysql_password):
        self.manager_host = manager_host
        self.worker_hosts = worker_hosts
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.current_strategy = Strategy.DIRECT.value
        self.current_port = STRATEGY_PORTS[Strategy.DIRECT.value]
        logger.info(f"ProxyManager initialized with strategy: {self.current_strategy}, port: {self.current_port}")

    def _get_connection(self, host, port):
        try:
            return mysql.connector.connect(
                host=host,
                port=port,
                user=self.mysql_user,
                password=self.mysql_password,
                database=MYSQL_DB,
                connect_timeout=10
            )
        except mysql.connector.Error as e:
            logger.error(f"Connection to {host}:{port} failed: {e}")
            raise e

    def route_request(self, query, params=None, is_write=False):
        target_host, target_port = None, None
        if is_write or self.current_strategy == Strategy.DIRECT.value:
            target_host, target_port = self.manager_host, self.current_port
        elif self.current_strategy == Strategy.RANDOM.value:
            target_host = random.choice(self.worker_hosts)
            target_port = self.current_port
        elif self.current_strategy == Strategy.CUSTOMIZED.value:
            target_host = self._get_fastest_worker()
            target_port = self.current_port

        if not target_host:
            return {"status": "error", "message": "No available workers or strategy not implemented"}

        return self._execute_query(target_host, target_port, query, params, is_write)

    def _get_fastest_worker(self):
        response_times = {}
        for worker in self.worker_hosts:
            start_time = time.time()
            try:
                conn = self._get_connection(worker, self.current_port)
                conn.close()
                response_times[worker] = time.time() - start_time
            except Exception:
                response_times[worker] = float('inf')

        fastest_worker = min(response_times, key=response_times.get)
        if response_times[fastest_worker] == float('inf'):
            logger.error("All workers are unreachable.")
            return None
        return fastest_worker

    def _execute_query(self, host, port, query, params, is_write):
        try:
            conn = self._get_connection(host, port)
            cursor = conn.cursor()
            cursor.execute(query, params or ())

            if cursor.with_rows:
                result = cursor.fetchall()
                response = {
                    "status": "success",
                    "result": result,
                    "host": host,
                    "port": port,
                    "strategy": self.current_strategy
                }
            else:
                conn.commit()
                response = {
                    "status": "success",
                    "message": "Query executed successfully.",
                    "host": host,
                    "port": port,
                    "strategy": self.current_strategy
                }

            cursor.close()
            conn.close()
            return response
        except mysql.connector.Error as e:
            logger.error(f"Query failed on {host}:{port}: {e}")
            return {"status": "error", "message": f"Query failed on {host}:{port}: {e}"}

proxy = ProxyManager(MANAGER_IP, WORKERS, MYSQL_USER, MYSQL_PASSWORD)

# ===========================
# Endpoints Flask
# ===========================
@app.route('/set_strategy/<strategy>', methods=['GET'])
def set_strategy(strategy):
    """
    Définit la stratégie utilisée pour le routage des requêtes.
    """
    if strategy not in STRATEGY_PORTS:
        logger.warning(f"Invalid strategy requested: {strategy}")
        return jsonify({"status": "error", "message": f"Invalid strategy: {strategy}"}), 400

    proxy.current_strategy = strategy
    proxy.current_port = STRATEGY_PORTS[strategy]
    logger.info(f"Strategy set to: {strategy}")
    return jsonify({"status": "success", "strategy": strategy, "port": proxy.current_port})

@app.route('/query', methods=['POST'])
def query():
    """
    Reçoit une requête SQL et la transmet selon la stratégie définie.
    """
    data = request.json
    query = data.get("query")
    if not query:
        logger.warning("Query not provided in request.")
        return jsonify({"status": "error", "message": "Query not provided"}), 400

    is_write = any(word in query.upper() for word in ["INSERT", "UPDATE", "DELETE"])
    result = proxy.route_request(query, is_write=is_write)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
