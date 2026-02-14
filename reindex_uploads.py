import os
import sys
import pypdf
sys.path.append(os.getcwd())
from src.rag import store_document
from src.db import get_client

def reindex():
    print("[Reindex] Starting...")
    client = get_client()
    if not client:
        print("[Reindex] Failed to connect to DB.")
        return
        
    # Truncate existing documents
    try:
        client.command("TRUNCATE TABLE documents")
        print("[Reindex] Truncated 'documents' table.")
    except Exception as e:
        print(f"[Reindex] Failed to truncate: {e}")
        
    if not os.path.exists("uploads"):
        print("[Reindex] No uploads directory found.")
        return
        
    files = os.listdir("uploads")
    if not files:
        print("[Reindex] No files in uploads/.")
        return
        
    for fname in files:
        path = os.path.join("uploads", fname)
        if not os.path.isfile(path):
            continue
            
        print(f"[Reindex] Processing {fname}...")
        content = ""
        
        try:
            if fname.lower().endswith(".pdf"):
                reader = pypdf.PdfReader(path)
                for page in reader.pages:
                    content += (page.extract_text() or "") + "\n"
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    
            if content.strip():
                store_document(fname, content)
                print(f"[Reindex] Indexed {fname} ({len(content)} chars)")
            else:
                print(f"[Reindex] File {fname} is empty/unreadable.")
                
        except Exception as e:
            print(f"[Reindex] Error processing {fname}: {e}")
            
    print("[Reindex] Complete.")

if __name__ == "__main__":
    reindex()
