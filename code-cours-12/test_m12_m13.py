import pytest
from pydantic import BaseModel
from outils import Outil
from agent import lancer_agent, ArretAgent
from crew import relire_tests, equipe_de_tests

class Faux:
    def __init__(self, *reps): self.reps = list(reps); self.n = 0
    def chat(self, messages, *, temperature=0.2):
        r = self.reps[min(self.n, len(self.reps) - 1)]; self.n += 1; return r

class A(BaseModel): x: int
def doubler(a): return a.x * 2
def casse(a): raise RuntimeError("panne")
OUT = {"doubler": Outil("doubler", "double", A, doubler), "casse": Outil("casse", "échoue", A, casse),
       "ecrire": Outil("ecrire", "écrit", A, lambda a: "écrit", ecriture=True)}

def test_agent_atteint_son_objectif():
    r = lancer_agent(Faux('{"outil":"doubler","arguments":{"x":4}}', '{"reponse":"8"}'), OUT, "double 4")
    assert r["resultat"] == "8" and r["etapes"] == 2 and r["journal"][0]["resultat"] == "8"

def test_agent_stoppe_sur_boucle():
    with pytest.raises(ArretAgent) as e:
        lancer_agent(Faux('{"outil":"doubler","arguments":{"x":4}}'), OUT, "o", max_etapes=10)
    assert "boucle" in e.value.raison

def test_agent_stoppe_apres_max_etapes():
    reps = [f'{{"outil":"doubler","arguments":{{"x":{i}}}}}' for i in range(10)]
    with pytest.raises(ArretAgent) as e:
        lancer_agent(Faux(*reps), OUT, "o", max_etapes=3)
    assert "3 étapes" in e.value.raison and len(e.value.journal) == 3

def test_erreur_outil_n_arrete_pas_l_agent():
    r = lancer_agent(Faux('{"outil":"casse","arguments":{"x":1}}', '{"reponse":"ok"}'), OUT, "o")
    assert "ERREUR outil" in r["journal"][0]["resultat"]

def test_ecriture_non_approuvee():
    r = lancer_agent(Faux('{"outil":"ecrire","arguments":{"x":1}}', '{"reponse":"ok"}'), OUT, "o")
    assert "REFUSÉ" in r["journal"][0]["resultat"]

def test_relecteur_statique():
    assert relire_tests("def test_a():\n    pass") == ["test_a : aucun assert"]
    assert "assert toujours vrai" in relire_tests("def test_a():\n    assert True")[0]
    assert "sleep" in relire_tests("import time\ndef test_a():\n    time.sleep(1)\n    assert 1 == 1 + 0 or True")[0]
    assert relire_tests("def test_a():\n    assert 2 + 2 == 4") == []
    assert "syntaxe" in relire_tests("def (")[0]

def test_equipe_corrige_apres_relecture():
    mauvais = "```python\ndef test_a():\n    pass\n```"
    bon = "```python\ndef test_a():\n    assert 1 + 1 == 2\n```"
    r = equipe_de_tests(Faux("plan", mauvais, bon), "story")
    assert r["valide"] and r["tours"] == 2 and r["historique"][0]["problemes"]

def test_equipe_abandonne_si_toujours_mauvais():
    r = equipe_de_tests(Faux("plan", "```python\ndef test_a():\n    pass\n```"), "story", max_tours=2)
    assert not r["valide"] and r["tours"] == 2
