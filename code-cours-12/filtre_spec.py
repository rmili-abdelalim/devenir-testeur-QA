"""Garde-fou anti-hallucination pour des tests d'API générés (module 6)."""
import re

from pydantic import BaseModel


class CasApi(BaseModel):
    methode: str
    chemin: str
    statut_attendu: int
    description: str


def endpoints_de_la_spec(spec: dict) -> set[tuple[str, str]]:
    """Couples (MÉTHODE, chemin) réellement déclarés dans un document OpenAPI."""
    methodes = {"get", "post", "put", "patch", "delete"}
    return {(m.upper(), chemin) for chemin, ops in spec.get("paths", {}).items()
            for m in ops if m.lower() in methodes}


def _gabarit(chemin: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", chemin)


def filtrer_cas(cas: list[CasApi], spec: dict):
    """Sépare les cas valides des cas qui visent un endpoint absent de la spec."""
    connus = {(m, _gabarit(c)) for m, c in endpoints_de_la_spec(spec)}
    gardes, rejetes = [], []
    for c in cas:
        vise = (c.methode.upper(), _gabarit(re.sub(r"/\d+(?=/|$)", "/{}", c.chemin)))
        (gardes if vise in connus else rejetes).append(c)
    return gardes, rejetes


def generer_fichier_tests(cas: list[CasApi], base_url_var: str = "BASE_URL") -> str:
    lignes = ["import os", "import httpx", "import pytest", "",
              f'BASE = os.environ.get("{base_url_var}", "http://localhost:8000")', "",
              "CAS = ["]
    for c in cas:
        lignes.append(f"    ({c.methode.upper()!r}, {c.chemin!r}, {c.statut_attendu}, {c.description!r}),")
    lignes += ["]", "", '@pytest.mark.parametrize("methode,chemin,statut,description", CAS)',
               "def test_cas_api(methode, chemin, statut, description):",
               "    reponse = httpx.request(methode, BASE + chemin, timeout=5)",
               "    assert reponse.status_code == statut, description", ""]
    return "\n".join(lignes)
