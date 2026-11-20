from collections import Counter

from premier_contact import demander


def variabilite(question: str, n: int = 20, temperature: float = 0.8):
    """Pose la même question n fois ; renvoie (nb de réponses distinctes, les 3 plus fréquentes)."""
    reponses = [demander(question, temperature)["texte"].strip().lower() for _ in range(n)]
    compte = Counter(reponses)
    return len(compte), compte.most_common(3)


if __name__ == "__main__":
    q = "Combien font 17 x 23 ? Réponds uniquement par le nombre."
    distinctes, top = variabilite(q)
    print(f"{distinctes} réponse(s) distincte(s) sur 20")
    for texte, nb in top:
        print(f"  {nb:>2} × {texte!r}")
