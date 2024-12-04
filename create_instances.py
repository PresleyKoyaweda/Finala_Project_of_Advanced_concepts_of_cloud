import boto3
from botocore.exceptions import ClientError
import os

# Création du client EC2
ec2 = boto3.client('ec2')

# Nom de la paire de clés
key_name = 'my-key-pair'

# Vérifie si la paire de clés existe déjà
try:
    ec2.describe_key_pairs(KeyNames=[key_name])
    print(f"Key Pair '{key_name}' existe déjà.")
except ClientError as e:
    if 'InvalidKeyPair.NotFound' in str(e):  # Si la clé n'existe pas, on la crée
        try:
            key_pair = ec2.create_key_pair(KeyName=key_name)
            # Sauvegarde de la clé privée dans un fichier local
            with open(f'{key_name}.pem', 'w') as file:
                file.write(key_pair['KeyMaterial'])
            os.chmod(f'{key_name}.pem', 0o400)  # Assure des permissions sécurisées sur le fichier
            print(f"Key Pair créée et enregistrée sous {key_name}.pem")
        except ClientError as create_key_error:
            print(f"Erreur lors de la création de la clé : {create_key_error}")
            raise
    else:
        print(f"Erreur lors de la vérification de la clé : {e}")
        raise

# Lecture des IDs de VPC, Subnet et Security Group depuis des fichiers
try:
    with open('vpc_id.txt', 'r') as file:
        vpc_id = file.read().strip()

    with open('subnet_id.txt', 'r') as file:
        selected_subnet_id = file.read().strip()

    with open('security_group_id.txt', 'r') as file:
        security_group_id = file.read().strip()
except FileNotFoundError as e:
    print(f"Fichier non trouvé : {e}")
    raise

# Utilisation d'un AMI valide (Amazon Linux 2)
ami_id = 'ami-007855ac798b5175e'

# Fonction pour créer une instance et récupérer son ID et son IP publique
def create_instance(instance_name, instance_type='t2.micro'):
    try:
        response = ec2.run_instances(
            ImageId=ami_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            SubnetId=selected_subnet_id,
            SecurityGroupIds=[security_group_id],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': instance_name}]
            }]
        )
        instance_id = response['Instances'][0]['InstanceId']
        print(f"Instance '{instance_name}' créée: {instance_id}")

        # Attendre que l'instance soit en état 'running'
        ec2.get_waiter('instance_running').wait(InstanceIds=[instance_id])

        # Récupération de l'adresse IP publique de l'instance
        instance_description = ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = instance_description['Reservations'][0]['Instances'][0]['PublicIpAddress']

        print(f"IP publique de l'instance '{instance_name}': {public_ip}")

        return instance_id, public_ip
    except ClientError as e:
        print(f"Erreur lors du lancement de l'instance '{instance_name}': {e}")
        raise

# Créer l'instance de manager et récupérer son IP publique
instance_id_manager, ip_manager = create_instance("manager")

# Sauvegarder l'ID et l'IP du manager dans des fichiers
with open('instance_id_manager.txt', 'w') as file:
    file.write(instance_id_manager)
with open('public_ip_manager.txt', 'w') as file:
    file.write(ip_manager)

# Créer les instances des workers (2 instances) et récupérer leurs IPs publiques
for i in range(1, 3):
    instance_id, public_ip = create_instance(f"worker{i}")
    # Enregistrer les ID et IP de chaque worker dans des fichiers séparés
    with open(f'instance_id_worker{i}.txt', 'w') as file:
        file.write(instance_id)
    with open(f'public_ip_worker{i}.txt', 'w') as file:
        file.write(public_ip)

# Créer les instances pour gatekeeper, trust-host et proxy
roles = ["gatekeeper", "trust-host", "proxy"]
for role in roles:
    instance_id, public_ip = create_instance(role)
    # Sauvegarder l'ID et l'IP de chaque rôle dans des fichiers
    with open(f'instance_id_{role}.txt', 'w') as file:
        file.write(instance_id)
    with open(f'public_ip_{role}.txt', 'w') as file:
        file.write(public_ip)

print("Instances et IPs publiques créées pour le manager, workers, gatekeeper, trust-host et proxy.")

# Configuration de la règle de groupe de sécurité pour autoriser l'accès au port 3306 uniquement depuis les IPs des workers
try:
    for i in range(1, 3):
        with open(f'public_ip_worker{i}.txt', 'r') as file:
            worker_ip = file.read().strip()
        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 3306,
                    'ToPort': 3306,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print(f"Accès au port 3306 autorisé pour l'IP du worker : {worker_ip}")
except ClientError as e:
    if 'InvalidPermission.Duplicate' in str(e):
        print("La règle d'accès au port 3306 pour les IPs des workers existe déjà.")
    else:
        print(f"Erreur lors de la configuration du groupe de sécurité : {e}")
        raise
