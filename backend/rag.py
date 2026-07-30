import os
import re
import math
import uuid
import threading
from typing import List, Dict, Any, Tuple, Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# Where the persistent Chroma vector store lives on disk (next to this file)
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_data")
CHROMA_COLLECTION_NAME = "support_kb"

# Pre-defined Knowledge Base of FAQs and Support Articles
KNOWLEDGE_BASE = [
    {
        "id": "kb_refund_policy",
        "title": "Refund Policy and Exceptions",
        "category": "Billing & Refunds",
        "content": "Our standard refund policy allows returns within 30 days of purchase for a full refund. The item must be in its original packaging and unused. Exceptions: Digital downloads, personalized items, and subscription services are non-refundable after first use. Refunds take 5-7 business days to process and appear on the customer's statement.",
        "tags": ["refund", "return", "refund policy", "money back", "30 days", "exceptions"],
        "source": "built-in",
        "editable": False
    },
    {
        "id": "kb_double_charge",
        "title": "Billing Discrepancy & Double Charges",
        "category": "Billing & Refunds",
        "content": "If a customer reports a double charge or billing discrepancy, follow these steps: 1. Ask for the transaction IDs or order numbers. 2. Verify in the billing dashboard if there are duplicate pending authorizations (often one is just a hold). 3. If duplicate charges are processed, issue a refund for the second transaction immediately and send confirmation. Remind them bank processing takes 3-5 days.",
        "tags": ["double charge", "billing", "charge twice", "discrepancy", "duplicate charge"],
        "source": "built-in",
        "editable": False
    },
    {
        "id": "kb_router_reset",
        "title": "Aura Router Troubleshooting & Factory Reset",
        "category": "Technical Support",
        "content": "To resolve connection drops or slow speeds on Aura Routers: 1. Perform a basic power cycle (unplug for 30 seconds). 2. If connection remains red, do a factory reset: Press and hold the pinhole 'Reset' button on the back for 15 seconds. 3. Wait for the front LED to blink white, then reconfigure using the Aura App (default SSID is printed on the router base).",
        "tags": ["router", "reset", "factory reset", "slow internet", "wifi", "aura router", "red light"],
        "source": "built-in",
        "editable": False
    },
    {
        "id": "kb_cancellation",
        "title": "Subscription Cancellation & Retention Guidelines",
        "category": "Billing & Refunds",
        "content": "Customers can cancel their Premium Plan anytime from their Account Settings. If they ask the agent to cancel: 1. Empathize and ask for the reason. 2. Offer a retention incentive (e.g. 1 month free or down-grade to the $9 Starter package). 3. If they insist, cancel immediately. Confirm that cancellation will be effective at the end of the current billing cycle and no further charges will apply.",
        "tags": ["cancel", "cancellation", "subscription", "unsubscribe", "stop service", "retention"],
        "source": "built-in",
        "editable": False
    },
    {
        "id": "kb_password_reset",
        "title": "Password Reset & Verification Security Protocols",
        "category": "Account Security",
        "content": "To reset a customer password: 1. Instruct the customer to click 'Forgot Password' on the login screen. 2. If they cannot access their email, verify their identity: ask for the last 4 digits of the payment card on file and the billing address. 3. Once verified, trigger a secure temporary password link from the admin dashboard. Never send password strings in plain text over chat.",
        "tags": ["password", "reset password", "login issue", "forgot password", "verify identity", "security"],
        "source": "built-in",
        "editable": False
    },
    {
        "id": "kb_shipping_delays",
        "title": "Shipping Status, Delays, and Lost Packages",
        "category": "Shipping & Delivery",
        "content": "Standard shipping takes 3-5 business days. Express shipping takes 1-2 days. If a package is delayed beyond the estimated delivery date: 1. Check tracking status via DHL/FedEx API. 2. If stuck in transit for > 3 days, offer a shipping fee refund ($5.99) or reship. 3. If marked as delivered but missing, instruct customer to check with neighbors, then file a lost claim.",
        "tags": ["shipping", "delay", "delivery", "late package", "lost package", "tracking"],
        "source": "built-in",
        "editable": False
    }
]


def clean_text(text: str) -> List[str]:
    """Lowercase text and split into alphabetic tokens."""
    return re.findall(r'[a-z0-9]+', text.lower())


