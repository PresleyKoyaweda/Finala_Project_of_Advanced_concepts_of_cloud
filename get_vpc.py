import boto3

# Création d'un client EC2
ec2 = boto3.client('ec2')

# Récupération du VPC par défaut
response = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
vpc_id = response['Vpcs'][0]['VpcId']
print(f"Default VPC ID: {vpc_id}")

# Sauvegarde de l'ID du VPC dans un fichier pour usage futur
with open('vpc_id.txt', 'w') as file:
    file.write(vpc_id)
