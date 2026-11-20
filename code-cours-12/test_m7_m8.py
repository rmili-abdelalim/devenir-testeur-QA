import json, sqlite3, pytest
from pydantic import BaseModel, Field
from outils import Outil, boucle_outils, sql_lecture_seule, LimiteEtapes, catalogue
from assistant import AssistantQA, tronquer_historique

class Faux:
    def __init__(self, *reps): self.reps = list(reps); self.appels = []
    def chat(self, messages, *, temperature=0.2):
        self.appels.append([dict(m) for m in messages]); return self.reps.pop(0) if len(self.reps) > 1 else self.reps[0]

class Cherche(BaseModel): mot_cle: str = Field(min_length=2)
class Brouillon(BaseModel): titre: str

CASES = ["TC-CONN-001 mot de passe trop court", "TC-PANIER-004 code promo"]
def chercher(a): return [c for c in CASES if a.mot_cle in c]
ecrits = []
OUTILS = {"chercher_cas": Outil("chercher_cas", "Cherche des cas de test.", Cherche, chercher),
          "brouillon": Outil("brouillon", "Crée un brouillon.", Brouillon, lambda a: ecrits.append(a.titre) or "ok", ecriture=True)}

def test_appel_outil_puis_reponse_et_journal():
    c = Faux('{"outil":"chercher_cas","arguments":{"mot_cle":"promo"}}', '{"reponse":"Voir TC-PANIER-004 (outil chercher_cas)."}')
    j = []
    assert "TC-PANIER-004" in boucle_outils(c, OUTILS, "cas promo ?", journal=j)
    assert j[0]["outil"] == "chercher_cas" and "TC-PANIER-004" in j[0]["resultat"]
    assert "<resultat" in c.appels[1][-1]["content"]

def test_arguments_invalides_renvoyes_au_modele():
    c = Faux('{"outil":"chercher_cas","arguments":{"mot_cle":"x"}}', '{"reponse":"ok"}')
    boucle_outils(c, OUTILS, "q")
    assert "ERREUR arguments invalides" in c.appels[1][-1]["content"]

def test_ecriture_refusee_sans_confirmation():
    ecrits.clear()
    c = Faux('{"outil":"brouillon","arguments":{"titre":"T"}}', '{"reponse":"fait"}')
    boucle_outils(c, OUTILS, "crée", confirmer=lambda n, a: False)
    assert ecrits == [] and "REFUSÉ" in c.appels[1][-1]["content"]
    c2 = Faux('{"outil":"brouillon","arguments":{"titre":"T"}}', '{"reponse":"fait"}')
    boucle_outils(c2, OUTILS, "crée", confirmer=lambda n, a: True)
    assert ecrits == ["T"]

def test_limite_etapes():
    c = Faux('{"outil":"chercher_cas","arguments":{"mot_cle":"promo"}}')
    with pytest.raises(LimiteEtapes):
        boucle_outils(c, OUTILS, "q", max_etapes=3)
    assert len(c.appels) == 3

def test_sql_lecture_seule(tmp_path):
    base = str(tmp_path / "t.db"); cx = sqlite3.connect(base)
    cx.execute("create table cas(id text)"); cx.execute("insert into cas values ('TC-1')"); cx.commit(); cx.close()
    assert sql_lecture_seule(base, "SELECT id FROM cas") == [("TC-1",)]
    for mauvaise in ["DELETE FROM cas", "SELECT 1; DROP TABLE cas", "  update cas set id='x'"]:
        with pytest.raises(PermissionError):
            sql_lecture_seule(base, mauvaise)

def test_catalogue_mentionne_outils_et_arguments():
    t = catalogue(OUTILS); assert "chercher_cas" in t and "mot_cle" in t

def test_assistant_memoire_et_troncature():
    c = Faux('{"reponse":"R1"}', '{"reponse":"R2"}')
    a = AssistantQA(c, OUTILS, max_messages=2)
    a.poser("Q1"); a.poser("Q2")
    assert any(m["content"] == "Q1" for m in c.appels[1])          # la mémoire passe
    a.poser("Q3")                                                 # historique tronqué à 2 messages
    assert not any(m["content"] == "Q1" for m in c.appels[1 + 1])
    assert tronquer_historique(list(range(5)), 2) == [3, 4]
