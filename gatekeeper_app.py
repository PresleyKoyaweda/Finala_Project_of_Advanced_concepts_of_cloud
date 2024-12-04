import os
from flask import Flask, request, jsonify
import requests
import logging

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gatekeeper.log"),  # Log to a file
        logging.StreamHandler()  # Log to console
    ]
)
logger = logging.getLogger(__name__)

# Fichier requis
trust_host_ip_file = "public_ip_trust-host.txt"

# Vérification de l'existence du fichier
if not os.path.exists(trust_host_ip_file):
    logger.error(f"Error: {trust_host_ip_file} is missing.")
    raise FileNotFoundError(f"Error: {trust_host_ip_file} is missing.")

# Charger l'IP du Trusted Host
def read_ip(file_path):
    try:
        with open(file_path, 'r') as file:
            ip = file.read().strip()
            if not ip:
                raise ValueError(f"{file_path} is empty.")
            return ip
    except Exception as e:
        logger.error(f"Error reading IP from {file_path}: {e}")
        raise

TRUST_HOST_IP = read_ip(trust_host_ip_file)

# Initialisation de l'application Flask
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """
    Endpoint pour vérifier si le service est en bonne santé.
    """
    return jsonify({"status": "ok"})

@app.route('/set_strategy/<strategy>', methods=['GET'])
def set_strategy(strategy):
    """
    Définit la stratégie sur le Trusted Host.
    """
    valid_strategies = ["direct", "random", "customized"]
    if strategy not in valid_strategies:
        logger.warning(f"Invalid strategy requested: {strategy}")
        return jsonify({"status": "error", "message": f"Invalid strategy: {strategy}"}), 400

    try:
        trusted_host_url = f'http://{TRUST_HOST_IP}:5000/set_strategy/{strategy}'
        response = requests.get(trusted_host_url, timeout=5)
        if response.status_code == 200:
            logger.info(f"Strategy set to {strategy} successfully on Trusted Host.")
            return jsonify({"status": "success", "strategy": strategy})
        else:
            logger.error(f"Error setting strategy on Trusted Host: {response.text}")
            return jsonify({"status": "error", "message": response.text}), response.status_code
    except requests.RequestException as e:
        logger.error(f"Error communicating with Trusted Host: {e}")
        return jsonify({"status": "error", "message": f"Unable to set strategy: {e}"}), 500

@app.route('/query', methods=['POST'])
def handle_request():
    """
    Transmet les requêtes SQL au Trusted Host.
    """
    try:
        data = request.json
        if not data or 'query' not in data:
            logger.warning("Invalid request: Missing 'query' field.")
            return jsonify({"status": "error", "message": "Query is missing"}), 400

        query = data['query']
        logger.info(f"Received query: {query}")

        # Forward the query to Trusted Host
        trusted_host_url = f'http://{TRUST_HOST_IP}:5000/query'
        response = requests.post(trusted_host_url, json=data, timeout=10)

        if response.status_code == 200:
            logger.info("Query successfully forwarded to Trusted Host.")
            return response.json()
        else:
            logger.error(f"Error from Trusted Host: {response.text}")
            return jsonify({"status": "error", "message": response.text}), response.status_code
    except requests.RequestException as e:
        logger.error(f"Error communicating with Trusted Host: {e}")
        return jsonify({"status": "error", "message": f"Unable to process request: {e}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.critical(f"Failed to start the application: {e}")
        raise
