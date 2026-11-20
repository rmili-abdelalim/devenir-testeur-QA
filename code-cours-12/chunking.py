"""Découpage de documents en morceaux (module 10)."""


def decouper(texte: str, taille: int = 400, chevauchement: int = 60) -> list[str]:
    """Morceaux d'environ `taille` caractères, coupés à une fin de phrase ou de ligne quand c'est possible."""
    if chevauchement >= taille:
        raise ValueError("le chevauchement doit être plus petit que la taille")
    texte, morceaux, debut = texte.strip(), [], 0
    while debut < len(texte):
        fin = min(debut + taille, len(texte))
        if fin < len(texte):
            coupe = max(texte.rfind(". ", debut, fin), texte.rfind("\n", debut, fin))
            if coupe > debut + taille // 2:
                fin = coupe + 1
        morceaux.append(texte[debut:fin].strip())
        if fin == len(texte):
            break
        debut = max(fin - chevauchement, debut + 1)
    return [m for m in morceaux if m]


def indexer_documents(base, documents: dict[str, str], **options) -> int:
    n = 0
    for source, texte in documents.items():
        morceaux = decouper(texte, **options)
        base.ajouter(morceaux, [{"source": source, "morceau": i} for i in range(len(morceaux))])
        n += len(morceaux)
    return n
