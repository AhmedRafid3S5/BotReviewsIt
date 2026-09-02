"""Embedding index + retrieval over the scraped specs (local nomic-embed-text)."""
import numpy as np
from langchain_ollama import OllamaEmbeddings
import database
from config import EMBED_HOST, EMBED_MODEL

_embedder = OllamaEmbeddings(model=EMBED_MODEL, base_url=EMBED_HOST)


def _chunks_for_phone(phone, specs):
    """One chunk per spec category, plus a one-line overview."""
    by_cat = {}
    for s in specs:
        by_cat.setdefault(s["category"], []).append(f"{s['spec_name']}: {s['spec_value']}")
    chunks = [
        f"{phone['name']} | {cat}\n" + "\n".join(lines)
        for cat, lines in by_cat.items()
    ]
    chunks.append(f"{phone['name']} is a Samsung smartphone. Categories: {', '.join(by_cat)}.")
    return chunks


def build_index():
    database.clear_embeddings()
    for phone in database.list_phones():
        data = database.get_specs(phone["name"])
        chunks = _chunks_for_phone(phone, data["specs"])
        vectors = _embedder.embed_documents(chunks)
        for chunk, vec in zip(chunks, vectors):
            blob = np.asarray(vec, dtype=np.float32).tobytes()
            database.save_embedding(phone["id"], chunk, blob)
        print(f"Indexed {phone['name']} ({len(chunks)} chunks)")


class Retriever:
    def __init__(self):
        rows = database.load_embeddings()
        self.chunks = [(r["phone_name"], r["chunk"]) for r in rows]
        mat = np.stack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
        self.matrix = mat / np.linalg.norm(mat, axis=1, keepdims=True)

    def search(self, query, k=6):
        q = np.asarray(_embedder.embed_query(query), dtype=np.float32)
        q /= np.linalg.norm(q)
        scores = self.matrix @ q
        top = np.argsort(scores)[::-1][:k]
        return [{"phone": self.chunks[i][0], "chunk": self.chunks[i][1],
                 "score": float(scores[i])} for i in top]


if __name__ == "__main__":
    build_index()
