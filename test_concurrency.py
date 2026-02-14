import threading
import time
from src.db import get_client

def worker():
    print(f"Thread {threading.current_thread().name} starting")
    cli = get_client()
    if cli:
        try:
            res = cli.command("SELECT 1")
            print(f"Thread {threading.current_thread().name} Success: {res}")
        except Exception as e:
            print(f"Thread {threading.current_thread().name} FAILURE: {e}")
    else:
        print(f"Thread {threading.current_thread().name} failed to get client")

threads = []
for i in range(5):
    t = threading.Thread(target=worker, name=f"T{i}")
    threads.append(t)
    t.start()

for t in threads:
    t.join()
