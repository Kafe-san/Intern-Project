import time
import docker

from database import (
    initialize_database,
    add_model,
    create_run
)

from resource_monitor import ResourceMonitor


MODEL = "llama3.2:1b"


initialize_database()

client = docker.from_env()

print("Starting test container...")

container = client.containers.run(
    "ollama/ollama:latest",

    name="benchmark-monitor-test",

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

print(
    f"Container started: "
    f"{container.id[:12]}"
)


model_id = add_model(
    model_name=MODEL,
    model_family="Llama",
    parameter_count=1.0,
    runtime="ollama"
)


run_id = create_run(
    model_id=model_id,
    benchmark_name="monitor_test",
    test_id="MONITOR-001",
    container_id=container.id
)


print(
    f"Database run created: {run_id}"
)


monitor = ResourceMonitor(
    container_id=container.id,
    run_id=run_id,

    # TEMPORARY TEST VALUES
    samples=5,
    interval=5
)


print("Starting monitor...")

monitor.start()


print("Letting container run...")

monitor.wait()


print()
print("========== SUMMARY ==========")

print(
    monitor.get_summary()
)


print()
print("Cleaning up...")

container.stop(timeout=5)
container.remove(force=True)

print("Container removed.")

print("MONITOR TEST COMPLETE")