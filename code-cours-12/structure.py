"""Sortie structurée générique : n'importe quel schéma Pydantic, avec réessai."""
import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def extraire_json(texte: str) -> str:
    debut, fin = texte.find("{"), texte.rfind("}")
    return texte[debut : fin + 1] if debut != -1 and fin > debut else texte


def sortie_structuree(client, schema: type[T], systeme: str, donnee: str,
                      *, max_essais: int = 3) -> T:
    messages = [{"role": "system", "content": systeme},
                {"role": "user", "content": f"<donnee>{donnee}</donnee>"}]
    derniere = None
    for _ in range(max_essais):
        texte = client.chat(messages, temperature=0.0)
        try:
            return schema.model_validate_json(extraire_json(texte))
        except (ValidationError, json.JSONDecodeError) as e:
            derniere = e
            messages += [{"role": "assistant", "content": texte},
                         {"role": "user", "content": f"Réponse invalide ({e.__class__.__name__}). "
                                                     "Renvoie uniquement le JSON corrigé."}]
    raise ValueError(f"sortie invalide après {max_essais} essais") from derniere
