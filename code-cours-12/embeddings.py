"""Embeddings, similarité cosinus et recherche (modules 9-10)."""
import math
import re
import unicodedata

import httpx


def cosinus(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return 0.0 if na == 0 or nb == 0 else sum(x * y for x, y in zip(a, b)) / (na * nb)


class OllamaEmbedder:
    """Appelle /api/embed d'Ollama (ex. modèle « nomic-embed-text » à télécharger au préalable)."""
    def __init__(self, modele="nomic-embed-text", url="http://localhost:11434"):
        self.modele, self.url = modele, url

    def embed(self, textes: list[str]) -> list[list[float]]:
        r = httpx.post(f"{self.url}/api/embed", json={"model": self.modele, "input": textes}, timeout=120)
        r.raise_for_status()
        return r.json()["embeddings"]


def _mots(t: str) -> list[str]:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]{3,}", t)


class FauxEmbedder:
    """Embedder lexical (sac de mots hachés) : déterministe, gratuit, parfait pour tester la plomberie."""
    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, textes: list[str]) -> list[list[float]]:
        sortie = []
        for t in textes:
            v = [0.0] * self.dim
            for m in _mots(t):
                v[sum(ord(c) * 31 ** i for i, c in enumerate(m)) % self.dim] += 1.0
            sortie.append(v)
        return sortie


class MemoireVectorielle:
    """Mini base vectorielle en mémoire : le même contrat que pgvector, sans serveur."""
    def __init__(self, embedder):
        self.embedder, self.items = embedder, []

    def ajouter(self, textes: list[str], metas: list[dict] | None = None) -> None:
        metas = metas or [{} for _ in textes]
        for t, m, v in zip(textes, metas, self.embedder.embed(textes)):
            self.items.append({"texte": t, "meta": m, "vecteur": v})

    def chercher(self, question: str, k: int = 3) -> list[dict]:
        q = self.embedder.embed([question])[0]
        notes = [{**it, "score": cosinus(q, it["vecteur"])} for it in self.items]
        return sorted(notes, key=lambda x: x["score"], reverse=True)[:k]


def rappel_a_k(base, cas: list[tuple[str, str]], k: int = 3) -> float:
    """Part des questions dont la bonne source est dans les k premiers résultats."""
    ok = sum(any(r["meta"].get("source") == source for r in base.chercher(q, k)) for q, source in cas)
    return ok / len(cas)
