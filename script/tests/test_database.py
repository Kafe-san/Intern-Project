from database import initialize_database, add_model


print("Initializing database...")

initialize_database()

print("Adding test model...")

model_id = add_model(
    model_name="llama3.2:1b",
    model_family="Llama",
    parameter_count=1.0,
    quantization="unknown",
    runtime="ollama"
)

print(f"Model created with ID: {model_id}")

print("Database test successful!")