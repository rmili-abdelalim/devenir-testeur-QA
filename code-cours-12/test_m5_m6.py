import json, pathlib, pytest
from qa_ai import anonymiser, trier, main, Triage
from filtre_spec import CasApi, filtrer_cas, generer_fichier_tests, endpoints_de_la_spec

class Faux:
    def __init__(self, *reps): self.reps = list(reps); self.appels = []
    def chat(self, messages, *, temperature=0.2):
        self.appels.append(messages); return self.reps.pop(0)

def test_anonymiser():
    t = anonymiser("user bob@exemple.fr depuis 10.0.0.12 token abcdefghijklmnopqrstuvwxyz123456")
    assert "bob@" not in t and "10.0.0.12" not in t and "abcdefghij" not in t
    assert "<EMAIL>" in t and "<IP>" in t and "<SECRET>" in t

def test_trier_ne_envoie_pas_de_donnees_brutes():
    c = Faux('{"categorie":"infra","resume":"timeout réseau"}')
    r = trier(c, "échec pour bob@exemple.fr : ConnectionResetError")
    assert r.categorie == "infra"
    assert "bob@exemple.fr" not in json.dumps(c.appels[0])

def test_categorie_inconnue_declenche_reessai():
    c = Faux('{"categorie":"magie","resume":"x"}', '{"categorie":"test","resume":"sélecteur"}')
    assert trier(c, "log").categorie == "test" and len(c.appels) == 2

def test_cli_dry_run_n_appelle_pas_le_modele(tmp_path, capsys):
    (tmp_path / "a.log").write_text("erreur pour bob@exemple.fr", encoding="utf-8")
    c = Faux()
    assert main(["triage", str(tmp_path), "--dry-run"], client=c) == 0
    sortie = capsys.readouterr().out
    assert "<EMAIL>" in sortie and "bob@" not in sortie and c.appels == []

SPEC = {"paths": {"/users": {"get": {}, "post": {}}, "/users/{id}": {"get": {}, "delete": {}}}}

def test_filtre_rejette_endpoint_invente():
    cas = [CasApi(methode="GET", chemin="/users", statut_attendu=200, description="liste"),
           CasApi(methode="GET", chemin="/users/42", statut_attendu=200, description="un user"),
           CasApi(methode="PUT", chemin="/users/42", statut_attendu=200, description="inventé"),
           CasApi(methode="GET", chemin="/admin", statut_attendu=200, description="inventé")]
    gardes, rejetes = filtrer_cas(cas, SPEC)
    assert [c.chemin for c in gardes] == ["/users", "/users/42"]
    assert [c.description for c in rejetes] == ["inventé", "inventé"]

def test_fichier_genere_compile():
    code = generer_fichier_tests([CasApi(methode="get", chemin="/users", statut_attendu=200, description="liste")])
    compile(code, "test_genere.py", "exec"); assert "parametrize" in code and "BASE_URL" in code
