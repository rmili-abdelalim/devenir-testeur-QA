import json, threading, http.server
import pytest
import premier_contact, variabilite as var
from extraction import demander_cas_de_test, extraire_json

class H(http.server.BaseHTTPRequestHandler):
    n = 0
    def do_POST(self):
        H.n += 1
        corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert corps["stream"] is False and "temperature" in corps["options"]
        rep = {"message": {"content": "391" if H.n % 4 else "390"}, "prompt_eval_count": 20, "eval_count": 3}
        d = json.dumps(rep).encode(); self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
    def log_message(self, *a): pass

@pytest.fixture(scope="module", autouse=True)
def serveur():
    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    premier_contact.URL = f"http://127.0.0.1:{s.server_port}/api/chat"
    yield; s.shutdown()

def test_demander():
    r = premier_contact.demander("x", 0.0)
    assert r["texte"] == "391" and r["tokens_entree"] == 20 and r["tokens_sortie"] == 3 and r["duree_s"] >= 0

def test_variabilite():
    n, top = var.variabilite("q", n=8)
    assert n == 2 and sum(c for _, c in top) == 8

VALIDE = '```json\n{"id":"TC-CONN-021","titre":"Mot de passe trop court","priorite":"haute","etapes":["Saisir 7 caractères"],"resultat_attendu":"Message d\'erreur"}\n```'

def test_extraire_json():
    assert json.loads(extraire_json("Voici :\n" + VALIDE + "\nBonne journée"))["id"] == "TC-CONN-021"

def test_reessaie_puis_reussit():
    reponses = iter(["Je ne peux pas.", VALIDE]); appels = []
    def faux(messages):
        appels.append(len(messages)); return next(reponses)
    cas = demander_cas_de_test(faux, "En tant que client…")
    assert cas.priorite == "haute" and len(appels) == 2 and appels[1] > appels[0]

def test_abandon():
    appels = []
    def faux(m): appels.append(1); return "{}"
    with pytest.raises(ValueError):
        demander_cas_de_test(faux, "x", max_essais=2)
    assert len(appels) == 2

def test_reessai_message_erreur():
    reponses = iter(["pas du json", VALIDE])
    dernier_message = []

    def faux_modele(messages):
        dernier_message.append(messages[-1]["content"])
        return next(reponses)

    cas = demander_cas_de_test(faux_modele, "En tant que client, je veux me connecter.")

    assert cas.id == "TC-CONN-021"
    assert len(dernier_message) == 2
    assert "invalide" in dernier_message[1]

def test_adaptateur_ollama():
    import extraction
    extraction_url = premier_contact.URL
    texte = extraction.demander_ollama([{"role": "user", "content": "x"}], url=extraction_url)
    assert texte == "391" or texte == "390"
