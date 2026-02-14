"""Amazon Titan text embeddings via AWS Bedrock."""
import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

_bedrock_client = None

def _get_bedrock():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-west-2"),
        )
    return _bedrock_client


def embed_text(text: str) -> list:
    """Generate a 1536-dim embedding vector using Amazon Titan.
    
    Args:
        text: Input text to embed (max ~8k tokens)
    
    Returns:
        List of 1536 floats
    """
    client = _get_bedrock()
    body = json.dumps({"inputText": text[:8000]})  # Titan limit
    
    response = client.invoke_model(
        modelId="amazon.titan-embed-text-v1",
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    
    result = json.loads(response["body"].read())
    return result["embedding"]


def embed_batch(texts: list) -> list:
    """Embed multiple texts. Returns list of vectors."""
    return [embed_text(t) for t in texts]
