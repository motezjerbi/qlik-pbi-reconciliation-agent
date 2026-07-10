import re
from pathlib import Path


def extract_dax_measures(doc_path: str) -> list[dict]:
    """
    Extrait les mesures DAX depuis le tableau markdown 'Annexe sémantique'
    généré automatiquement dans la documentation Power BI.
    """
    content = Path(doc_path).read_text(encoding="utf-8")

    # On cible uniquement les lignes du tableau markdown qui concernent le dossier "Mesure\General"
    measures = []
    for line in content.splitlines():
        if line.startswith("| Mesure") and "|" in line:
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 7:
                measures.append({
                    "dossier": cols[0],
                    "nom": cols[1],
                    "format": cols[2],
                    "visible": cols[3],
                    "table_source": cols[4],
                    "colonne_source": cols[5],
                    "formule_dax": cols[6].replace("<br>", "\n")
                })

    return measures


def save_measures_as_text(measures: list[dict], output_path: str):
    """Sauvegarde les mesures extraites dans un fichier texte lisible par le parser."""
    lines = []
    for m in measures:
        lines.append(f"# Mesure : {m['nom']}")
        lines.append(f"# Table source : {m['table_source']} | Colonne source : {m['colonne_source']}")
        lines.append(m["formule_dax"])
        lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    measures = extract_dax_measures("data/samples/case_encadrante_01/powerbi/documentation.md")

    print(f"{len(measures)} mesure(s) DAX extraite(s) :\n")
    for m in measures:
        print(f"- {m['nom']} → {m['formule_dax'][:60]}...")

    save_measures_as_text(measures, "data/samples/case_encadrante_01/powerbi/measures_dax.txt")
    print(f"\nSauvegardé dans measures_dax.txt")