import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List

class SemanticRetriever:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, embedding_model: str = "text-embedding-3-small"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.client = OpenAI()
        self.chunks = []
        self.chunk_embeddings = None
        
    def chunk_text(self, text: str, source_title: str) -> List[Dict[str, str]]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            chunks.append({
                'text': chunk_text,
                'source': source_title,
                'start_idx': i
            })
            
        return chunks
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for a list of texts using OpenAI API."""
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.embedding_model
            )
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings)
        except Exception as e:
            print(f"Error getting embeddings: {e}")
            return None
    
    def add_documents(self, documents: List[Dict[str, str]]):
        """Add documents to the RAG system."""
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_text(doc['content'], doc['title'])
            all_chunks.extend(chunks)
        
        self.chunks = all_chunks
        
        # Get embeddings for all chunks
        if self.chunks:
            chunk_texts = [chunk['text'] for chunk in self.chunks]
            # Process in batches to avoid API limits
            batch_size = 100
            all_embeddings = []
            
            for i in range(0, len(chunk_texts), batch_size):
                batch_texts = chunk_texts[i:i + batch_size]
                batch_embeddings = self.get_embeddings(batch_texts)
                if batch_embeddings is not None:
                    all_embeddings.extend(batch_embeddings)
                else:
                    # Fallback: create zero embeddings if API fails
                    all_embeddings.extend([np.zeros(1536) for _ in batch_texts])
            
            self.chunk_embeddings = np.array(all_embeddings)
    
    def retrieve_relevant_chunks(self, query: str, top_k: int = 3) -> List[Dict[str, str]]:
        """Retrieve most relevant chunks for a query."""
        if not self.chunks or self.chunk_embeddings is None:
            return []
        
        # Get embedding for the query
        query_embedding = self.get_embeddings([query])
        if query_embedding is None:
            return []
        
        query_embedding = query_embedding[0].reshape(1, -1)
        
        # Calculate similarities
        similarities = cosine_similarity(query_embedding, self.chunk_embeddings).flatten()
        
        # Get top-k most similar chunks
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        relevant_chunks = []
        for idx in top_indices:
            if similarities[idx] > 0.3:  # Minimum similarity threshold for embeddings
                chunk = self.chunks[idx].copy()
                chunk['similarity'] = similarities[idx]
                relevant_chunks.append(chunk)
        
        return relevant_chunks