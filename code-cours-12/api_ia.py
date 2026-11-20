"""API FastAPI qui expose l'assistant (module 18)."""
import hmac
import os
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from llm import OllamaClient


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class LimiteurDebit:
    """Fenêtre glissante en mémoire : n appels par minute et par clé (suffisant pour 1 instance)."""
    def __init__(self, max_par_minute: int = 20, horloge=time.monotonic):
        self.max, self.horloge, self.appels = max_par_minute, horloge, defaultdict(deque)

    def verifier(self, cle: str) -> None:
        maintenant, file = self.horloge(), self.appels[cle]
        while file and maintenant - file[0] > 60:
            file.popleft()
        if len(file) >= self.max:
            raise HTTPException(429, "trop de requêtes", headers={"Retry-After": "60"})
        file.append(maintenant)


def get_client():
    return OllamaClient(modele=os.environ.get("MODELE", "llama3.2"), url=os.environ.get("OLLAMA_URL", "http://localhost:11434"))


def get_limiteur(_cache={}):
    return _cache.setdefault("l", LimiteurDebit(int(os.environ.get("LIMITE_PAR_MIN", "20"))))


def verifier_cle(x_api_key: str = Header(default="")) -> str:
    attendue = os.environ.get("API_KEY", "")
    if not attendue or not hmac.compare_digest(x_api_key.encode(), attendue.encode()):
        raise HTTPException(401, "clé API invalide")
    return x_api_key


def creer_app() -> FastAPI:
    app = FastAPI(title="NovaQA Copilot")

    @app.get("/health")
    def health():
        return {"statut": "ok"}

    @app.post("/chat")
    def chat(q: Question, cle: str = Depends(verifier_cle), client=Depends(get_client), lim=Depends(get_limiteur)):
        lim.verifier(cle)
        try:
            texte = client.chat([{"role": "user", "content": q.question}])
        except Exception:
            raise HTTPException(503, "modèle indisponible")     # message générique : pas de détail interne
        return {"reponse": texte}

    @app.post("/chat/flux")
    def flux(q: Question, cle: str = Depends(verifier_cle), client=Depends(get_client), lim=Depends(get_limiteur)):
        lim.verifier(cle)
        def evenements():
            for morceau in client.stream([{"role": "user", "content": q.question}]):
                yield f"data: {morceau}\n\n"
            yield "data: [FIN]\n\n"
        return StreamingResponse(evenements(), media_type="text/event-stream")

    return app


app = creer_app()
