import os
from chromadb import Client
from sentence_transformers import SentenceTransformer

# Global client variable for ChromaDB.
client = None

# Load a multilingual embedding model
embedding_model = SentenceTransformer('distiluse-base-multilingual-cased-v1')

def init_chromadb(documents_directory):
    global client
    # Initialize ChromaDB client
    client = Client()

    # Get or create a collection
    collection = client.get_or_create_collection(name="documents")

    # Walk through the documents directory, including subfolders
    for root, _, files in os.walk(documents_directory):
        for file in files:
            if file.endswith(".txt"):  # Adjust file type as needed
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Generate multilingual embeddings for the document
                        embedding = embedding_model.encode(content)
                        # Add the document to the collection with its embedding
                        collection.add(
                            documents=[content],
                            embeddings=[embedding],
                            metadatas=[{"path": file_path}],
                            ids=[file_path]  # Use the file path as a unique ID
                        )
                        print(f"Document added: {file_path}")  # Debug statement
                except Exception as e:
                    print(f"Failed to load {file_path}: {e}")

def query_context(prompt: str, n_results: int = 5, similarity_threshold: float = 1.5) -> str:
    if client is None:
        raise Exception("ChromaDB not initialized. Call init_chromadb() first.")
    
    # Get or create a collection
    collection = client.get_or_create_collection(name="documents")

    # Generate multilingual embeddings for the prompt
    prompt_embedding = embedding_model.encode(prompt)

    # Perform the query using the prompt embedding
    results = collection.query(
        query_embeddings=[prompt_embedding],
        n_results=n_results
    )

    # Extract documents and distances
    if results and "documents" in results and results["documents"]:
        documents = results["documents"][0]
        distances = results.get("distances", [[]])[0]  # Get distances for the first query

        # Log the distances for debugging
        print("Query Results (Distances):", list(zip(documents, distances)))  # Debug statement

        # Filter documents based on the distance threshold (lower is better)
        filtered_documents = [
            doc for doc, distance in zip(documents, distances) if distance <= similarity_threshold
        ]

        # Return the filtered context as a single string
        if filtered_documents:
            return "\n".join(filtered_documents)
    
    return ""  # Return an empty string if no documents meet the threshold
