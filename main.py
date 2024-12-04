import subprocess

# Fonction pour exécuter un script et gérer les erreurs
def executer_script(nom_script, description_etape, max_retries=5):
    """
    Exécute un script Python et réessaye en cas d'échec jusqu'à max_retries fois.
    """
    for attempt in range(max_retries):
        print(f"{description_etape} (Tentative {attempt + 1}/{max_retries})...")
        try:
            subprocess.run(['python', nom_script], check=True)
            print(f"{description_etape} terminé avec succès.\n")
            return  # Sort de la boucle en cas de succès
        except subprocess.CalledProcessError as e:
            print(f"Erreur lors de l'exécution de {nom_script}: {str(e)}")
            if attempt < max_retries - 1:
                print("Nouvelle tentative en cours...\n")
            else:
                print(f"Échec après {max_retries} tentatives.\n")
                exit(1)

# Fonction pour exécuter une commande Windows (par exemple icacls)
def executer_commande_windows(commande, description_etape):
    """
    Exécute une commande Windows dans un shell.
    """
    print(f"{description_etape}...")
    try:
        subprocess.run(commande, shell=True, check=True)
        print(f"{description_etape} terminé avec succès.\n")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'exécution de la commande: {str(e)}")
        exit(1)

# Étapes de création et configuration

# Étape 0 : Création du VPC
executer_script('get_vpc.py', "0. Création du VPC...")

# Étape 1 : Récupération des IDs des sous-réseaux
executer_script('get_subnet_id.py', "1. Récupération des Subnet IDs...")

# Étape 2 : Création du groupe de sécurité
executer_script('create_security_group.py', "2. Création du groupe de sécurité...")

# Étape 4 : Lancement des instances EC2 pour les workers et manager
executer_script('create_instances.py', "4. Lancement des instances EC2 pour les workers, manager, proxy, gatekeeper et trusthost...")

# Étape 5 : Configuration du cluster (manager et workers)
executer_script('setup_manager_and_workers.py', "5. Configuration du cluster (manager et workers)...")

# Étape 6 : Configuration du Proxy, Gate-keeper et Trusted Host
# Répété plusieurs fois car certaines étapes peuvent échouer lors de la première exécution,
# mais elles fonctionnent souvent après une nouvelle tentative.
for i in range(5):
    executer_script('setup_cluster_2.py', f"6. Configuration du Proxy, Gate-keeper et Trusted Host (Tentative {i + 1}/5)")

# Étape 7 : Exécution de Benchmarking avec 1000 requêtes.
executer_script('benchmarking_requests.py', "7. Exécution de benchmark avec les 1000 requêtes")
