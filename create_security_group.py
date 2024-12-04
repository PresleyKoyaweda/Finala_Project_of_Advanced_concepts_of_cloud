import boto3
from botocore.exceptions import ClientError

# Création d'un client EC2
ec2 = boto3.client('ec2')

# Lecture de l'ID du VPC à partir d'un fichier
with open('vpc_id.txt', 'r') as file:
    vpc_id = file.read().strip()

# Nom du groupe de sécurité
group_name = 'my-security-group'

# Vérification si le groupe de sécurité existe déjà
try:
    response = ec2.describe_security_groups(GroupNames=[group_name])
    security_group_id = response['SecurityGroups'][0]['GroupId']
    print(f"Le groupe de sécurité '{group_name}' existe déjà avec l'ID : {security_group_id}")

    # Vérifie si le groupe est utilisé par d'autres ressources
    try:
        print(f"Le groupe de sécurité '{group_name}' est en cours d'utilisation. Il ne sera pas supprimé.")
    except ClientError as e:
        if 'DependencyViolation' in str(e):
            print(f"Impossible de supprimer le groupe de sécurité '{group_name}' car il est associé à des ressources.")
        else:
            raise e

except ClientError as e:
    if 'InvalidGroup.NotFound' in str(e):
        print(f"Le groupe de sécurité '{group_name}' n'existe pas encore, création d'un nouveau.")

        # Création d'un nouveau groupe de sécurité
        security_group = ec2.create_security_group(
            GroupName=group_name,
            Description="Security group for EC2 instances",  # La description doit être en ASCII uniquement
            VpcId=vpc_id
        )

        security_group_id = security_group['GroupId']
        print(f"Groupe de sécurité créé : {security_group_id}")

        # Sauvegarde de l'ID du groupe de sécurité dans un fichier
        with open('security_group_id.txt', 'w') as file:
            file.write(security_group_id)

        # Configuration des règles du groupe de sécurité pour autoriser les ports nécessaires
        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'icmp', 'FromPort': -1, 'ToPort': -1, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},  # Autorise le ping
                {'IpProtocol': 'tcp', 'FromPort': 5000, 'ToPort': 5000, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        print("Groupe de sécurité configuré pour les ports 80, 443, 22, ICMP et 5000.")

# Si le groupe de sécurité existe déjà, ajoute la règle ICMP et le port 5000 si elles n'existent pas encore
try:
    # Ajout de la règle ICMP pour autoriser les requêtes ping
    ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpProtocol='icmp',
        CidrIp='0.0.0.0/0',
        FromPort=-1,
        ToPort=-1
    )
    print("Règle ICMP ajoutée pour autoriser les requêtes ping.")
except ClientError as e:
    if 'InvalidPermission.Duplicate' in str(e):
        print("La règle ICMP existe déjà.")
    else:
        print(f"Erreur lors de l'ajout de la règle ICMP : {e}")

# Ajout de la règle pour le port 5000 si elle n'existe pas encore
try:
    ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpProtocol='tcp',
        CidrIp='0.0.0.0/0',
        FromPort=5000,
        ToPort=5000
    )
    print("Règle pour le port 5000 ajoutée.")
except ClientError as e:
    if 'InvalidPermission.Duplicate' in str(e):
        print("La règle pour le port 5000 existe déjà.")
    else:
        print(f"Erreur lors de l'ajout de la règle pour le port 5000 : {e}")
