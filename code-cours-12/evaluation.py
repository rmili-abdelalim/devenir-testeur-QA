"""Évaluer un système d'IA : métriques simples et honnêtes (modules 14-15)."""
import json
import pathlib
import re
import unicodedata


def charger_jeu(chemin) -> list[dict]:
    """Jeu de référence au format JSONL : une ligne = un cas {id, question, attendu…}."""
    return [json.loads(l) for l in pathlib.Path(chemin).read_text(encoding="utf-8").splitlines() if l.strip()]


def taux_reussite(cas: list[dict], systeme, verifie) -> dict:
    echecs = [c["id"] for c in cas if not verifie(c, systeme(c))]
    return {"total": len(cas), "reussis": len(cas) - len(echecs), "taux": 1 - len(echecs) / len(cas), "echecs": echecs}


def hit_at_k(classements: list[list[str]], attendus: list[str], k: int) -> float:
    return sum(a in c[:k] for c, a in zip(classements, attendus)) / len(attendus)


def mrr(classements: list[list[str]], attendus: list[str]) -> float:
    total = 0.0
    for c, a in zip(classements, attendus):
        if a in c:
            total += 1 / (c.index(a) + 1)
    return total / len(attendus)


def _normaliser(t: str) -> list[str]:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9_]{3,}", t)


def ancrage_lexical(reponse: str, extraits: list[str]) -> float:
    """Part des mots « utiles » de la réponse qui apparaissent dans les extraits (0 à 1).
    Un garde-fou BON MARCHÉ contre l'hallucination, pas une preuve : il rate les paraphrases."""
    vocabulaire = {m for e in extraits for m in _normaliser(e)}
    mots = [m for m in _normaliser(re.sub(r"\[\d+\]", "", reponse)) if len(m) > 4]
    return 1.0 if not mots else sum(m in vocabulaire for m in mots) / len(mots)


def accord(verdicts_juge: list[bool], verdicts_humain: list[bool]) -> dict:
    """Calibration d'un « LLM juge » face à un humain : accord brut et kappa de Cohen."""
    n = len(verdicts_juge)
    po = sum(j == h for j, h in zip(verdicts_juge, verdicts_humain)) / n
    pj, ph = sum(verdicts_juge) / n, sum(verdicts_humain) / n
    pe = pj * ph + (1 - pj) * (1 - ph)
    kappa = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    return {"accord": po, "kappa": kappa}


def verifier_seuils(metriques: dict[str, float], seuils: dict[str, float]) -> list[str]:
    """Liste les métriques sous leur seuil (liste vide = on peut livrer)."""
    return [f"{nom} = {metriques[nom]:.2f} < {mini:.2f}" for nom, mini in seuils.items() if metriques[nom] < mini]
