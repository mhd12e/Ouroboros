"""RAG: Store and retrieve solutions/memories/documents using ClickHouse vector search."""
import time
from src.db import get_client
from src.embeddings import embed_text


def chunk_text(text: str, size: int = 1000, overlap: int = 100) -> list:
    """Split text into overlapping chunks."""
    if not text:
        return []
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + size
        chunk = text[start:end]
        chunks.append(chunk)
        start += size - overlap
    return chunks


def store_document(filename: str, content: str):
    """Chunk, embed, and store a document for RAG."""
    try:
        client = get_client()
        if client is None:
            return
            
        chunks = chunk_text(content)
        data = []
        
        print(f"[RAG] Indexing '{filename}': {len(chunks)} chunks...")
        
        for i, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            data.append([filename, i, chunk, embedding])
            
        # Batch insert
        client.insert(
            'documents',
            data,
            column_names=['filename', 'chunk_index', 'content', 'embedding']
        )
        print(f"[RAG] Indexed '{filename}' successfully.")
    except Exception as e:
        print(f"[RAG] Failed to index document: {e}")


def retrieve_documents(query: str, top_k: int = 3) -> list:
    """Find relevant document chunks."""
    try:
        query_vec = embed_text(query)
        client = get_client()
        if client is None:
            return []
            
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        
        result = client.query(f"""
            SELECT filename, content, 
                   L2Distance(embedding, {vec_str}) as distance
            FROM documents
            ORDER BY distance ASC
            LIMIT {top_k}
        """)
        
        docs = []
        for row in result.result_rows:
            docs.append({
                "filename": row[0],
                "content": row[1],
                "distance": row[2]
            })
        return docs
    except Exception as e:
        print(f"[RAG] Document retrieval error: {e}")
        return []


def store_solution(task: str, code: str, result: str):
    """Embed a task and store the solution, avoiding duplicates."""
    try:
        client = get_client()
        if client is None:
            return
            
        embedding = embed_text(task)
        
        # Deduplication check
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        existing = client.query(f"""
            SELECT task, L2Distance(embedding, {vec_str}) as distance
            FROM solutions
            ORDER BY distance ASC
            LIMIT 1
        """)
        
        if existing.result_rows:
            dist = existing.result_rows[0][1]
            if dist < 0.2:
                print(f"[RAG] Skipping duplicate solution (dist={dist:.4f})")
                return

        client.insert(
            'solutions',
            [[task[:2000], code[:10000], result[:5000], embedding]],
            column_names=['task', 'code', 'result', 'embedding']
        )
        print(f"[RAG] Stored solution for: {task[:60]}...")
    except Exception as e:
        print(f"[RAG] Failed to store solution: {e}")


def retrieve_similar(query: str, top_k: int = 3) -> list:
    """Find the most similar past solutions."""
    try:
        query_vec = embed_text(query)
        client = get_client()
        if client is None:
            return []
        
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        
        result = client.query(f"""
            SELECT task, code, result,
                   L2Distance(embedding, {vec_str}) as distance
            FROM solutions
            ORDER BY distance ASC
            LIMIT {top_k}
        """)
        
        rows = []
        for row in result.result_rows:
            rows.append({
                "task": row[0],
                "code": row[1], 
                "result": row[2],
                "distance": row[3]
            })
        return rows
    except Exception as e:
        print(f"[RAG] Retrieval error: {e}")
        return []


def store_memory(fact: str):
    """Store a key fact in long-term memory."""
    try:
        client = get_client()
        if client is None:
            return
            
        embedding = embed_text(fact)
        
        # Deduplication check
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        existing = client.query(f"""
            SELECT fact, L2Distance(embedding, {vec_str}) as distance
            FROM memories
            ORDER BY distance ASC
            LIMIT 1
        """)
        
        if existing.result_rows:
            dist = existing.result_rows[0][1]
            if dist < 0.15:
                print(f"[Memory] Skipping duplicate fact (dist={dist:.4f})")
                return

        client.insert(
            'memories',
            [[fact[:2000], embedding]],
            column_names=['fact', 'embedding']
        )
        print(f"[Memory] Stored: {fact[:60]}...")
    except Exception as e:
        print(f"[Memory] Failed to store: {e}")


