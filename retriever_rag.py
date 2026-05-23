"""
retriever_rag.py — Coordinates chunk retrieval from SOP.
Implements a hybrid retrieval strategy:
1. OpenAI Vector Search (if API key is present).
2. Local SentenceTransformer Search (if sentence-transformers is installed).
3. Pure-Python BM25 Retriever (fallback keyword matcher).
Also incorporates Stage-Aware Context Preservation to ensure catalog/booking info
remains in context during qualification phases.
"""

import os
import re
import math
from openai import OpenAI
from sop_rag import get_sop_chunks

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class BM25Retriever:
    def __init__(self, documents, k1=1.5, b=0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.doc_len = []
        self.avg_doc_len = 0.0
        self.doc_count = len(documents)
        self.vocab = {}
        self.df = {}
        self.idf = {}
        self.doc_tfs = []
        self._initialize()

    def _tokenize(self, text):
        return re.findall(r'\b\w+\b', text.lower())

    def _initialize(self):
        total_len = 0
        for doc in self.documents:
            tokens = self._tokenize(doc["text"])
            total_len += len(tokens)
            self.doc_len.append(len(tokens))
            
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_tfs.append(tf)
            
            for token in tf.keys():
                self.df[token] = self.df.get(token, 0) + 1
                
        self.avg_doc_len = total_len / self.doc_count if self.doc_count > 0 else 0.0
        
        for token, df_val in self.df.items():
            self.idf[token] = math.log((self.doc_count - df_val + 0.5) / (df_val + 0.5) + 1.0)

    def score(self, query, index):
        query_tokens = self._tokenize(query)
        score = 0.0
        doc_tf = self.doc_tfs[index]
        d_len = self.doc_len[index]
        
        for token in query_tokens:
            if token not in doc_tf:
                continue
            tf_val = doc_tf[token]
            idf_val = self.idf.get(token, 0.0)
            numerator = tf_val * (self.k1 + 1)
            denominator = tf_val + self.k1 * (1 - self.b + self.b * (d_len / self.avg_doc_len))
            score += idf_val * (numerator / denominator)
        return score

    def retrieve(self, query, top_n=3, score_threshold=0.8):
        scored_docs = []
        for i in range(self.doc_count):
            score_val = self.score(query, i)
            scored_docs.append((self.documents[i], score_val))
            
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for doc, score_val in scored_docs:
            if score_val >= score_threshold:
                results.append((doc, score_val))
        return results[:top_n]


def cosine_similarity(v1, v2):
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = math.sqrt(sum(x * x for x in v1))
    norm_v2 = math.sqrt(sum(y * y for y in v2))
    if norm_v1 * norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


class ClosiraRAGRetriever:
    def __init__(self):
        self.chunks = get_sop_chunks()
        self.bm25 = BM25Retriever(self.chunks)
        
        # Check for OpenAI API key
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.use_vector = bool(self.openai_key)
        self.use_local_vector = False
        self.local_model = None
        self.chunk_embeddings = {}
        
        if self.use_vector:
            try:
                # Pre-embed all chunks once at startup to save latency
                client = OpenAI(api_key=self.openai_key)
                texts = [c["text"] for c in self.chunks]
                response = client.embeddings.create(
                    input=texts,
                    model="text-embedding-3-small"
                )
                for idx, item in enumerate(response.data):
                    self.chunk_embeddings[self.chunks[idx]["id"]] = item.embedding
            except Exception as e:
                print(f"[RAG] OpenAI Embedding failed: {e}. Trying local SentenceTransformer.")
                self.use_vector = False

        if not self.use_vector:
            if HAS_SENTENCE_TRANSFORMERS:
                try:
                    print("[RAG] Initializing local semantic retriever (all-MiniLM-L6-v2)...")
                    self.local_model = SentenceTransformer('all-MiniLM-L6-v2')
                    texts = [c["text"] for c in self.chunks]
                    embeddings = self.local_model.encode(texts).tolist()
                    for idx, emb in enumerate(embeddings):
                        self.chunk_embeddings[self.chunks[idx]["id"]] = emb
                    self.use_local_vector = True
                    print("[RAG] Local semantic retriever initialized successfully.")
                except Exception as e:
                    print(f"[RAG] Local embedding initialization failed: {e}. Falling back to BM25.")
            else:
                print("[RAG] Local sentence-transformers library not installed. Falling back to BM25.")

    def retrieve_vector(self, query, top_n=3, threshold=0.35):
        try:
            client = OpenAI(api_key=self.openai_key)
            response = client.embeddings.create(
                input=[query],
                model="text-embedding-3-small"
            )
            query_embedding = response.data[0].embedding
            
            scored_docs = []
            for chunk in self.chunks:
                chunk_emb = self.chunk_embeddings.get(chunk["id"])
                if chunk_emb:
                    sim = cosine_similarity(query_embedding, chunk_emb)
                    if sim >= threshold:
                        scored_docs.append((chunk, sim))
            
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            return scored_docs[:top_n]
        except Exception:
            if HAS_SENTENCE_TRANSFORMERS:
                return self.retrieve_local_vector(query, top_n=top_n)
            return self.bm25.retrieve(query, top_n=top_n)

    def retrieve_local_vector(self, query, top_n=3, threshold=0.30):
        try:
            query_embedding = self.local_model.encode([query])[0].tolist()
            scored_docs = []
            for chunk in self.chunks:
                chunk_emb = self.chunk_embeddings.get(chunk["id"])
                if chunk_emb:
                    sim = cosine_similarity(query_embedding, chunk_emb)
                    if sim >= threshold:
                        scored_docs.append((chunk, sim))
            
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            return scored_docs[:top_n]
        except Exception:
            return self.bm25.retrieve(query, top_n=top_n)

    def retrieve(self, query, current_stage="answering_question", top_n=3) -> tuple:
        """
        Retrieves matching chunks and returns: (list_of_chunks, query_has_match)
        """
        query_has_match = False
        matched_chunks = []
        
        if self.use_vector:
            matched_chunks = self.retrieve_vector(query, top_n=top_n)
        elif self.use_local_vector:
            matched_chunks = self.retrieve_local_vector(query, top_n=top_n)
        else:
            matched_chunks = self.bm25.retrieve(query, top_n=top_n)
            
        retrieved = [doc for doc, score in matched_chunks]
        if retrieved:
            query_has_match = True
            
        # Stage-Aware Context Preservation
        # If in a plan-recommendation or booking helper stage, always append plan and booking specs.
        # This keeps critical business definitions contextually active during short user responses.
        if current_stage in ["recommending_plan", "booking_help"]:
            # Ensure plans-related chunks are appended
            has_plans = any("plan" in c["category"].lower() for c in retrieved)
            if not has_plans:
                for chunk in self.chunks:
                    if "plan" in chunk["category"].lower():
                        retrieved.append(chunk)
            
            # Ensure booking-related chunks are appended
            has_booking = any("book" in c["category"].lower() for c in retrieved)
            if not has_booking:
                for chunk in self.chunks:
                    if "book" in chunk["category"].lower():
                        retrieved.append(chunk)
                        
        return retrieved, query_has_match
