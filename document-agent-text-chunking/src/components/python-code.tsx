'use client';

export function PythonCodeSnippet() {
  const code = `import os
import chromadb
from chromadb.utils import embedding_functions
import PyPDF2

# Initialize ChromaDB and Embedding Function
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
collection = chroma_client.get_or_create_collection(
    name="financial_research",
    embedding_function=embedding_model
)

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return "\\n".join([p.extract_text() for p in reader.pages])
    return open(file_path, 'r').read()

def chunk_text(text, size=1000, overlap=200):
    chunks = []
    for i in range(0, len(text), size - overlap):
        chunks.append(text[i:i + size])
    return chunks

def document_agent(file_path):
    """
    Extracts, Chunks, Embeds, and Stores in ChromaDB
    """
    name = os.path.basename(file_path)
    text = extract_text(file_path)
    chunks = chunk_text(text)
    
    # Generate IDs and Metadata
    ids = [f"{name}_{i}" for i in range(len(chunks))]
    meta = [{"source": name} for _ in chunks]
    
    # Store in ChromaDB (Embeddings generated automatically)
    collection.add(documents=chunks, metadatas=meta, ids=ids)
    
    return {"status": "success", "chunks": len(chunks), "db": "ChromaDB"}`;

  return (
    <div className="relative group">
      <pre className="text-xs md:text-sm font-mono text-slate-300 overflow-x-auto p-4 leading-relaxed scrollbar-hide">
        <code>{code}</code>
      </pre>
      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button 
          onClick={() => navigator.clipboard.writeText(code)}
          className="bg-slate-700 hover:bg-slate-600 text-white text-[10px] py-1 px-2 rounded border border-slate-600"
        >
          Copy Code
        </button>
      </div>
    </div>
  );
}
