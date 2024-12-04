import os
from flask import Flask, request, jsonify
import requests
import logging

# ===========================
# Configuration et Logs
# ===========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("trusted_host.log"),  # Log to a file
        logging.StreamHandler()  # Log to console
    ]
)
logger = logging.getLogger(__name__)

# ===========================
# Fichiers de Configuration
# ===========================
proxy_ip_file = "public_ip_proxy.txt"

def check_file_exists(file_path):
    """
    Vérifie si un fichier existe. Lève une erreur s'il est introuvable.
    """
    if not os.path.exists(file_path):
        logger.error(f"Error: {file_path} is missing.")
        raise FileNotFoundError(f"Error: {file_path} is missing.")
    return True

required_files = [proxy_ip_file]
for file in required_files:
    check_file_exists(file)

def read_ip(file_path):
    """
    Lit la première ligne d'un fichier contenant une adresse IP.
    """
    try:
        with open(file_path, 'r') as file:
            ip = file.read().strip()
            if not ip:
                raise ValueError(f"{file_path} is empty.")
            return ip
    except Exception as e:
        logger.error(f"Error reading IP from {file_path}: {e}")
        raise

# Chargement de l'adresse IP du Proxy
PROXY_IP = read_ip(proxy_ip_file)

# ===========================
# Application Flask
# ===========================
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """
    Vérifie l'état de santé du service Trusted Host.
    """
    return jsonify({"status": "ok"})

@app.route('/set_strategy/<strategy>', methods=['GET'])
def set_strategy(strategy):
    """
    Transmet la stratégie choisie au Proxy.
    """
    valid_strategies = ["direct", "random", "customized"]
    if strategy not in valid_strategies:
        logger.warning(f"Invalid strategy requested: {strategy}")
        return jsonify({"status": "error", "message": f"Invalid strategy: {strategy}"}), 400

    try:
        proxy_url = f'http://{PROXY_IP}:5000/set_strategy/{strategy}'
        response = requests.get(proxy_url, timeout=5)
        if response.status_code == 200:
            logger.info(f"Strategy set to {strategy} successfully on Proxy.")
            return jsonify({"status": "success", "strategy": strategy})
        else:
            logger.error(f"Error setting strategy on Proxy: {response.text}")
            return jsonify({"status": "error", "message": response.text}), response.status_code
    except requests.RequestException as e:
        logger.error(f"Error communicating with Proxy: {e}")
        return jsonify({"status": "error", "message": f"Unable to set strategy: {e}"}), 500

@app.route('/query', methods=['POST'])
def handle_request():
    """
    Transmet les requêtes SQL au service Proxy.
    """
    try:
        data = request.json
        if not data or 'query' not in data:
            logger.warning("Invalid request: Missing 'query' field.")
            return jsonify({"status": "error", "message": "Query is missing"}), 400

        logger.info(f"Received query: {data['query']}")

        # URL du Proxy
        proxy_url = f'http://{PROXY_IP}:5000/query'
        response = requests.post(proxy_url, json=data, timeout=10)

        if response.status_code == 200:
            logger.info("Query successfully forwarded to Proxy.")
            return response.json()
        else:
            logger.error(f"Error from Proxy: {response.text}")
            return jsonify({"status": "error", "message": response.text}), response.status_code
    except requests.RequestException as e:
        logger.error(f"Error communicating with Proxy: {e}")
        return jsonify({"status": "error", "message": f"Unable to process request: {e}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    try:
        logger.info("Starting Trusted Host service...")
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.critical(f"Failed to start the Trusted Host service: {e}")
        raise
