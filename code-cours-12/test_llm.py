import json, threading, http.server
import pytest
from llm import OllamaClient, OpenAICompatibleClient, Budget, BudgetEpuise, ErreurLLM

def serveur(scenario):
    """scenario : liste de (statut, en-têtes, corps) joués dans l'ordre, puis le dernier se répète."""
    vus = []
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["Content-Length"]); vus.append((self.path, json.loads(self.rfile.read(n)), dict(self.headers)))
            st, hd, corps = scenario[min(len(vus) - 1, len(scenario) - 1)]
            data = corps if isinstance(corps, bytes) else json.dumps(corps).encode()
            self.send_response(st)
            for k, v in hd.items(): self.send_header(k, v)
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        def log_message(self, *a): pass
    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, vus

OK = (200, {}, {"message": {"content": "salut"}, "prompt_eval_count": 10, "eval_count": 5})

def test_429_respecte_retry_after_puis_ok():
    s, vus = serveur([(429, {"Retry-After": "2"}, {}), OK]); pauses = []
    c = OllamaClient(url=f"http://127.0.0.1:{s.server_port}", dormir=pauses.append)
    assert c.chat([{"role": "user", "content": "x"}]) == "salut"
    assert pauses == [2] and len(vus) == 2

def test_abandon_apres_essais():
    s, vus = serveur([(500, {}, {})]); pauses = []
    c = OllamaClient(url=f"http://127.0.0.1:{s.server_port}", dormir=pauses.append)
    with pytest.raises(ErreurLLM):
        c.chat([{"role": "user", "content": "x"}])
    assert len(vus) == 4 and len(pauses) == 3

def test_401_sans_retry():
    s, vus = serveur([(401, {}, {})])
    c = OpenAICompatibleClient(f"http://127.0.0.1:{s.server_port}", "k", "m")
    with pytest.raises(Exception):
        c.chat([{"role": "user", "content": "x"}])
    assert len(vus) == 1

def test_budget():
    s, _ = serveur([OK])
    c = OllamaClient(url=f"http://127.0.0.1:{s.server_port}", budget=Budget(20))
    c.chat([{"role": "user", "content": "x"}])        # 15 tokens
    with pytest.raises(BudgetEpuise):
        c.chat([{"role": "user", "content": "x"}])     # 30 > 20

def test_openai_compatible_format_et_en_tete():
    rep = (200, {}, {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 7}})
    s, vus = serveur([rep])
    c = OpenAICompatibleClient(f"http://127.0.0.1:{s.server_port}/v1", "SECRET", "m", budget=Budget(100))
    assert c.chat([{"role": "user", "content": "x"}]) == "ok"
    chemin, corps, en_tetes = vus[0]
    assert chemin == "/v1/chat/completions" and en_tetes["Authorization"] == "Bearer SECRET"

def test_stream():
    lignes = b'{"message":{"content":"Bon"},"done":false}\n{"message":{"content":"jour"},"done":false}\n{"done":true}\n'
    s, _ = serveur([(200, {}, lignes)])
    c = OllamaClient(url=f"http://127.0.0.1:{s.server_port}")
    assert "".join(c.stream([{"role": "user", "content": "x"}])) == "Bonjour"
