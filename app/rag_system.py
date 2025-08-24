import os
import json
import pickle
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import PyPDF2
from dotenv import load_dotenv

load_dotenv()

class RAGSystem:
    """RAG system with Gemini AI and semantic search"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        # Configure Gemini AI
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Load embedding model
        print("Loading sentence transformer model...")
        self.embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embedding model loaded successfully!")
        
        # Storage paths
        self.storage_dir = "storage"
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for i, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += f"[Page {i+1}]\n{page_text}\n\n"
            return text
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    def create_chunks(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """Create text chunks for processing"""
        sentences = text.split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def process_document(self, file_path: str, user_id: int) -> str:
        """Process a document and create embeddings"""
        try:
            print(f"Processing document: {os.path.basename(file_path)}")
            
            # Extract text
            text = self.extract_text_from_pdf(file_path)
            
            # Create chunks
            chunks = self.create_chunks(text)
            print(f"Created {len(chunks)} chunks")
            
            # Generate embeddings
            print("Generating embeddings...")
            embeddings = self.embeddings_model.encode(chunks)
            
            # Create document ID
            filename = os.path.basename(file_path)
            doc_id = f"user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            
            # Save embeddings and metadata
            embedding_data = {
                'doc_id': doc_id,
                'user_id': user_id,
                'filename': filename,
                'chunks': chunks,
                'embeddings': embeddings.tolist(),
                'processed_at': datetime.utcnow().isoformat(),
                'chunk_count': len(chunks)
            }
            
            # Save to file
            embedding_file = os.path.join(self.storage_dir, f"{doc_id}.pkl")
            with open(embedding_file, 'wb') as f:
                pickle.dump(embedding_data, f)
            
            # Update user's document index
            self._update_user_index(user_id, doc_id, embedding_data)
            
            print(f"✅ Document processed successfully: {doc_id}")
            return doc_id
            
        except Exception as e:
            raise Exception(f"Error processing document: {str(e)}")
    
    def _update_user_index(self, user_id: int, doc_id: str, doc_data: dict):
        """Update user's document index"""
        index_file = os.path.join(self.storage_dir, f"user_{user_id}_index.json")
        
        # Load existing index or create new one
        user_index = {}
        if os.path.exists(index_file):
            with open(index_file, 'r') as f:
                user_index = json.load(f)
        
        # Add document to index
        user_index[doc_id] = {
            'filename': doc_data['filename'],
            'processed_at': doc_data['processed_at'],
            'chunk_count': doc_data['chunk_count']
        }
        
        # Save updated index
        with open(index_file, 'w') as f:
            json.dump(user_index, f, indent=2)
    
    def get_user_documents(self, user_id: int) -> List[Dict]:
        """Get list of user's processed documents"""
        index_file = os.path.join(self.storage_dir, f"user_{user_id}_index.json")
        
        if os.path.exists(index_file):
            with open(index_file, 'r') as f:
                return list(json.load(f).values())
        return []
    
    def _load_user_embeddings(self, user_id: int) -> Dict:
        """Load all embeddings for a user"""
        index_file = os.path.join(self.storage_dir, f"user_{user_id}_index.json")
        
        if not os.path.exists(index_file):
            return {'chunks': [], 'embeddings': [], 'metadata': []}
        
        with open(index_file, 'r') as f:
            user_index = json.load(f)
        
        all_chunks = []
        all_embeddings = []
        all_metadata = []
        
        for doc_id in user_index.keys():
            embedding_file = os.path.join(self.storage_dir, f"{doc_id}.pkl")
            if os.path.exists(embedding_file):
                with open(embedding_file, 'rb') as f:
                    doc_data = pickle.load(f)
                
                all_chunks.extend(doc_data['chunks'])
                all_embeddings.extend(doc_data['embeddings'])
                
                for i, chunk in enumerate(doc_data['chunks']):
                    all_metadata.append({
                        'doc_id': doc_id,
                        'filename': doc_data['filename'],
                        'chunk_index': i
                    })
        
        return {
            'chunks': all_chunks,
            'embeddings': np.array(all_embeddings) if all_embeddings else np.array([]),
            'metadata': all_metadata
        }
    
    def semantic_search(self, query: str, user_id: int, top_k: int = 5) -> List[Dict]:
        """Perform semantic search on user's documents"""
        try:
            # Load user embeddings
            user_data = self._load_user_embeddings(user_id)
            
            if len(user_data['embeddings']) == 0:
                return []
            
            # Generate query embedding
            query_embedding = self.embeddings_model.encode([query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_embedding, user_data['embeddings'])[0]
            
            # Get top results
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    results.append({
                        'content': user_data['chunks'][idx],
                        'metadata': user_data['metadata'][idx],
                        'similarity': float(similarities[idx])
                    })
            
            return results
            
        except Exception as e:
            print(f"Error in semantic search: {str(e)}")
            return []
    
    async def get_answer(self, question: str, user_id: int, top_k: int = 5) -> Dict:
        """Get AI answer using RAG"""
        try:
            # Perform semantic search
            relevant_chunks = self.semantic_search(question, user_id, top_k)
            
            if not relevant_chunks:
                return {
                    "answer": "I don't have any relevant information in your uploaded documents to answer this question. Please upload relevant medical documents first.",
                    "sources": []
                }
            
            # Create context from relevant chunks
            context = "\n\n".join([
                f"Source: {chunk['metadata']['filename']}\n{chunk['content']}"
                for chunk in relevant_chunks
            ])
            
            # Create enhanced prompt for Gemini
            prompt = f"""
            You are an expert healthcare information assistant. Answer the user's question based ONLY on the provided context from medical documents.
            
            Context from medical documents:
            {context}
            
            User Question: {question}
            
            Instructions:
            1. Answer based strictly on the provided context
            2. If the information is not in the context, clearly state this
            3. Provide specific medical information when available
            4. Include relevant dosage, administration, contraindications if mentioned
            5. Always remind users to consult healthcare professionals
            6. Be precise, helpful, and medically accurate
            
            Please provide a detailed, accurate answer followed by:
            "Important: This information is for educational purposes only. Always consult with healthcare professionals for medical advice, diagnosis, or treatment decisions."
            """
            
            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Lower temperature for medical accuracy
                    max_output_tokens=1000,
                )
            )
            
            # Prepare sources information
            sources = []
            for chunk in relevant_chunks:
                sources.append({
                    'filename': chunk['metadata']['filename'],
                    'similarity': chunk['similarity'],
                    'content_preview': chunk['content'][:200] + "..."
                })
            
            return {
                "answer": response.text,
                "sources": sources
            }
            
        except Exception as e:
            return {
                "answer": f"I encountered an error while processing your question: {str(e)}. Please try again.",
                "sources": []
            }