def calculate_tf_idf_similarity(query: str, docs: List[Dict[str, Any]]) -> List[Tuple[float, Dict[str, Any]]]:
    """
    A lightweight, pure-Python TF-IDF vector similarity search.
    """
    query_tokens = clean_text(query)
    if not query_tokens:
        return [(0.0, doc) for doc in docs]

    # Create document vocabulary and token frequencies
    doc_tokens_list = [clean_text(doc["title"] + " " + doc["content"] + " " + " ".join(doc.get("tags", []))) for doc in docs]

    # Calculate document frequency (DF) for each query token
    df = {}
    for token in set(query_tokens):
        df[token] = sum(1 for doc_tokens in doc_tokens_list if token in doc_tokens)

    # Calculate TF-IDF scores
    n_docs = len(docs)
    scores = []

    for i, doc in enumerate(docs):
        doc_tokens = doc_tokens_list[i]
        if not doc_tokens:
            scores.append((0.0, doc))
            continue

        similarity = 0.0
        # Calculate dot product
        for token in query_tokens:
            if token in doc_tokens:
                # TF in document
                tf_doc = doc_tokens.count(token) / len(doc_tokens)
                # TF in query
                tf_query = query_tokens.count(token) / len(query_tokens)
                # IDF
                doc_freq = df.get(token, 0)
                idf = math.log((1 + n_docs) / (1 + doc_freq)) + 1

                similarity += tf_doc * tf_query * (idf ** 2)

        scores.append((similarity, doc))

    return sorted(scores, key=lambda x: x[0], reverse=True)


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from PDF bytes.
    Uses PyPDF2 if available, otherwise falls back to raw byte decoding.
    """
    try:
        import io
        try:
            import pypdf as pdf_lib
            reader = pdf_lib.PdfReader(io.BytesIO(file_bytes))
        except ImportError:
            try:
                import PyPDF2 as pdf_lib
                reader = pdf_lib.PdfReader(io.BytesIO(file_bytes))
            except ImportError:
                return _fallback_pdf_text(file_bytes)

        pages_text = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(pages_text).strip()
    except Exception as e:
        return _fallback_pdf_text(file_bytes)


def _fallback_pdf_text(file_bytes: bytes) -> str:
    """Basic fallback: extract printable ASCII strings from PDF bytes."""
    text = ""
    try:
        raw = file_bytes.decode("latin-1", errors="replace")
        # Extract text between BT (begin text) and ET (end text) markers
        chunks = re.findall(r'\(([^)]{3,})\)', raw)
        text = " ".join(chunks)
        # Clean up non-printable artifacts
        text = re.sub(r'[^\x20-\x7E\n]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
    except Exception:
        text = "Could not extract text from PDF."
    return text


def _extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """Route file to appropriate text extractor based on extension."""
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        return _extract_text_from_pdf(file_bytes)
    elif ext in (".txt", ".md", ".rst", ".csv"):
        try:
            return file_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            return file_bytes.decode("latin-1", errors="replace").strip()
    elif ext in (".doc", ".docx"):
        try:
            import io
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            # Fallback: try to decode as utf-8
            try:
                return file_bytes.decode("utf-8", errors="replace").strip()
            except Exception:
                return "Could not parse .docx file. Install python-docx for full support."
    else:
        # Generic fallback
        try:
            return file_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            return "Unsupported file format."


def chunk_text(text: str, max_words: int = 220, overlap_words: int = 30) -> List[str]:
    """
    Split long text into overlapping word-count chunks so retrieval can surface
    the specific relevant passage instead of an entire document. Splits on
    paragraph boundaries first, then packs paragraphs into ~max_words chunks;
    a paragraph longer than max_words is hard-split with overlap.
    """
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []

    chunks: List[str] = []
    current_words: List[str] = []

    def flush():
        if current_words:
            chunks.append(" ".join(current_words))

    for para in paragraphs:
        words = para.split()
        if len(words) > max_words:
            # Hard-split an oversized paragraph with overlap
            flush()
            current_words.clear()
            start = 0
            while start < len(words):
                end = start + max_words
                chunks.append(" ".join(words[start:end]))
                start = end - overlap_words if end < len(words) else end
            continue

        if len(current_words) + len(words) > max_words:
            flush()
            # start new chunk with overlap from the tail of the previous one
            current_words = current_words[-overlap_words:] if overlap_words else []
        current_words.extend(words)

    flush()
    return chunks or [text.strip()]


class RAGEngine:
    def __init__(self, kb_data: List[Dict[str, Any]] = None):
        self._lock = threading.Lock()
        # Deep copy so we can mutate independently
        self.kb_data: List[Dict[str, Any]] = [dict(d) for d in (kb_data or KNOWLEDGE_BASE)]

        # Vector store starts disabled and (if enabled) gets flipped on by a
        # background thread once it's actually ready — see _init_vector_store.
        # retrieve() etc. work fine on TF-IDF in the meantime.
        self.vector_enabled = False
        self._collection = None

        vector_disabled_by_env = os.getenv("RAG_DISABLE_VECTOR", "").strip().lower() in ("1", "true", "yes")
        if CHROMADB_AVAILABLE and not vector_disabled_by_env:
            # The embedding model may need to download (~90MB) on first run.
            # That can be slow or blocked entirely depending on the network,
            # so it runs in a background thread rather than blocking app
            # startup — the app is usable on TF-IDF immediately either way,
            # and silently upgrades to vector search if/when this finishes.
            threading.Thread(target=self._init_vector_store, daemon=True).start()
        elif vector_disabled_by_env:
            print("[rag] Vector store disabled via RAG_DISABLE_VECTOR — using TF-IDF only.")

    def _init_vector_store(self):
        try:
            client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            embed_fn = embedding_functions.DefaultEmbeddingFunction()
            collection = client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                embedding_function=embed_fn,
                metadata={"hnsw:space": "cosine"},
            )
            with self._lock:
                self._collection = collection
            self._seed_vector_store()
            self.vector_enabled = True
            print("[rag] Vector store ready — now using embedding-based retrieval.")
        except Exception as e:
            print(f"[rag] Vector store unavailable, staying on TF-IDF: {e}")
            self.vector_enabled = False
            self._collection = None

    # ---------------------------------------------------------------
    # Vector store helpers
    # ---------------------------------------------------------------
    def _seed_vector_store(self):
        """Populate the Chroma collection with the built-in KB on first run only."""
        try:
            already_seeded = self._collection.count() > 0
        except Exception:
            already_seeded = False
        if not already_seeded:
            for doc in self.kb_data:
                self._upsert_vector(doc)

    def _upsert_vector(self, doc: Dict[str, Any]):
        if not self.vector_enabled:
            return
        try:
            self._collection.upsert(
                ids=[doc["id"]],
                documents=[f"{doc['title']}\n{doc['content']}"],
                metadatas=[{
                    "title": doc["title"],
                    "category": doc.get("category", "General"),
                    "tags": ",".join(doc.get("tags", [])),
                    "source": doc.get("source", "unknown"),
                    "editable": bool(doc.get("editable", True)),
                }],
            )
        except Exception as e:
            # Once the embedding backend fails once (e.g. the local ONNX model
            # couldn't download), stop retrying it on every subsequent call —
            # just degrade to TF-IDF for the rest of this process's lifetime.
            print(f"[rag] Vector store failed, disabling for this session and falling back to TF-IDF: {e}")
            self.vector_enabled = False

    def _delete_vector(self, doc_id: str):
        if not self.vector_enabled:
            return
        try:
            self._collection.delete(ids=[doc_id])
        except Exception as e:
            print(f"[rag] Vector store failed during delete, disabling for this session: {e}")
            self.vector_enabled = False

    # ---------------------------------------------------------------
    # Query
    # ---------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves the top_k most relevant support articles/chunks for the query.
        Uses ChromaDB + local embeddings when available; automatically falls
        back to the pure-Python TF-IDF matcher if the vector store isn't set up.
        """
        with self._lock:
            docs_snapshot = list(self.kb_data)

        if not query:
            return docs_snapshot[:top_k]

        if self.vector_enabled:
            try:
                return self._retrieve_vector(query, top_k, docs_snapshot)
            except Exception as e:
                print(f"[rag] Vector retrieval failed, disabling for this session and falling back to TF-IDF: {e}")
                self.vector_enabled = False

        return self._retrieve_tfidf(query, top_k, docs_snapshot)

    def _retrieve_vector(self, query: str, top_k: int, docs_snapshot: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = self._collection.query(query_texts=[query], n_results=top_k)

        ids = (results.get("ids") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]

        kb_by_id = {d["id"]: d for d in docs_snapshot}
        retrieved = []
        for i, doc_id in enumerate(ids):
            base = kb_by_id.get(doc_id)
            if base:
                doc_copy = base.copy()
            else:
                # KB entry not found in memory (e.g. process restarted with a
                # fresh in-memory list but a pre-populated persistent Chroma
                # store) — reconstruct enough of it from stored metadata.
                meta = metadatas[i] if i < len(metadatas) else {}
                tags_str = meta.get("tags", "")
                doc_copy = {
                    "id": doc_id,
                    "title": meta.get("title", "Untitled"),
                    "category": meta.get("category", "General"),
                    "content": documents[i] if i < len(documents) else "",
                    "tags": tags_str.split(",") if tags_str else [],
                    "source": meta.get("source", "unknown"),
                    "editable": meta.get("editable", True),
                }
            distance = distances[i] if i < len(distances) else None
            # Cosine distance is in [0, 2]; convert to an approximate
            # similarity score in [0, 1] for display purposes.
            doc_copy["relevance_score"] = round(max(0.0, 1 - (distance / 2)), 3) if distance is not None else None
            retrieved.append(doc_copy)
        return retrieved

    def _retrieve_tfidf(self, query: str, top_k: int, docs_snapshot: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = calculate_tf_idf_similarity(query, docs_snapshot)
        retrieved = []
        for score, doc in results[:top_k]:
            doc_copy = doc.copy()
            doc_copy["relevance_score"] = round(score, 3)
            retrieved.append(doc_copy)
        return retrieved

    # ---------------------------------------------------------------
    # Management — add / remove / list
    # ---------------------------------------------------------------
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Return all documents in the knowledge base."""
        with self._lock:
            return [dict(d) for d in self.kb_data]

    def add_document(
        self,
        title: str,
        content: str,
        category: str = "General",
        tags: List[str] = None,
        source: str = "user-added",
        doc_id: str = None,
    ) -> Dict[str, Any]:
        """Add a new document to the knowledge base. Returns the created document."""
        if not title or not content:
            raise ValueError("Title and content are required.")

        new_doc = {
            "id": doc_id or f"kb_{uuid.uuid4().hex[:10]}",
            "title": title.strip(),
            "category": category.strip() or "General",
            "content": content.strip(),
            "tags": [t.strip() for t in (tags or []) if t.strip()],
            "source": source,
            "editable": True,
        }

        with self._lock:
            # Prevent duplicate IDs
            existing_ids = {d["id"] for d in self.kb_data}
            if new_doc["id"] in existing_ids:
                new_doc["id"] = f"kb_{uuid.uuid4().hex[:10]}"
            self.kb_data.append(new_doc)

        self._upsert_vector(new_doc)
        return new_doc

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document by ID. Returns True if removed, False if not found or protected."""
        with self._lock:
            for doc in self.kb_data:
                if doc["id"] == doc_id:
                    if not doc.get("editable", True):
                        return False  # Protected built-in — refuse deletion
                    self.kb_data.remove(doc)
                    self._delete_vector(doc_id)
                    return True
        return False

    def ingest_file(
        self,
        filename: str,
        file_bytes: bytes,
        category: str = "Uploaded Document",
        tags: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parse a file (PDF, TXT, DOCX, MD, etc.), split it into retrievable chunks,
        and add each chunk to the knowledge base. Returns the list of created
        chunk documents (a short file may yield just one).
        """
        content = _extract_text_from_file(filename, file_bytes)
        if not content:
            raise ValueError("Could not extract any text from the uploaded file.")

        # Use filename (without extension) as default title
        base_title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()
        chunks = chunk_text(content)
        multi_chunk = len(chunks) > 1

        created_docs = []
        for i, chunk in enumerate(chunks):
            title = f"{base_title} (part {i + 1}/{len(chunks)})" if multi_chunk else base_title
            doc = self.add_document(
                title=title,
                content=chunk,
                category=category,
                tags=tags or [],
                source=f"file:{filename}",
            )
            created_docs.append(doc)

        return created_docs


# Single, thread-safe shared instance
rag_engine = RAGEngine()
