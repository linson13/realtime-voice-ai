import logging
import numpy as np

logger = logging.getLogger(__name__)

class RAGEngine:
    """
    Lightweight local RAG using sentence-transformers + FAISS.
    No API key needed. Fully offline.
    
    Usage:
        rag = RAGEngine()
        rag.load("Your knowledge base text here...")
        context = rag.query("What is the refund policy?")
    """

    def __init__(self, chunk_size: int = 300, top_k: int = 3):
        self.chunk_size = chunk_size
        self.top_k      = top_k
        self._model     = None
        self._index     = None
        self._chunks: list[str] = []
        self._ready     = False

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformer model…")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence-transformer loaded ✓")
        return self._model

    def load(self, text: str):
        """Split text into chunks, embed, and build FAISS index."""
        try:
            import faiss
            model = self._load_model()

            # Chunk the text
            words  = text.split()
            chunks = []
            for i in range(0, len(words), self.chunk_size):
                chunk = " ".join(words[i:i + self.chunk_size])
                if chunk.strip():
                    chunks.append(chunk)

            if not chunks:
                logger.warning("RAG: No chunks created — text may be empty")
                return

            self._chunks = chunks
            logger.info(f"RAG: {len(chunks)} chunks created")

            # Embed all chunks
            embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
            embeddings = embeddings.astype(np.float32)

            # L2-normalise for cosine similarity via inner product
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / (norms + 1e-8)

            # Build FAISS flat index
            dim          = embeddings.shape[1]
            self._index  = faiss.IndexFlatIP(dim)
            self._index.add(embeddings)
            self._ready  = True

            logger.info(f"RAG: FAISS index built ({dim}d, {len(chunks)} vectors) ✓")

        except ImportError as e:
            logger.warning(f"RAG dependencies missing ({e}). RAG disabled.")
        except Exception as e:
            logger.error(f"RAG load error: {e}", exc_info=True)

    def query(self, question: str, top_k: int | None = None) -> str:
        """Retrieve top-k relevant chunks for the question."""
        if not self._ready or not self._index:
            return ""

        try:
            k     = top_k or self.top_k
            model = self._load_model()

            q_emb = model.encode([question], convert_to_numpy=True).astype(np.float32)
            q_emb = q_emb / (np.linalg.norm(q_emb, axis=1, keepdims=True) + 1e-8)

            scores, indices = self._index.search(q_emb, k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score > 0.3:   # Score threshold
                    results.append(self._chunks[idx])

            context = "\n\n".join(results)
            logger.info(f"RAG: Retrieved {len(results)} chunks (scores: {scores[0].tolist()})")
            return context

        except Exception as e:
            logger.error(f"RAG query error: {e}", exc_info=True)
            return ""

    def is_ready(self) -> bool:
        return self._ready
