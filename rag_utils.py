import os
from chromadb import Client
from sentence_transformers import SentenceTransformer
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import tempfile
import shutil
import datetime

# Global client variable for ChromaDB.
client = None

# Load a multilingual embedding model
embedding_model = SentenceTransformer('distiluse-base-multilingual-cased-v1')

# Configure Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_image(image_path):
    """Extract text from an image using Tesseract OCR."""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"Failed to extract text from image {image_path}: {e}")
        return ""

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF using PyMuPDF and Tesseract OCR."""
    try:
        text_parts = []
        # Open PDF file
        pdf_document = fitz.open(pdf_path)
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            
            # Try to get text directly first
            text = page.get_text()
            if text.strip():
                text_parts.append(text.strip())
            else:
                # If no text found, try OCR on the page image
                pix = page.get_pixmap()
                with tempfile.TemporaryDirectory() as temp_dir:
                    img_path = f"{temp_dir}/page_{page_num}.png"
                    pix.save(img_path)
                    # Extract text using OCR
                    ocr_text = extract_text_from_image(img_path)
                    if ocr_text:
                        text_parts.append(ocr_text)
        
        pdf_document.close()
        return "\n".join(text_parts)
    except Exception as e:
        print(f"Failed to extract text from PDF {pdf_path}: {e}")
        return ""

def init_chromadb(documents_directory):
    global client
    # Initialize ChromaDB client
    client = Client()

    # Get or create a collection
    collection = client.get_or_create_collection(name="documents")

    # Walk through the documents directory, including subfolders
    for root, _, files in os.walk(documents_directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                content = ""
                # Handle different file types
                if file.lower().endswith(('.txt')):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                elif file.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                    content = extract_text_from_image(file_path)
                elif file.lower().endswith('.pdf'):
                    content = extract_text_from_pdf(file_path)
                
                if content.strip():  # Only process if we have extracted content
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

def process_uploaded_file(file_path: str, destination_dir: str = "RAG_SCANNABLE_DOCUMENTS") -> tuple[str, str]:
    """
    Process an uploaded file and add it to both the conversation context and RAG system.
    Returns a tuple of (extracted_text, destination_path).
    """
    try:
        # Create destination directory if it doesn't exist
        os.makedirs(destination_dir, exist_ok=True)
        
        # Generate unique filename using timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = os.path.basename(file_path)
        base_name, ext = os.path.splitext(file_name)
        unique_name = f"{base_name}_{timestamp}{ext}"
        destination_path = os.path.join(destination_dir, unique_name)
        
        # Copy file to destination
        shutil.copy2(file_path, destination_path)
        
        # Extract text based on file type
        content = ""
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
            content = extract_text_from_image(destination_path)
        elif file_path.lower().endswith('.pdf'):
            content = extract_text_from_pdf(destination_path)
        else:
            raise ValueError("Unsupported file type")
            
        if not content.strip():
            raise ValueError("No text could be extracted from the file")
            
        # Add to ChromaDB
        if client is None:
            init_chromadb(destination_dir)
            
        collection = client.get_or_create_collection(name="documents")
        embedding = embedding_model.encode(content)
        
        # Add the document to ChromaDB
        collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[{"path": destination_path, "filename": unique_name}],
            ids=[destination_path]
        )
        
        print(f"File processed and added to RAG: {destination_path}")
        return content, destination_path
        
    except Exception as e:
        print(f"Failed to process uploaded file {file_path}: {e}")
        # Clean up if file was copied but processing failed
        if 'destination_path' in locals() and os.path.exists(destination_path):
            os.remove(destination_path)
        raise
