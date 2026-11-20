"""Agent simple : un objectif, des outils, des garde-fous (module 12)."""
import json
import time

from pydantic import ValidationError

from outils import Decision, Outil, catalogue, SYSTEME_OUTILS
from structure import extraire_json


class ArretAgent(Exception):
    def __init__(self, raison: str, journal: list):
        super().__init__(raison)
        self.raison, self.journal = raison, journal


def lancer_agent(client, outils: dict[str, Outil], objectif: str, *, max_etapes: int = 6,
                 delai_max_s: float = 60, approuver=lambda nom, args: False) -> dict:
    journal, debut = [], time.monotonic()
    messages = [{"role": "system", "content": "Tu es un agent QA qui atteint son objectif étape par étape.\n"
                 + SYSTEME_OUTILS.format(catalogue=catalogue(outils))},
                {"role": "user", "content": f"Objectif : {objectif}"}]
    vus = set()
    for etape in range(1, max_etapes + 1):
        if time.monotonic() - debut > delai_max_s:
            raise ArretAgent("délai dépassé", journal)
        texte = client.chat(messages, temperature=0.0)
        try:
            d = Decision.model_validate_json(extraire_json(texte))
        except (ValidationError, json.JSONDecodeError):
            journal.append({"etape": etape, "erreur": "décision illisible"})
            messages += [{"role": "assistant", "content": texte}, {"role": "user", "content": "JSON invalide, recommence."}]
            continue
        if d.reponse is not None:
            journal.append({"etape": etape, "fin": d.reponse})
            return {"resultat": d.reponse, "journal": journal, "etapes": etape}
        cle = (d.outil, json.dumps(d.arguments, sort_keys=True))
        if cle in vus:                                   # même action deux fois = boucle probable
            raise ArretAgent("boucle détectée (même appel répété)", journal)
        vus.add(cle)
        outil = outils.get(d.outil or "")
        if outil is None:
            resultat = f"ERREUR : outil inconnu {d.outil!r}"
        elif outil.ecriture and not approuver(outil.nom, d.arguments):
            resultat = "REFUSÉ : action d'écriture non approuvée."
        else:
            try:
                resultat = json.dumps(outil.fonction(outil.schema(**d.arguments)), ensure_ascii=False, default=str)
            except Exception as e:                       # une erreur d'outil est une information, pas un crash
                resultat = f"ERREUR outil : {e}"
        journal.append({"etape": etape, "outil": d.outil, "arguments": d.arguments, "resultat": resultat[:200]})
        messages += [{"role": "assistant", "content": texte},
                     {"role": "user", "content": f"<resultat outil={d.outil}>{resultat[:2000]}</resultat>"}]
    raise ArretAgent(f"{max_etapes} étapes sans conclusion", journal)
