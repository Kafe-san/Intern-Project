import time
import docker

client = docker.from_env()

CONTAINER_NAME = "benchmark-ollama-test"

# Remove an old test container if it exists
try:
    old = client.containers.get(CONTAINER_NAME)
    print("Removing old test container...")
    old.remove(force=True)
except docker.errors.NotFound:
    pass

print("Creating Ollama container...")

container = client.containers.run(
    "ollama/ollama:latest",
    name=CONTAINER_NAME,
    ports={
        "11434/tcp": 11434
    },
    volumes={
        "ollama_models": {
            "bind": "/root/.ollama",
            "mode": "rw"
        }
    },
    detach=True
)

print(f"Container started: {container.id[:12]}")

print("Waiting for Ollama...")

import requests

for attempt in range(30):

    try:
        response = requests.get(
            "http://localhost:11434/api/tags",
            timeout=2
        )

        if response.status_code == 200:
            print("Ollama is ready!")
            break

    except requests.RequestException:
        pass

    time.sleep(2)

else:
    print("Ollama did not become ready.")
    container.remove(force=True)
    raise SystemExit(1)


print("Pulling model...")

response = requests.post(
    "http://localhost:11434/api/pull",
    json={
        "name": "llama3.2:1b",
        "stream": False
    },
    timeout=1800
)

response.raise_for_status()

print("Model downloaded.")


print("Running test prompt...")

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.2:1b",
        "prompt": "Explain what a database is in three sentences.",
        "stream": False
    },
    timeout=600
)

response.raise_for_status()

data = response.json()

print()
print("========== MODEL RESPONSE ==========")
print(data["response"])

print()
print("========== RAW METRICS ==========")

print(
    f"Total duration: "
    f"{data.get('total_duration', 0) / 1_000_000:.2f} ms"
)

print(
    f"Prompt evaluation: "
    f"{data.get('prompt_eval_duration', 0) / 1_000_000:.2f} ms"
)

print(
    f"Generation: "
    f"{data.get('eval_duration', 0) / 1_000_000:.2f} ms"
)

print(
    f"Input tokens: "
    f"{data.get('prompt_eval_count')}"
)

print(
    f"Output tokens: "
    f"{data.get('eval_count')}"
)

print()
print("Cleaning up container...")

container.stop(timeout=10)
container.remove(force=True)

print("Container removed.")
print("TEST COMPLETE")