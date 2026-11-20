import time

import httpx

URL = "http://localhost:11434/api/chat"
MODELE = "llama3.2"          # adapte avec le nom affiché par `ollama list`


def demander(question: str, temperature: float = 0.8) -> dict:
    corps = {
        "model": MODELE,
        "messages": [{"role": "user", "content": question}],
        "stream": False,
        "options": {"temperature": temperature},
    }
    debut = time.perf_counter()
    reponse = httpx.post(URL, json=corps, timeout=120)
    reponse.raise_for_status()
    donnees = reponse.json()
    return {
        "texte": donnees["message"]["content"],
        "tokens_entree": donnees.get("prompt_eval_count"),
        "tokens_sortie": donnees.get("eval_count"),
        "duree_s": round(time.perf_counter() - debut, 2),
    }


if __name__ == "__main__":
    for _ in range(3):
        r = demander("Explique en une phrase ce qu'est un test de non-régression.")
        print(f'{r["duree_s"]} s | {r["tokens_entree"]} → {r["tokens_sortie"]} tokens')
        print(r["texte"], "\n")
