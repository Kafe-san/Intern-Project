import docker

client = docker.from_env()

print("Python -> Docker connection successful!")

for container in client.containers.list(all=True):
    print(f"{container.name} | {container.status}")