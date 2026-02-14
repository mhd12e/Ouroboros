import docker
try:
    client = docker.from_env()
    client.ping()
    print("Docker is connected.")
    print(f"Images: {[img.tags for img in client.images.list()]}")
except Exception as e:
    print(f"Docker connection failed: {e}")