def retrieve_memories(query: str, limit: int = 5) -> list:
    """Retrieve relevant memories."""
    try:
        query_vec = embed_text(query)
        client = get_client()
        if client is None:
            return []
            
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        
        result = client.query(f"""
            SELECT fact, L2Distance(embedding, {vec_str}) as distance
            FROM memories
            ORDER BY distance ASC
            LIMIT {limit}
        """)
        
        facts = [row[0] for row in result.result_rows]
        return facts
    except Exception as e:
        print(f"[Memory] Retrieval error: {e}")
        return []


def retrieve_recent_memories(limit: int = 10) -> list:
    """Retrieve the most recent memories."""
    try:
        client = get_client()
        if client is None:
            return []
            
        result = client.query(f"""
            SELECT fact FROM memories
            ORDER BY created_at DESC
            LIMIT {limit}
        """)
        
        facts = [row[0] for row in result.result_rows]
        return facts
    except Exception as e:
        print(f"[Memory] Recent retrieval error: {e}")
        return []


    return "\n".join(parts)


def store_lesson(prompt: str, response: str, lesson: str):
    """Store a self-improvement lesson in ClickHouse."""
    try:
        client = get_client()
        if client is None:
            return
            
        embedding = embed_text(prompt + " " + lesson)
        
        client.insert(
            'lessons',
            [[prompt[:2000], response[:5000], lesson[:2000], embedding]],
            column_names=['prompt', 'response', 'lesson', 'embedding']
        )
        print(f"[RAG] Stored lesson for prompt: {prompt[:60]}...")
    except Exception as e:
        print(f"[RAG] Failed to store lesson: {e}")


def retrieve_lessons(query: str, limit: int = 3) -> list:
    """Retrieve relevant past lessons."""
    try:
        query_vec = embed_text(query)
        client = get_client()
        if client is None:
            return []
            
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        
        result = client.query(f"""
            SELECT prompt, response, lesson,
                   L2Distance(embedding, {vec_str}) as distance
            FROM lessons
            ORDER BY distance ASC
            LIMIT {limit}
        """)
        
        lessons = []
        for row in result.result_rows:
            lessons.append({
                "prompt": row[0],
                "response": row[1],
                "lesson": row[2],
                "distance": row[3]
            })
        return lessons
    except Exception as e:
        print(f"[RAG] Lesson retrieval error: {e}")
        return []


def format_rag_context(solutions: list, memories: list = None, documents: list = None, lessons: list = None) -> str:
    """Format retrieved context into a single string."""
    parts = []
    
    if lessons:
        parts.append("=== PAST LESSONS (SELF-IMPROVEMENT) ===")
        for l in lessons:
            parts.append(f"• PAST PROMPT: {l['prompt']}")
            parts.append(f"  LESSON LEARNED: {l['lesson']}")
        parts.append("")

    if memories:
        parts.append("=== RELEVANT MEMORIES ===")
        for m in memories:
            parts.append(f"• {m}")
        parts.append("")
        
    if documents:
        parts.append("=== RELEVANT DOCUMENT CHUNKS ===")
        for doc in documents:
            parts.append(f"\n--- From '{doc['filename']}' ---")
            parts.append(doc['content'])
        parts.append("")
        
    if solutions:
        parts.append("=== SIMILAR PAST SOLUTIONS ===")
        for i, sol in enumerate(solutions, 1):
            parts.append(f"\n--- Solution {i} (distance: {sol['distance']:.4f}) ---")
            parts.append(f"Task: {sol['task']}")
            parts.append(f"Code:\n{sol['code'][:2000]}")
            parts.append(f"Result: {sol['result'][:200]}")
    elif not memories and not documents and not lessons:
        parts.append("No similar past solutions found.")
    
    return "\n".join(parts)
