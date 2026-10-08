import sqlite3
from pathlib import Path
from datetime import datetime


# ============================================================
# DATABASE PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_ROOT / "database" / "benchmark.db"


# ============================================================
# CONNECTION
# ============================================================

def get_connection():
    """
    Create and return a SQLite database connection.
    """

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():
    """
    Create all benchmark tables if they do not already exist.
    """

    connection = get_connection()

    connection.executescript("""

    CREATE TABLE IF NOT EXISTS models (

        model_id INTEGER PRIMARY KEY AUTOINCREMENT,

        model_name TEXT NOT NULL,

        model_family TEXT,

        parameter_count REAL,

        quantization TEXT,

        runtime TEXT,

        created_at TEXT NOT NULL
    );


    CREATE TABLE IF NOT EXISTS benchmark_runs (

        run_id INTEGER PRIMARY KEY AUTOINCREMENT,

        model_id INTEGER NOT NULL,

        benchmark_name TEXT NOT NULL,

        test_id TEXT NOT NULL,

        docker_container_id TEXT,

        started_at TEXT NOT NULL,

        finished_at TEXT,

        status TEXT,

        error_message TEXT,

        FOREIGN KEY (model_id)
            REFERENCES models(model_id)
    );


    CREATE TABLE IF NOT EXISTS chat_results (

        result_id INTEGER PRIMARY KEY AUTOINCREMENT,

        run_id INTEGER NOT NULL,

        prompt TEXT NOT NULL,

        response TEXT,

        input_tokens INTEGER,

        output_tokens INTEGER,

        load_time_ms REAL,

        prompt_eval_time_ms REAL,

        generation_time_ms REAL,

        total_time_ms REAL,

        tokens_per_second REAL,

        evaluation_score REAL,

        evaluation_notes TEXT,

        FOREIGN KEY (run_id)
            REFERENCES benchmark_runs(run_id)
    );


    CREATE TABLE IF NOT EXISTS rag_results (

        result_id INTEGER PRIMARY KEY AUTOINCREMENT,

        run_id INTEGER NOT NULL,

        test_id TEXT,

        response TEXT,

        input_tokens INTEGER,

        output_tokens INTEGER,

        total_time_ms REAL,

        retrieval_hit INTEGER,

        answer_correct INTEGER,

        groundedness_score REAL,

        evaluation_notes TEXT,

        FOREIGN KEY (run_id)
            REFERENCES benchmark_runs(run_id)
    );


    CREATE TABLE IF NOT EXISTS classification_results (

        result_id INTEGER PRIMARY KEY AUTOINCREMENT,

        run_id INTEGER NOT NULL,

        test_id TEXT,

        expected_class TEXT,

        predicted_class TEXT,

        input_tokens INTEGER,

        output_tokens INTEGER,

        total_time_ms REAL,

        correct INTEGER,

        valid_output INTEGER,

        FOREIGN KEY (run_id)
            REFERENCES benchmark_runs(run_id)
    );


    CREATE TABLE IF NOT EXISTS tool_use_results (

        result_id INTEGER PRIMARY KEY AUTOINCREMENT,

        run_id INTEGER NOT NULL,

        test_id TEXT,

        expected_tool TEXT,

        selected_tool TEXT,

        correct_tool INTEGER,

        correct_arguments INTEGER,

        schema_valid INTEGER,

        task_completed INTEGER,

        tool_call_count INTEGER,

        unnecessary_calls INTEGER,

        total_time_ms REAL,

        FOREIGN KEY (run_id)
            REFERENCES benchmark_runs(run_id)
    );


    CREATE TABLE IF NOT EXISTS resource_samples (

        sample_id INTEGER PRIMARY KEY AUTOINCREMENT,

        run_id INTEGER NOT NULL,

        sample_number INTEGER NOT NULL,

        timestamp TEXT NOT NULL,

        cpu_percent REAL,

        memory_used_mb REAL,

        memory_percent REAL,

        memory_limit_mb REAL,

        pids INTEGER,

        FOREIGN KEY (run_id)
            REFERENCES benchmark_runs(run_id)
    );


    CREATE TABLE IF NOT EXISTS errors (

        error_id INTEGER PRIMARY KEY AUTOINCREMENT,

        run_id INTEGER,

        timestamp TEXT NOT NULL,

        stage TEXT,

        error_type TEXT,

        message TEXT,

        FOREIGN KEY (run_id)
            REFERENCES benchmark_runs(run_id)
    );

    """)

    connection.commit()

    connection.close()


