import time
import threading
from datetime import datetime

import docker

from database.database import get_connection


class ResourceMonitor:

    def __init__(
        self,
        container_id,
        run_id,
        samples=20,
        interval=15
    ):
        self.container_id = container_id
        self.run_id = run_id

        self.samples = samples
        self.interval = interval

        self.client = docker.from_env()

        self.thread = None
        self.stop_event = threading.Event()

        self.samples_data = []
        self.error = None

    def start(self):
        self.thread = threading.Thread(
            target=self._monitor,
            daemon=True
        )

        self.thread.start()

    def wait(self):
        if self.thread:
            self.thread.join()

    def stop(self):
        self.stop_event.set()

        if self.thread:
            self.thread.join(timeout=5)

    def _monitor(self):

        try:

            container = self.client.containers.get(
                self.container_id
            )

            for sample_number in range(
                1,
                self.samples + 1
            ):

                if self.stop_event.is_set():
                    break

                stats = container.stats(
                    stream=False
                )

                cpu_percent = (
                    self._calculate_cpu_percent(stats)
                )

                memory_stats = stats.get(
                    "memory_stats",
                    {}
                )

                memory_used = (
                    memory_stats.get(
                        "usage",
                        0
                    ) / (1024 * 1024)
                )

                memory_limit = (
                    memory_stats.get(
                        "limit",
                        0
                    ) / (1024 * 1024)
                )

                if memory_limit > 0:
                    memory_percent = (
                        memory_used /
                        memory_limit *
                        100
                    )
                else:
                    memory_percent = 0

                pids = (
                    stats
                    .get("pids_stats", {})
                    .get("current", 0)
                )

                sample = {
                    "sample_number": sample_number,
                    "timestamp": datetime.now().isoformat(),

                    "cpu_percent": cpu_percent,

                    "memory_used_mb": memory_used,
                    "memory_percent": memory_percent,
                    "memory_limit_mb": memory_limit,

                    "pids": pids
                }

                self.samples_data.append(sample)

                self._save_sample(sample)

                print(
                    f"[MONITOR] "
                    f"{sample_number}/{self.samples} "
                    f"| CPU: {cpu_percent:.1f}% "
                    f"| RAM: {memory_used:.1f} MB"
                )

                if sample_number < self.samples:
                    time.sleep(self.interval)

        except Exception as error:

            self.error = error

            print(
                f"[MONITOR ERROR] {error}"
            )

    def _save_sample(self, sample):

        connection = get_connection()

        connection.execute("""
            INSERT INTO resource_samples (
                run_id,
                sample_number,
                timestamp,
                cpu_percent,
                memory_used_mb,
                memory_percent,
                memory_limit_mb,
                pids
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.run_id,

            sample["sample_number"],
            sample["timestamp"],

            sample["cpu_percent"],

            sample["memory_used_mb"],
            sample["memory_percent"],
            sample["memory_limit_mb"],

            sample["pids"]
        ))

        connection.commit()
        connection.close()

    @staticmethod
    def _calculate_cpu_percent(stats):

        cpu_stats = stats.get(
            "cpu_stats",
            {}
        )

        previous_cpu_stats = stats.get(
            "precpu_stats",
            {}
        )

        cpu_usage = cpu_stats.get(
            "cpu_usage",
            {}
        )

        previous_cpu_usage = (
            previous_cpu_stats.get(
                "cpu_usage",
                {}
            )
        )

        cpu_delta = (
            cpu_usage.get("total_usage", 0)
            -
            previous_cpu_usage.get(
                "total_usage",
                0
            )
        )

        system_delta = (
            cpu_stats.get(
                "system_cpu_usage",
                0
            )
            -
            previous_cpu_stats.get(
                "system_cpu_usage",
                0
            )
        )

        if system_delta <= 0:
            return 0.0

        percpu_usage = cpu_usage.get(
            "percpu_usage",
            []
        )

        cpu_count = len(percpu_usage)

        if cpu_count == 0:
            cpu_count = 1

        return (
            cpu_delta /
            system_delta *
            cpu_count *
            100
        )

    def get_summary(self):

        if not self.samples_data:
            return {}

        cpu_values = [
            sample["cpu_percent"]
            for sample in self.samples_data
        ]

        memory_values = [
            sample["memory_used_mb"]
            for sample in self.samples_data
        ]

        return {
            "sample_count": len(
                self.samples_data
            ),

            "cpu_first": cpu_values[0],
            "cpu_last": cpu_values[-1],

            "cpu_average": (
                sum(cpu_values) /
                len(cpu_values)
            ),

            "cpu_min": min(cpu_values),
            "cpu_max": max(cpu_values),

            "memory_first_mb":
                memory_values[0],

            "memory_last_mb":
                memory_values[-1],

            "memory_average_mb": (
                sum(memory_values) /
                len(memory_values)
            ),

            "memory_min_mb":
                min(memory_values),

            "memory_max_mb":
                max(memory_values)
        }