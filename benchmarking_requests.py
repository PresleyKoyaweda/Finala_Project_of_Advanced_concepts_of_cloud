import time
import requests
import os

# Nombre de requêtes pour le benchmark
NB_REQUESTS = 1000

# Fichier contenant l'adresse IP du Gatekeeper
GATEKEEPER_IP_FILE = "public_ip_gatekeeper.txt"

# Fonction pour lire l'adresse IP du Gatekeeper
def read_gatekeeper_ip(file_path):
    """
    Lit l'adresse IP du Gatekeeper à partir d'un fichier.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Erreur : le fichier {file_path} est introuvable.")
    with open(file_path, 'r') as f:
        return f.read().strip()

# Fonction pour exécuter le benchmark pour une stratégie spécifique
def run_proxy_benchmark(gatekeeper_ip, strategy, timeout=5):
    """
    Teste la performance d'une stratégie du proxy en envoyant des requêtes de lecture et d'écriture.
    """
    print(f"\nExécution du benchmark pour la stratégie : {strategy}...")

    # Structure pour stocker les résultats
    results = {
        'read': {'success': 0, 'fail': 0, 'time': 0},
        'write': {'success': 0, 'fail': 0, 'time': 0}
    }

    # 1. Configuration de la stratégie
    if strategy != "direct":
        try:
            response = requests.get(
                f'http://{gatekeeper_ip}:5000/set_strategy/{strategy}', timeout=timeout
            )
            if response.status_code != 200:
                print(f"Échec de la configuration de la stratégie {strategy} : {response.text}")
                return results
        except Exception as e:
            print(f"Erreur lors de la configuration de la stratégie : {str(e)}")
            return results

    # 2. Benchmark de lecture
    start_time = time.time()
    for i in range(NB_REQUESTS):
        try:
            response = requests.post(
                f'http://{gatekeeper_ip}:5000/query',
                json={'query': f'SELECT * FROM actor WHERE actor_id = {(i % 200) + 1}'},
                timeout=timeout
            )
            if response.status_code == 200 and response.json().get('status') == 'success':
                results['read']['success'] += 1
            else:
                results['read']['fail'] += 1
        except Exception as e:
            results['read']['fail'] += 1
            print(f"Erreur lors de la requête de lecture : {str(e)}")
        
        if i % 100 == 0:
            print(f"{i} requêtes de lecture complétées")

    results['read']['time'] = time.time() - start_time

    # 3. Benchmark d'écriture
    start_time = time.time()
    for i in range(NB_REQUESTS):
        try:
            response = requests.post(
                f'http://{gatekeeper_ip}:5000/query',
                json={'query': f'INSERT INTO actor (first_name, last_name) VALUES ("Test{i}", "User{i}")'},
                timeout=timeout
            )
            if response.status_code == 200 and response.json().get('status') == 'success':
                results['write']['success'] += 1
            else:
                results['write']['fail'] += 1
        except Exception as e:
            results['write']['fail'] += 1
            print(f"Erreur lors de la requête d'écriture : {str(e)}")
            
        if i % 100 == 0:
            print(f"{i} requêtes d'écriture complétées")

    results['write']['time'] = time.time() - start_time

    return results

# Fonction pour afficher les résultats des benchmarks
def print_benchmark_results(results):
    """
    Affiche les résultats des benchmarks.
    """
    print("\nRésultats du Benchmark :")
    print("\nOpérations de Lecture :")
    print(f"Succès : {results['read']['success']}")
    print(f"Échecs : {results['read']['fail']}")
    print(f"Temps total : {results['read']['time']:.2f} secondes")
    print(f"Temps moyen par requête : {(results['read']['time'] / NB_REQUESTS):.4f} secondes")
    
    print("\nOpérations d'Écriture :")
    print(f"Succès : {results['write']['success']}")
    print(f"Échecs : {results['write']['fail']}")
    print(f"Temps total : {results['write']['time']:.2f} secondes")
    print(f"Temps moyen par requête : {(results['write']['time'] / NB_REQUESTS):.4f} secondes")

# Fonction principale pour exécuter les benchmarks
def main():
    """
    Exécute les benchmarks pour toutes les stratégies définies.
    """
    try:
        # Chargement de l'adresse IP du Gatekeeper
        gatekeeper_ip = read_gatekeeper_ip(GATEKEEPER_IP_FILE)
    except FileNotFoundError as e:
        print(e)
        return

    # Liste des stratégies à tester
    strategies = ['direct', 'random', 'customized']
    benchmark_results = {}

    for strategy in strategies:
        print(f"\nTest de la stratégie : {strategy}")
        results = run_proxy_benchmark(gatekeeper_ip, strategy)
        benchmark_results[strategy] = results
        print_benchmark_results(results)

    # Sauvegarde des résultats dans un fichier
    with open('benchmark_results.txt', 'w') as f:
        f.write("Résultats du Benchmark\n")
        f.write("=======================\n\n")
        for strategy in strategies:
            f.write(f"\nStratégie : {strategy}\n")
            f.write("-----------------------\n")
            results = benchmark_results[strategy]
            f.write("\nOpérations de Lecture :\n")
            f.write(f"Succès : {results['read']['success']}\n")
            f.write(f"Échecs : {results['read']['fail']}\n")
            f.write(f"Temps total : {results['read']['time']:.2f} secondes\n")
            f.write(f"Temps moyen par requête : {(results['read']['time'] / NB_REQUESTS):.4f} secondes\n")
            
            f.write("\nOpérations d'Écriture :\n")
            f.write(f"Succès : {results['write']['success']}\n")
            f.write(f"Échecs : {results['write']['fail']}\n")
            f.write(f"Temps total : {results['write']['time']:.2f} secondes\n")
            f.write(f"Temps moyen par requête : {(results['write']['time'] / NB_REQUESTS):.4f} secondes\n")

    print("\nLes résultats ont été enregistrés dans 'benchmark_results.txt'.")

if __name__ == "__main__":
    main()
