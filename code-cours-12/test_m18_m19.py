import json, pytest
from fastapi.testclient import TestClient
import api_ia
from api_ia import creer_app, get_client, get_limiteur, LimiteurDebit
from tracing import Traceur, resume, percentile, porte_regression

class Faux:
    def chat(self, m, *, temperature=0.2): return "pong"
    def stream(self, m, *, temperature=0.2): yield from ["Bon", "jour"]
class Casse:
    def chat(self, m, *, temperature=0.2): raise RuntimeError("secret interne")

@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv("API_KEY", "bonne-cle")
    app = creer_app(); app.dependency_overrides[get_client] = lambda: Faux()
    lim = LimiteurDebit(2); app.dependency_overrides[get_limiteur] = lambda: lim
    return TestClient(app), app

H = {"X-API-Key": "bonne-cle"}
def test_health_sans_cle(c): assert c[0].get("/health").json() == {"statut": "ok"}
def test_401(c):
    assert c[0].post("/chat", json={"question": "a"}).status_code == 401
    assert c[0].post("/chat", json={"question": "a"}, headers={"X-API-Key": "x"}).status_code == 401
def test_chat_ok_et_validation(c):
    assert c[0].post("/chat", json={"question": "a"}, headers=H).json() == {"reponse": "pong"}
    assert c[0].post("/chat", json={"question": ""}, headers=H).status_code == 422
def test_429_apres_limite(c):
    for _ in range(2): assert c[0].post("/chat", json={"question": "a"}, headers=H).status_code == 200
    r = c[0].post("/chat", json={"question": "a"}, headers=H)
    assert r.status_code == 429 and r.headers["Retry-After"] == "60"
def test_503_sans_fuite_de_detail(c):
    c[1].dependency_overrides[get_client] = lambda: Casse()
    r = c[0].post("/chat", json={"question": "a"}, headers=H)
    assert r.status_code == 503 and "secret" not in r.text
def test_flux(c):
    r = c[0].post("/chat/flux", json={"question": "a"}, headers=H)
    assert r.headers["content-type"].startswith("text/event-stream") and "data: Bon" in r.text and "[FIN]" in r.text
def test_limiteur_fenetre_glissante():
    t = [0.0]; l = LimiteurDebit(1, horloge=lambda: t[0]); l.verifier("k")
    with pytest.raises(Exception): l.verifier("k")
    t[0] = 61; l.verifier("k")

def test_traces_et_resume(tmp_path):
    f = tmp_path / "t.jsonl"; tr = Traceur(f)
    for _ in range(3): tr.appeler(Faux(), [{"role": "user", "content": "bonjour"}])
    with pytest.raises(RuntimeError): tr.appeler(Casse(), [{"role": "user", "content": "x"}])
    r = resume(f); assert r["appels"] == 4 and r["taux_erreur"] == 0.25
    assert "bonjour" not in f.read_text()           # aucun contenu stocké
def test_percentile_et_regression():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10 and percentile([5], 50) == 5
    assert porte_regression({"hit": 0.7}, {"hit": 0.9}) == ["hit : 0.90 → 0.70"]
    assert porte_regression({"hit": 0.88}, {"hit": 0.9}) == []
