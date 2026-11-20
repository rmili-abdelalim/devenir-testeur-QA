"""Couche d'accès aux modèles : une interface, deux implémentations."""
import json
import logging
import random
import time
from typing import Iterator, Protocol

import httpx

log = logging.getLogger("llm")
STATUTS_A_REJOUER = (429, 500, 502, 503, 504)


class ErreurLLM(Exception):
    """Le modèle n'a pas répondu correctement après les essais autorisés."""


class BudgetEpuise(ErreurLLM):
    """Le plafond de tokens fixé a été atteint."""


class Budget:
    def __init__(self, max_tokens: int):
        self.max_tokens, self.utilises = max_tokens, 0

    def depenser(self, tokens: int) -> None:
        self.utilises += tokens
        if self.utilises > self.max_tokens:
            raise BudgetEpuise(f"{self.utilises} tokens utilisés, plafond {self.max_tokens}")


class LLMClient(Protocol):
    def chat(self, messages: list[dict], *, temperature: float = 0.2) -> str: ...


def post_avec_retry(url, corps, *, headers=None, essais=4, attente_base=0.5,
                    dormir=time.sleep, timeout=120):
    """POST qui respecte Retry-After sur 429 et ré-essaie les 5xx (jamais à l'infini)."""
    derniere = None
    for essai in range(1, essais + 1):
        try:
            r = httpx.post(url, json=corps, headers=headers, timeout=timeout)
        except httpx.TransportError as e:            # réseau coupé, timeout…
            derniere = e
        else:
            if r.status_code not in STATUTS_A_REJOUER:
                r.raise_for_status()
                return r
            derniere = r
        if essai == essais:
            break
        ra = derniere.headers.get("Retry-After") if isinstance(derniere, httpx.Response) else None
        attente = int(ra) if ra and ra.isdigit() else attente_base * 2 ** (essai - 1) + random.uniform(0, 0.2)
        log.warning("essai %s/%s échoué, pause %.1f s", essai, essais, attente)
        dormir(attente)
    raise ErreurLLM(f"échec après {essais} essais : {derniere!r}")


class OllamaClient:
    def __init__(self, modele="llama3.2", url="http://localhost:11434",
                 budget: Budget | None = None, dormir=time.sleep):
        self.modele, self.url, self.budget, self.dormir = modele, url, budget, dormir

    def _corps(self, messages, temperature, stream):
        return {"model": self.modele, "messages": messages, "stream": stream,
                "options": {"temperature": temperature}}

    def chat(self, messages, *, temperature=0.2) -> str:
        debut = time.perf_counter()
        r = post_avec_retry(f"{self.url}/api/chat", self._corps(messages, temperature, False),
                            dormir=self.dormir)
        d = r.json()
        tokens = (d.get("prompt_eval_count") or 0) + (d.get("eval_count") or 0)
        log.info("modele=%s tokens=%s duree=%.2fs", self.modele, tokens, time.perf_counter() - debut)
        if self.budget:
            self.budget.depenser(tokens)
        return d["message"]["content"]

    def stream(self, messages, *, temperature=0.2) -> Iterator[str]:
        """Renvoie la réponse morceau par morceau (une ligne JSON par morceau)."""
        with httpx.stream("POST", f"{self.url}/api/chat", timeout=120,
                          json=self._corps(messages, temperature, True)) as r:
            r.raise_for_status()
            for ligne in r.iter_lines():
                if not ligne:
                    continue
                morceau = json.loads(ligne)
                if morceau.get("done"):
                    break
                yield morceau["message"]["content"]


class OpenAICompatibleClient:
    """Format « chat/completions », proposé par de nombreux fournisseurs (et par Ollama sous /v1)."""

    def __init__(self, base_url, cle_api, modele, budget: Budget | None = None, dormir=time.sleep):
        self.base_url, self.cle_api, self.modele = base_url.rstrip("/"), cle_api, modele
        self.budget, self.dormir = budget, dormir

    def chat(self, messages, *, temperature=0.2) -> str:
        r = post_avec_retry(
            f"{self.base_url}/chat/completions",
            {"model": self.modele, "messages": messages, "temperature": temperature},
            headers={"Authorization": f"Bearer {self.cle_api}"}, dormir=self.dormir)
        d = r.json()
        if self.budget:
            self.budget.depenser(d.get("usage", {}).get("total_tokens", 0))
        return d["choices"][0]["message"]["content"]
