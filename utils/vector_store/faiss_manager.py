import os
import pickle
from typing import List, Dict, Optional, Tuple
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

class FAISSManager:
    def __init__(self, index_path: str, model_name: str = 'all-MiniLM-L6-v2'):
        self.index_path = index_path
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.metadata = []
        self.dimension = 384
        
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        index_file = os.path.join(self.index_path, "index.faiss")
        metadata_file = os.path.join(self.index_path, "metadata.pkl")
        
        if os.path.exists(index_file) and os.path.exists(metadata_file):
            self.index = faiss.read_index(index_file)
            with open(metadata_file, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
    
    def add_documents(self, documents: List[Dict[str, str]]):
        texts = [doc['text'] for doc in documents]
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        
        self.index.add(embeddings.astype('float32'))
        self.metadata.extend(documents)
        
        self._save_index()
    
    def search(self, query: str, k: int = 5) -> List[Tuple[Dict, float]]:
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding.astype('float32'), k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                results.append((self.metadata[idx], float(distances[0][i])))
        
        return results
    
    def _save_index(self):
        index_file = os.path.join(self.index_path, "index.faiss")
        metadata_file = os.path.join(self.index_path, "metadata.pkl")
        
        faiss.write_index(self.index, index_file)
        with open(metadata_file, 'wb') as f:
            pickle.dump(self.metadata, f)
    
    def get_document_count(self) -> int:
        return len(self.metadata)
    
    def clear_index(self):
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        self._save_index()
