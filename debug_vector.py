import clickhouse_connect
from dotenv import load_dotenv
import os

load_dotenv()

client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST'),
    port=int(os.getenv('CLICKHOUSE_PORT', '8443')),
    username=os.getenv('CLICKHOUSE_USER', 'default'),
    password=os.getenv('CLICKHOUSE_PASSWORD', ''),
    secure=True
)

client.command("SET allow_experimental_vector_similarity_index = 1")

tests = [
    # 3 args: method, distance, data_type?
    "vector_similarity('hnsw', 'L2Distance', 'f32')",
    # 3 args: method, distance, dim?
    "vector_similarity('hnsw', 'L2Distance', 1536)",
    # 3 args: method, distance, M?
    "vector_similarity('hnsw', 'L2Distance', 16)",
    # 3 args: method, distance, ef?
    "vector_similarity('hnsw', 'L2Distance', 200)",
    # 6 args? method, distance, data_type, M, ef_construction, ef_search?
    "vector_similarity('hnsw', 'L2Distance', 'f32', 16, 200, 100)",
    # Legacy?
    "vector_similarity('hnsw', 'L2Distance')",
]

for idx_def in tests:
    print(f"\nTrying index: {idx_def}")
    try:
        client.command(f"DROP TABLE IF EXISTS test_vec_{hash(idx_def)}")
        client.command(f"""
            CREATE TABLE test_vec_{hash(idx_def)} (
                id Int32,
                vec Array(Float32),
                INDEX vec_idx vec TYPE {idx_def}
            ) ENGINE = MergeTree() ORDER BY id
        """)
        print(f"SUCCESS: {idx_def}")
        client.command(f"DROP TABLE test_vec_{hash(idx_def)}")
        break
    except Exception as e:
        print(f"FAILED: {e}")
