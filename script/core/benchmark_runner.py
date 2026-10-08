import argparse
import time
import requests
import docker

from core.config_loader import load_config

from database.database import (
    initialize_database,
    add_model,
    create_run,
    add_chat_result,
    finish_run,
    add_error
)

from core.resource_monitor import ResourceMonitor


def wait_for_ollama(
    port,
    timeout_seconds=60
):

    url = (
        f"http://localhost:{port}"
        "/api/tags"
    )

    start_time = time.time()

    while (
        time.time() - start_time
        < timeout_seconds
    ):

        try:

            response = requests.get(
                url,
                timeout=2
            )

            if response.status_code == 200:

                print(
                    "Ollama is ready."
                )

                return True

        except requests.RequestException:
            pass

        time.sleep(2)

    raise TimeoutError(
        "Ollama did not become ready."
    )


def run_benchmark(config):

    model_config = config["model"]
    docker_config = config["docker"]
    inference_config = config["inference"]
    benchmark_config = config["benchmark"]
    monitoring_config = config["monitoring"]

    model = model_config["name"]

    image = docker_config["image"]

    port = docker_config["port"]

    volume = docker_config["volume"]

    container_name = (
        f"{docker_config['container_name_prefix']}-"
        f"{model.replace(':', '-')}"
    )

    client = docker.from_env()

    container = None
    monitor = None
    run_id = None

    # --------------------------------------------------
    # DATABASE
    # --------------------------------------------------

    initialize_database()

    model_id = add_model(
        model_name=model_config["name"],
        model_family=model_config.get(
            "family"
        ),
        parameter_count=model_config.get(
            "parameters_b"
        ),
        quantization=model_config.get(
            "quantization"
        ),
        runtime=model_config.get(
            "runtime",
            "ollama"
        )
    )

    # --------------------------------------------------
    # REMOVE OLD CONTAINER
    # --------------------------------------------------

    try:

        old_container = client.containers.get(
            container_name
        )

        print(
            f"Removing existing container "
            f"{container_name}..."
        )

        old_container.remove(
            force=True
        )

    except docker.errors.NotFound:
        pass

    try:

        # --------------------------------------------------
        # CREATE CONTAINER
        # --------------------------------------------------

        print()
        print(
            "Creating Ollama container..."
        )

        print(
            f"Model: {model}"
        )

        container = client.containers.run(

            image,

            name=container_name,

            ports={
                "11434/tcp": port
            },

            volumes={
                volume: {
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

        # --------------------------------------------------
        # CREATE DATABASE RUN
        # --------------------------------------------------

        run_id = create_run(

            model_id=model_id,

            benchmark_name=(
                benchmark_config["name"]
            ),

            test_id=(
                benchmark_config["test_id"]
            ),

            container_id=container.id
        )

        print(
            f"Database run ID: {run_id}"
        )

        # --------------------------------------------------
        # WAIT FOR OLLAMA
        # --------------------------------------------------

        print(
            "Waiting for Ollama..."
        )

        wait_for_ollama(port)

        # --------------------------------------------------
        # PULL MODEL
        # --------------------------------------------------

        print(
            f"Checking/pulling model: "
            f"{model}"
        )

        response = requests.post(

            f"http://localhost:{port}"
            "/api/pull",

            json={
                "name": model,
                "stream": False
            },

            timeout=1800
        )

        response.raise_for_status()

        print("Model ready.")

        # --------------------------------------------------
        # START RESOURCE MONITOR
        # --------------------------------------------------

        monitor = ResourceMonitor(

            container_id=container.id,

            run_id=run_id,

            samples=(
                monitoring_config[
                    "samples"
                ]
            ),

            interval=(
                monitoring_config[
                    "interval_seconds"
                ]
            )
        )

        print()
        print(
            "Starting resource monitor..."
        )

        monitor.start()

        # --------------------------------------------------
        # RUN MODEL
        # --------------------------------------------------

        prompt = inference_config["prompt"]

        print()
        print(
            "Running benchmark prompt..."
        )

        start_time = time.perf_counter()

        response = requests.post(

            f"http://localhost:{port}"
            "/api/generate",

            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },

            timeout=(
                inference_config[
                    "timeout_seconds"
                ]
            )
        )

        elapsed = (
            time.perf_counter()
            - start_time
        )

        response.raise_for_status()

        result = response.json()

        # --------------------------------------------------
        # EXTRACT METRICS
        # --------------------------------------------------

        metrics = {

            "total_duration_ms":
                result.get(
                    "total_duration",
                    0
                ) / 1_000_000,

            "prompt_eval_duration_ms":
                result.get(
                    "prompt_eval_duration",
                    0
                ) / 1_000_000,

            "eval_duration_ms":
                result.get(
                    "eval_duration",
                    0
                ) / 1_000_000,

            "load_duration_ms":
                result.get(
                    "load_duration",
                    0
                ) / 1_000_000,

            "prompt_eval_count":
                result.get(
                    "prompt_eval_count"
                ),

            "eval_count":
                result.get(
                    "eval_count"
                )
        }

        generation_seconds = (
            metrics[
                "eval_duration_ms"
            ] / 1000
        )

        if (
            generation_seconds > 0
            and metrics["eval_count"]
        ):

            metrics["tokens_per_second"] = (
                metrics["eval_count"]
                /
                generation_seconds
            )

        else:

            metrics[
                "tokens_per_second"
            ] = None

        # --------------------------------------------------
        # SAVE CHAT RESULT
        # --------------------------------------------------

        add_chat_result(

            run_id=run_id,

            prompt=prompt,

            response=result.get(
                "response",
                ""
            ),

            metrics=metrics
        )

        # --------------------------------------------------
        # DISPLAY RESULT
        # --------------------------------------------------

        print()
        print("=" * 60)
        print("MODEL RESPONSE")
        print("=" * 60)

        print(
            result.get(
                "response",
                ""
            )
        )

        print()
        print("=" * 60)
        print("INFERENCE METRICS")
        print("=" * 60)

        print(
            f"Total duration: "
            f"{metrics['total_duration_ms']:.2f} ms"
        )

        print(
            f"Prompt evaluation: "
            f"{metrics['prompt_eval_duration_ms']:.2f} ms"
        )

        print(
            f"Generation: "
            f"{metrics['eval_duration_ms']:.2f} ms"
        )

        print(
            f"Load time: "
            f"{metrics['load_duration_ms']:.2f} ms"
        )

        print(
            f"Input tokens: "
            f"{metrics['prompt_eval_count']}"
        )

        print(
            f"Output tokens: "
            f"{metrics['eval_count']}"
        )

        print(
            f"Generation speed: "
            f"{metrics['tokens_per_second']:.2f} "
            f"tokens/sec"
            if metrics["tokens_per_second"]
            else "Generation speed: N/A"
        )

        print(
            f"Python elapsed: "
            f"{elapsed:.2f} seconds"
        )

        # --------------------------------------------------
        # WAIT FOR MONITOR
        # --------------------------------------------------

        print()
        print(
            "Waiting for resource monitor..."
        )

        monitor.wait()

        if monitor.error:

            add_error(

                run_id=run_id,

                stage="resource_monitor",

                error_type=(
                    type(
                        monitor.error
                    ).__name__
                ),

                message=str(
                    monitor.error
                )
            )

            print(
                f"Resource monitor error: "
                f"{monitor.error}"
            )

        # --------------------------------------------------
        # RESOURCE SUMMARY
        # --------------------------------------------------

        summary = (
            monitor.get_summary()
        )

        print()
        print("=" * 60)
        print("RESOURCE SUMMARY")
        print("=" * 60)

        for key, value in summary.items():

            if isinstance(
                value,
                float
            ):

                print(
                    f"{key}: "
                    f"{value:.2f}"
                )

            else:

                print(
                    f"{key}: "
                    f"{value}"
                )

        # --------------------------------------------------
        # FINISH RUN
        # --------------------------------------------------

        finish_run(

            run_id=run_id,

            status="SUCCESS"
        )

        print()
        print(
            f"Benchmark run {run_id} "
            f"completed successfully."
        )

    except Exception as error:

        print()
        print(
            "=" * 60
        )

        print(
            "BENCHMARK ERROR"
        )

        print(
            "=" * 60
        )

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        # --------------------------------------------------
        # DATABASE ERROR
        # --------------------------------------------------

        if run_id is not None:

            try:

                add_error(

                    run_id=run_id,

                    stage="benchmark",

                    error_type=(
                        type(error).__name__
                    ),

                    message=str(error)
                )

                finish_run(

                    run_id=run_id,

                    status="FAILED",

                    error_message=str(error)
                )

            except Exception as database_error:

                print(
                    "Could not record "
                    f"database error: "
                    f"{database_error}"
                )

        raise

    finally:

        # --------------------------------------------------
        # CLEANUP MONITOR
        # --------------------------------------------------

        if monitor is not None:

            try:
                monitor.stop()

            except Exception:
                pass

        # --------------------------------------------------
        # CLEANUP CONTAINER
        # --------------------------------------------------

        if container is not None:

            print()
            print(
                "Cleaning up container..."
            )

            try:

                container.stop(
                    timeout=10
                )

            except Exception:
                pass

            try:

                container.remove(
                    force=True
                )

            except Exception:
                pass

            print(
                "Container removed."
            )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Local LLM benchmark runner"
        )
    )

    parser.add_argument(
        "--config",
        default="config/config.json",
        help=(
            "Path to benchmark "
            "configuration"
        )
    )

    args = parser.parse_args()

    print(
        "Loading configuration..."
    )

    config = load_config(
        args.config
    )

    print(
        "Configuration loaded."
    )

    run_benchmark(config)


if __name__ == "__main__":
    main()