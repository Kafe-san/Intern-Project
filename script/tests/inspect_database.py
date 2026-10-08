from database.database import get_connection


def main():

    connection = get_connection()

    print()
    print("=" * 70)
    print("MODELS")
    print("=" * 70)

    rows = connection.execute("""
        SELECT *
        FROM models
        ORDER BY model_id
    """).fetchall()

    for row in rows:
        print(dict(row))


    print()
    print("=" * 70)
    print("BENCHMARK RUNS")
    print("=" * 70)

    runs = connection.execute("""
        SELECT *
        FROM benchmark_runs
        ORDER BY run_id
    """).fetchall()

    for row in runs:
        print(dict(row))


    print()
    print("=" * 70)
    print("CHAT RESULTS")
    print("=" * 70)

    results = connection.execute("""
        SELECT
            result_id,
            run_id,
            input_tokens,
            output_tokens,
            load_time_ms,
            prompt_eval_time_ms,
            generation_time_ms,
            total_time_ms,
            tokens_per_second
        FROM chat_results
        ORDER BY result_id
    """).fetchall()

    for row in results:
        print(dict(row))


    print()
    print("=" * 70)
    print("RESOURCE SAMPLES")
    print("=" * 70)

    resources = connection.execute("""
        SELECT
            run_id,
            COUNT(*) AS sample_count,
            MIN(cpu_percent) AS cpu_min,
            MAX(cpu_percent) AS cpu_max,
            AVG(cpu_percent) AS cpu_average,
            MIN(memory_used_mb) AS memory_min_mb,
            MAX(memory_used_mb) AS memory_max_mb,
            AVG(memory_used_mb) AS memory_average_mb
        FROM resource_samples
        GROUP BY run_id
        ORDER BY run_id
    """).fetchall()

    for row in resources:
        print(dict(row))


    print()
    print("=" * 70)
    print("ERRORS")
    print("=" * 70)

    errors = connection.execute("""
        SELECT *
        FROM errors
        ORDER BY error_id
    """).fetchall()

    if errors:
        for row in errors:
            print(dict(row))
    else:
        print("No errors recorded.")


    print()
    print("=" * 70)
    print("SAMPLE COUNTS PER RUN")
    print("=" * 70)

    counts = connection.execute("""
        SELECT
            br.run_id,
            br.status,
            COUNT(rs.sample_id) AS resource_samples
        FROM benchmark_runs br
        LEFT JOIN resource_samples rs
            ON br.run_id = rs.run_id
        GROUP BY br.run_id
        ORDER BY br.run_id
    """).fetchall()

    for row in counts:
        print(dict(row))


    connection.close()


if __name__ == "__main__":
    main()