"""Plusieurs rôles, un contrôle déterministe : générateur de tests + relecteur (module 13)."""
import ast


def relire_tests(code: str) -> list[str]:
    """Relecteur STATIQUE (pas de modèle) : repère les tests qui ne prouvent rien."""
    try:
        arbre = ast.parse(code)
    except SyntaxError as e:
        return [f"syntaxe invalide ligne {e.lineno}"]
    problemes = []
    for fn in [n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]:
        asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        if not asserts:
            problemes.append(f"{fn.name} : aucun assert")
        for a in asserts:
            if isinstance(a.test, ast.Constant) and a.test.value:
                problemes.append(f"{fn.name} : assert toujours vrai")
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) == "sleep":
                problemes.append(f"{fn.name} : sleep interdit")
    return problemes


def extraire_code(texte: str) -> str:
    if "```" in texte:
        bloc = texte.split("```")[1]
        return bloc.split("\n", 1)[1] if bloc.startswith("python") else bloc
    return texte


def equipe_de_tests(client, user_story: str, *, max_tours: int = 3) -> dict:
    """Planificateur → générateur → relecteur ; on s'arrête au premier code propre ou après max_tours."""
    plan = client.chat([{"role": "system", "content": "Liste en 5 lignes max les cas de test pytest à écrire."},
                        {"role": "user", "content": user_story}])
    messages = [{"role": "system", "content": "Écris un fichier pytest (un bloc ```python). Chaque test doit contenir un assert utile."},
                {"role": "user", "content": f"Story : {user_story}\nPlan :\n{plan}"}]
    historique = []
    for tour in range(1, max_tours + 1):
        brut = client.chat(messages)
        code = extraire_code(brut)
        problemes = relire_tests(code)
        historique.append({"tour": tour, "problemes": problemes})
        if not problemes:
            return {"code": code, "tours": tour, "valide": True, "historique": historique}
        messages += [{"role": "assistant", "content": brut},
                     {"role": "user", "content": "Relecture : " + " ; ".join(problemes) + ". Corrige."}]
    return {"code": code, "tours": max_tours, "valide": False, "historique": historique}