# ============================================================
# MODELS
# ============================================================

def add_model(
    model_name,
    model_family=None,
    parameter_count=None,
    quantization=None,
    runtime="ollama"
):
    """
    Add a model to the models table.

    Returns:
        model_id
    """

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO models (
            model_name,
            model_family,
            parameter_count,
            quantization,
            runtime,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            model_name,
            model_family,
            parameter_count,
            quantization,
            runtime,
            datetime.now().isoformat()
        )
    )

    model_id = cursor.lastrowid

    connection.commit()

    connection.close()

    return model_id


def get_model_id(model_name):
    """
    Find the most recently added model with the given name.

    Returns:
        model_id or None
    """

    connection = get_connection()

    row = connection.execute(
        """
        SELECT model_id
        FROM models
        WHERE model_name = ?
        ORDER BY model_id DESC
        LIMIT 1
        """,
        (
            model_name,
        )
    ).fetchone()

    connection.close()

    if row:
        return row["model_id"]

    return None


# ============================================================
# BENCHMARK RUNS
# ============================================================

def create_run(
    model_id,
    benchmark_name,
    test_id,
    container_id=None
):
    """
    Create a new benchmark run.

    The run starts with status RUNNING.

    Returns:
        run_id
    """

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO benchmark_runs (
            model_id,
            benchmark_name,
            test_id,
            docker_container_id,
            started_at,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            model_id,
            benchmark_name,
            test_id,
            container_id,
            datetime.now().isoformat(),
            "RUNNING"
        )
    )

    run_id = cursor.lastrowid

    connection.commit()

    connection.close()

    return run_id


def finish_run(
    run_id,
    status,
    error_message=None
):
    """
    Mark a benchmark run as finished.
    """

    connection = get_connection()

    connection.execute(
        """
        UPDATE benchmark_runs

        SET
            finished_at = ?,
            status = ?,
            error_message = ?

        WHERE run_id = ?
        """,
        (
            datetime.now().isoformat(),
            status,
            error_message,
            run_id
        )
    )

    connection.commit()

    connection.close()


def get_run(run_id):
    """
    Retrieve one benchmark run.

    Returns:
        sqlite3.Row or None
    """

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM benchmark_runs
        WHERE run_id = ?
        """,
        (
            run_id,
        )
    ).fetchone()

    connection.close()

    return row


# ============================================================
# CHAT RESULTS
# ============================================================

def add_chat_result(
    run_id,
    prompt,
    response,
    metrics
):
    """
    Store the result of a chat/inference benchmark.
    """

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO chat_results (

            run_id,

            prompt,

            response,

            input_tokens,

            output_tokens,

            load_time_ms,

            prompt_eval_time_ms,

            generation_time_ms,

            total_time_ms,

            tokens_per_second

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,

            prompt,

            response,

            metrics.get(
                "prompt_eval_count"
            ),

            metrics.get(
                "eval_count"
            ),

            metrics.get(
                "load_duration_ms"
            ),

            metrics.get(
                "prompt_eval_duration_ms"
            ),

            metrics.get(
                "eval_duration_ms"
            ),

            metrics.get(
                "total_duration_ms"
            ),

            metrics.get(
                "tokens_per_second"
            )
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# ERRORS
# ============================================================

def add_error(
    run_id,
    stage,
    error_type,
    message
):
    """
    Record an error associated with a benchmark run.
    """

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO errors (

            run_id,

            timestamp,

            stage,

            error_type,

            message

        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            run_id,

            datetime.now().isoformat(),

            stage,

            error_type,

            message
        )
    )

    connection.commit()

    connection.close()


def add_resource_error(
    run_id,
    error
):
    """
    Convenience function for recording
    resource-monitor errors.
    """

    add_error(
        run_id=run_id,

        stage="resource_monitor",

        error_type=type(error).__name__,

        message=str(error)
    )


# ============================================================
# UTILITY
# ============================================================

def get_database_path():
    """
    Return the absolute database path.
    """

    return DB_PATH


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    initialize_database()

    print(
        "Database initialized successfully."
    )

    print(
        f"Database location: {DB_PATH}"
    )