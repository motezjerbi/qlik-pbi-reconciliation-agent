import re
from pathlib import Path
try:
    from taxonomy import TAXONOMY_PATTERNS
except ImportError:
    from module_b.taxonomy import TAXONOMY_PATTERNS

def parse_qlik_script(filepath: str) -> list[dict]:
    content = Path(filepath).read_text(encoding="utf-8")
    # Ignore le bloc "Main" auto-généré (réglages régionaux, pas du vrai code métier)
    if "///$tab Variables" in content:
        content = content.split("///$tab Variables", 1)[1]
    elif "///$tab Main" in content:
        # fallback si pas de section Variables : on saute juste après Main
        parts = content.split("///$tab")
        content = "///$tab".join(parts[2:]) if len(parts) > 2 else content
    findings = []
    for pattern_name, regex in TAXONOMY_PATTERNS.items():
        matches = re.finditer(regex, content, re.IGNORECASE)
        for match in matches:
            findings.append({
                "pattern": pattern_name,
                "expression_source": match.group(0),
                "position": match.start()
            })
    return findings


if __name__ == "__main__":
    results = parse_qlik_script("data/samples/case_encadrante_01/qlik/load_script.qvs")

    print(f"{len(results)} pattern(s) détecté(s) :\n")
    for r in results:
        print(f"- {r['pattern']} → '{r['expression_source']}'")