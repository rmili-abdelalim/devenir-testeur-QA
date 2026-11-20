"""Observabilité minimale : une trace JSONL par appel + statistiques (module 19)."""
import json
import math
import pathlib
import time


class Traceur:
    def __init__(self, chemin, version_prompt: str = "v1"):
        self.chemin, self.version_prompt = pathlib.Path(chemin), version_prompt

    def appeler(self, client, messages, **options):
        debut, erreur, reponse = time.perf_counter(), None, None
        try:
            reponse = client.chat(messages, **options)
            return reponse
        except Exception as e:
            erreur = type(e).__name__
            raise
        finally:
            ligne = {"ts": time.time(), "version_prompt": self.version_prompt,
                     "duree_s": round(time.perf_counter() - debut, 4), "erreur": erreur,
                     "taille_entree": sum(len(m["content"]) for m in messages),
                     "taille_sortie": len(reponse or "")}     # pas de contenu : données personnelles
            with self.chemin.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ligne) + "\n")


def percentile(valeurs: list[float], p: float) -> float:
    v = sorted(valeurs)
    return v[max(0, math.ceil(p / 100 * len(v)) - 1)]


def resume(chemin) -> dict:
    lignes = [json.loads(l) for l in pathlib.Path(chemin).read_text(encoding="utf-8").splitlines() if l.strip()]
    d = [l["duree_s"] for l in lignes]
    return {"appels": len(lignes), "p50_s": percentile(d, 50), "p95_s": percentile(d, 95),
            "taux_erreur": sum(l["erreur"] is not None for l in lignes) / len(lignes)}


def porte_regression(actuel: dict, reference: dict, *, tolerance: float = 0.05) -> list[str]:
    """Compare deux jeux de métriques « plus haut = mieux » ; signale toute baisse > tolérance."""
    return [f"{k} : {reference[k]:.2f} → {actuel[k]:.2f}" for k in reference if actuel.get(k, 0) < reference[k] - tolerance]
