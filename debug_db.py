import os
import clickhouse_connect
from dotenv import load_dotenv

# Replicate behavior from settings
load_dotenv(".env")
host = os.getenv('CLICKHOUSE_HOST')
port = int(os.getenv('CLICKHOUSE_PORT', '8443'))
user = os.getenv('CLICKHOUSE_USER', 'default')
password = os.getenv('CLICKHOUSE_PASSWORD', '')

print(f"Connecting to: {host}:{port} as {user}")
print(f"Password length: {len(password) if password else 0}")
print(f"Password first char: {password[0] if password else 'N/A'}")
print(f"Password last char: {password[-1] if password else 'N/A'}")

try:
    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        secure=True,
        connect_timeout=10,
    )
    res = client.command("SELECT version()")
    print(f"SUCCESS! Connected to ClickHouse version: {res}")
except Exception as e:
    print(f"FAILURE: {e}")
