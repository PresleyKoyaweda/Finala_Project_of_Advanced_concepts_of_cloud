import boto3

# Lecture du fichier conyenant le VPC ID
with open('vpc_id.txt', 'r') as file:
    vpc_id = file.read().strip()

print(f"VPC ID: {vpc_id}")

# Création d'un client EC2
ec2 = boto3.client('ec2')

# Récupération des sous-réseaux associés à ce VPC
response = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])

if response['Subnets']:
    subnet=response['Subnets'][0]
    subnet_id = subnet['SubnetId']
    with open('subnet_id.txt', 'w') as file:
        file.write(subnet_id)
    print(f"Subnet ID: {subnet_id}, Zone de disponibilité: {subnet['AvailabilityZone']}")
    print("Subnet IDs enregistrés dans 'subnet_id.txt'.")
else:
    print(f"Aucun sous-réseau trouvé pour le VPC ID: {vpc_id}")
