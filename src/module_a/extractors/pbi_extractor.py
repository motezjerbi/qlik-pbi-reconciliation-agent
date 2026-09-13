# src/module_a/extractors/pbi_extractor.py
"""
Extracteur Power BI - Module A (Data Reconciliation)

Support principal : extraction LIVE via ADOMD.NET (pbi_engine_client.py)
   -> nécessite Power BI Desktop ouvert avec le .pbix chargé
   -> donne les VRAIES valeurs des mesures (comme qlik_extractor.py côté Qlik)

Fallback : extraction structurelle via ZIP (sans valeurs réelles, structure seule)
Autres formats : .pbit / .pbip / .pdf / .json / .xlsx / .csv

Usage test :
  python src/module_a/extractors/pbi_extractor.py <chemin_fichier.pbix>
"""

import re
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
import zipfile

# Import du client Engine (fonctionne en package et en script direct),
# même logique que qlik_extractor.py / qlik_engine_client.py
try:
    from .pbi_engine_client import extract_app_structure as extract_pbi_live
except ImportError:
    try:
        from pbi_engine_client import extract_app_structure as extract_pbi_live
    except ImportError:
        extract_pbi_live = None


class PBIExtractor:
    """Extrait la structure et les données d'un rapport Power BI pour la réconciliation Module A."""

    def __init__(self):
        self.kpis = []
        self.visuals = []
        self.tables = []
        self.measures = []
        self.dax_measures = []
        self.pages = []
        self.columns = []
        self.tables_data = {}

    def extract_from_file(self, filepath: str) -> Dict:
        """Point d'entrée : extraction du fichier .pbix (ou autres formats supportés)."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Fichier introuvable : {filepath}")

        suffix = filepath.suffix.lower()

        if suffix == ".pbix":
            return self._extract_pbix_dispatch(filepath)
        if suffix == ".pbit":
            return self._extract_from_pbit(filepath)
        if suffix in (".pbip", ".pbi"):
            return self._extract_from_pbip(filepath)
        if suffix == ".pdf":
            return self._extract_from_pdf(filepath)
        if suffix in (".json", ".txt"):
            return self._extract_from_json(filepath)
        if suffix in (".xlsx", ".xls", ".csv"):
            return self._extract_from_export(filepath)
        raise ValueError(f"Format non supporté: {filepath.suffix}")

    # ============================================================
    # DISPATCH .PBIX : LIVE (ADOMD) EN PRIORITÉ, ZIP EN SECOURS
    # ============================================================

    def _extract_pbix_dispatch(self, filepath: Path) -> Dict:
        """
        Combine deux sources, car aucune des deux seule n'a tout :
        - le moteur ADOMD.NET (vraies valeurs des mesures/KPIs, mais ignore
          totalement la mise en page du rapport : pages/visuels)
        - le ZIP (pages/visuels, mais aucune valeur réelle calculée)
        """
        zip_result = self._extract_from_pbix_zip(filepath)

        if extract_pbi_live is None:
            return zip_result

        try:
            print("🔌 Extraction live via le moteur Power BI (ADOMD.NET)...")
            print("   (Power BI Desktop doit être ouvert avec ce fichier chargé)")
            live_result = extract_pbi_live(str(filepath.resolve()))
            merged = self._normalize_live_result(live_result, filepath)
            # Le moteur ADOMD ne connaît pas la mise en page du rapport :
            # on complète avec les pages/visuels trouvés dans le ZIP.
            merged["pages"] = zip_result.get("pages", [])
            merged["visuals"] = zip_result.get("visuals", [])
            merged["metadata"]["pages_count"] = len(merged["pages"])
            merged["metadata"]["visuals_count"] = len(merged["visuals"])
            merged["metadata"]["source"] = "pbix_live_adomd_with_zip_pages"
            return merged
        except Exception as e:
            print(f"   ⚠️ Extraction live impossible : {e}")
            print("   ↩️ Repli complet sur l'extraction structurelle via ZIP (sans valeurs réelles)")
            return zip_result

    def _normalize_live_result(self, live_result: Dict, filepath: Path) -> Dict:
        """
        Adapte le format renvoyé par pbi_engine_client (tables/measures/kpis)
        au format attendu par le reste du pipeline (app.py, kpi_reconciliation.py).
        """
        result = {
            "tables": live_result.get("tables", []),
            "measures": live_result.get("measures", []),
            "dax_measures": live_result.get("measures", []),
            "dimensions": live_result.get("dimensions", []),
            "kpis": live_result.get("kpis", []),
            "pages": live_result.get("pages", []),
            "visuals": live_result.get("visuals", []),
            "columns": live_result.get("columns", []),
            "power_query": live_result.get("power_query", []),
            "roles": live_result.get("roles", []),
            "tables_data": live_result.get("tables_data", {}),
            "relationships": live_result.get("relationships", []),
            "calculated_columns": [],
            "metadata": {
                "source": "pbix_live_adomd",
                "file": str(filepath.name),
                "type": "Power BI Report (extraction live)",
            },
        }
        result["metadata"]["tables_count"] = len(result["tables"])
        result["metadata"]["dax_measures_count"] = len(result["dax_measures"])
        result["metadata"]["visuals_count"] = len(result["visuals"])
        result["metadata"]["kpis_count"] = len(result["kpis"])
        result["metadata"]["pages_count"] = len(result["pages"])
        result["metadata"]["columns_count"] = len(result["columns"])
        result["metadata"]["power_query_count"] = len(result["power_query"])
        result["metadata"]["tables_data_count"] = len(result["tables_data"])
        return result

    # ============================================================
    # EXTRACTION STRUCTURELLE (ZIP) — SECOURS SANS VALEURS RÉELLES
    # ============================================================

    def _extract_from_pbix_zip(self, filepath: Path) -> Dict:
        """Extraction structurelle via ZIP (repli si Power BI Desktop n'est pas ouvert)."""
        result = {
            "tables": [],
            "measures": [],
            "dimensions": [],
            "visuals": [],
            "kpis": [],
            "dax_measures": [],
            "relationships": [],
            "calculated_columns": [],
            "pages": [],
            "columns": [],
            "tables_data": {},
            "metadata": {
                "source": "pbix_zip_fallback",
                "file": str(filepath.name),
                "type": "Power BI Report (structure seule, sans valeurs)",
            },
        }

        try:
            with zipfile.ZipFile(filepath, "r") as zip_ref:
                all_files = zip_ref.namelist()

                result["pages"] = self._extract_pages_from_zip(zip_ref, all_files)
                page_id_to_name = {p.get("id", ""): p.get("name", "") for p in result["pages"]}

                visuals_data = self._extract_visuals_from_zip(zip_ref, all_files, page_id_to_name)
                result["visuals"] = visuals_data["visuals"]
                result["kpis"] = visuals_data["kpis"]

                result["dax_measures"] = self._extract_dax_measures_from_zip(zip_ref, all_files)
                result["measures"] = result["dax_measures"]
                result["tables"] = self._extract_tables_from_zip(zip_ref, all_files)
                result["columns"] = self._extract_columns_from_zip(zip_ref, all_files)
                result["dimensions"] = [{"name": c} for c in result["columns"][:30]]

                self._add_measure_kpis(result)

        except zipfile.BadZipFile:
            print("   ⚠️ Le fichier n'est pas un zip valide")
            result["metadata"]["error"] = "Bad zip file"
        except Exception as e:
            print(f"   ⚠️ Erreur extraction ZIP : {e}")
            result["metadata"]["error"] = str(e)

        result["metadata"]["tables_count"] = len(result.get("tables", []))
        result["metadata"]["dax_measures_count"] = len(result.get("dax_measures", []))
        result["metadata"]["visuals_count"] = len(result.get("visuals", []))
        result["metadata"]["kpis_count"] = len(result.get("kpis", []))
        result["metadata"]["pages_count"] = len(result.get("pages", []))
        result["metadata"]["columns_count"] = len(result.get("columns", []))
        result["metadata"]["tables_data_count"] = len(result.get("tables_data", {}))
        return result

    def _extract_pages_from_zip(self, zip_ref, all_files) -> List[Dict]:
        """Extrait les pages du rapport."""
        pages = []
        page_files = [
            f for f in all_files
            if "definition/pages/" in f.replace("\\", "/")
            and f.endswith("page.json")
        ]
        for page_file in page_files:
            try:
                with zip_ref.open(page_file) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                display_match = re.search(r'"displayName"\s*:\s*"([^"]*?)"', content)
                name_match = re.search(r'"name"\s*:\s*"([^"]*?)"', content)
                page_name = display_match.group(1) if display_match else (name_match.group(1) if name_match else "Page")
                page_id = Path(page_file).parent.name
                if page_name not in [p.get("name") for p in pages]:
                    pages.append({"name": page_name, "id": page_id})
            except Exception:
                pass

        if not pages:
            for cand in ("Report/Layout", "Layout"):
                if cand in all_files:
                    try:
                        with zip_ref.open(cand) as f:
                            layout = f.read().decode("utf-8", errors="ignore")
                        for match in re.finditer(r'"Name":"([^"]+?)"', layout):
                            name = match.group(1)
                            if name and name not in [p.get("name") for p in pages]:
                                pages.append({"name": name, "id": name})
                    except Exception:
                        pass
                    break
        return pages

    def _extract_visuals_from_zip(self, zip_ref, all_files, page_id_to_name) -> Dict:
        """Extrait les visuels et leurs valeurs (si trouvables dans le JSON)."""
        visuals = []
        kpis = []
        seen_kpi_ids = set()

        visual_files = [
            f for f in all_files
            if "visuals/" in f.replace("\\", "/")
            and f.endswith(".json")
            and "visual.json" in f.replace("\\", "/")
        ]

        for visual_file in visual_files:
            try:
                with zip_ref.open(visual_file) as f:
                    content = f.read().decode("utf-8", errors="ignore")

                display_match = re.search(r'"displayName"\s*:\s*"([^"]*?)"', content)
                title_match = re.search(r'"title"\s*:\s*"([^"]*?)"', content)
                name_match = re.search(r'"name"\s*:\s*"([^"]*?)"', content)

                visual_name = display_match.group(1) if display_match else (title_match.group(1) if title_match else (name_match.group(1) if name_match else "Visuel"))
                type_match = re.search(r'"visualType"\s*:\s*"([^"]*?)"', content)
                visual_type = type_match.group(1) if type_match else "unknown"

                # visual_file : .../pages/<pageId>/visuals/<visualId>/visual.json
                # -> remonter de 3 niveaux (pas 2) pour atteindre <pageId>,
                #    sinon on tombe sur le dossier littéralement nommé "visuals".
                page_id = Path(visual_file).parent.parent.parent.name
                page_name = page_id_to_name.get(page_id, page_id)

                measures_used = list(dict.fromkeys(re.findall(r'"measure"\s*:\s*"([^"]*?)"', content)))[:10]

                visual_value = None
                if "card" in visual_type.lower():
                    visual_value = self._extract_card_value_from_json(content)

                visual_id = Path(visual_file).parent.name
                visual_data = {
                    "name": visual_name,
                    "id": visual_id,
                    "type": visual_type,
                    "page": page_name,
                    "measures_used": measures_used,
                    "value": visual_value,
                }
                visuals.append(visual_data)

                if "card" in visual_type.lower() and visual_id not in seen_kpi_ids:
                    seen_kpi_ids.add(visual_id)
                    kpis.append({
                        "name": visual_name,
                        "value": visual_value,
                        "expression": ", ".join(measures_used) if measures_used else "",
                        "page": page_name,
                        "type": "card",
                        "id": visual_id,
                        "measures_used": measures_used,
                    })

            except Exception:
                pass

        return {"visuals": visuals, "kpis": kpis}

    def _extract_card_value_from_json(self, content: str) -> Optional[float]:
        """Extrait la valeur numérique d'un card (rarement présent en clair)."""
        patterns = [
            r'"singleValue"\s*:\s*([0-9.]+)',
            r'"value"\s*:\s*([0-9.]+)',
            r'"Value"\s*:\s*([0-9.]+)',
            r'"dataValue"\s*:\s*([0-9.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    return float(match.group(1))
                except Exception:
                    pass
        return None

    def _extract_dax_measures_from_zip(self, zip_ref, all_files) -> List[Dict]:
        """Extrait les mesures DAX (nom + expression, sans valeur)."""
        measures_found = {}
        dax_keywords = ("SUM", "CALCULATE", "AVERAGE", "COUNT", "DIVIDE", "DISTINCTCOUNT", "TOTALYTD", "SAMEPERIODLASTYEAR")
        json_files = [f for f in all_files if f.endswith(".json")]
        for json_file in json_files:
            try:
                with zip_ref.open(json_file) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                for match in re.finditer(r'"expression"\s*:\s*"((?:\\.|[^"\\])*)"', content):
                    expr = match.group(1).replace('\\"', '"')
                    if len(expr) > 10 and any(kw in expr.upper() for kw in dax_keywords):
                        window = content[max(0, match.start()-200):match.end()+100]
                        name_match = re.search(r'"name"\s*:\s*"([^"]+?)"', window)
                        name = name_match.group(1) if name_match else f"Measure_{len(measures_found)+1}"
                        if name not in measures_found:
                            measures_found[name] = expr[:500]
            except Exception:
                pass
        return [{"name": n, "dax": e, "type": "measure"} for n, e in measures_found.items()]

    def _extract_tables_from_zip(self, zip_ref, all_files) -> List[Dict]:
        """Extrait les noms de tables."""
        tables_found = []
        json_files = [f for f in all_files if f.endswith(".json")]
        for json_file in json_files:
            try:
                with zip_ref.open(json_file) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                for match in re.finditer(r'"table(?:Name)?"\s*:\s*"([^"]+?)"', content, re.I):
                    t = match.group(1)
                    if t and len(t) > 1 and t not in tables_found and t.lower() not in ["date", "calendar"]:
                        tables_found.append(t)
            except Exception:
                pass
        return [{"name": t, "type": "table"} for t in tables_found[:40]]

    def _extract_columns_from_zip(self, zip_ref, all_files) -> List[str]:
        """Extrait les noms de colonnes."""
        columns_found = []
        json_files = [f for f in all_files if f.endswith(".json")]
        for json_file in json_files:
            try:
                with zip_ref.open(json_file) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                for match in re.finditer(r'"columnName"\s*:\s*"([^"]+?)"', content):
                    col = match.group(1)
                    if col and len(col) > 0 and col not in columns_found:
                        columns_found.append(col)
            except Exception:
                pass
        return columns_found[:50]

    def _add_measure_kpis(self, result: Dict) -> None:
        """Ajoute des KPIs candidats basés sur le nom des mesures DAX (structure seule)."""
        kpi_hints = ("total", "sales", "current", "previous", "avg", "count", "ytd", "growth", "max", "min", "distinct")
        existing = {k.get("name", "").lower() for k in result.get("kpis", [])}
        for measure in result.get("dax_measures", []):
            name = (measure.get("name") or "").strip()
            if not name or name.lower() in existing:
                continue
            if any(h in name.lower() for h in kpi_hints):
                existing.add(name.lower())
                result["kpis"].append({
                    "name": name,
                    "value": None,
                    "expression": measure.get("dax", ""),
                    "page": "",
                    "type": "dax_measure",
                    "id": f"measure_{name[:8]}"
                })

    # ============================================================
    # AUTRES FORMATS
    # ============================================================

    def _extract_from_pbit(self, filepath: Path) -> Dict:
        result = self._extract_pbix_dispatch(filepath)
        result["metadata"]["type"] = "Power BI Template"
        return result

    def _extract_from_pbip(self, filepath: Path) -> Dict:
        result = self._extract_pbix_dispatch(filepath)
        result["metadata"]["type"] = "Power BI Project"
        return result

    def _extract_from_pdf(self, filepath: Path) -> Dict:
        result = {
            "tables": [], "measures": [], "dimensions": [], "visuals": [], "kpis": [],
            "dax_measures": [], "relationships": [], "calculated_columns": [], "pages": [], "columns": [],
            "tables_data": {},
            "metadata": {"source": "pdf", "file": str(filepath.name)}
        }
        try:
            import PyPDF2
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        for val in re.findall(r"\$?([0-9,]+\.?[0-9]*)", text)[:10]:
                            result["kpis"].append({"name": f"KPI_{len(result['kpis'])+1}", "value": val, "type": "kpi"})
        except Exception:
            pass
        return result

    def _extract_from_json(self, filepath: Path) -> Dict:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = {
            "tables": [], "measures": [], "dimensions": [], "visuals": [], "kpis": [],
            "dax_measures": [], "relationships": [], "calculated_columns": [], "pages": [], "columns": [],
            "tables_data": {},
            "metadata": {"source": "json", "file": str(filepath.name)}
        }
        if "measures" in data:
            for m in data["measures"]:
                result["dax_measures"].append({"name": m.get("name", ""), "dax": m.get("expression", "")})
        if "tables" in data:
            for t in data["tables"]:
                result["tables"].append({"name": t.get("name", "")})
        self._add_measure_kpis(result)
        return result

    def _extract_from_export(self, filepath: Path) -> Dict:
        if filepath.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath)
        result = {
            "tables": [{"name": "Data", "columns": list(df.columns)}],
            "measures": [], "dimensions": [], "visuals": [], "kpis": [],
            "dax_measures": [], "relationships": [], "calculated_columns": [], "pages": [], "columns": list(df.columns),
            "tables_data": {},
            "metadata": {"source": "export", "file": str(filepath.name), "rows": len(df)}
        }
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                result["measures"].append({"name": col, "expression": f"SUM({col})"})
        self._add_measure_kpis(result)
        return result

    # ============================================================
    # HELPERS
    # ============================================================

    def extract_all(self, filepath: str) -> Dict:
        return self.extract_from_file(filepath)

    def extract_measures(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("measures", []))

    def extract_dax_measures(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("dax_measures", []))

    def extract_tables(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("tables", []))

    def extract_visuals(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("visuals", []))

    def extract_kpis(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("kpis", []))

    def get_summary(self, filepath: str = None, result: Dict = None) -> Dict:
        if result is None:
            if filepath is None:
                raise ValueError("Fournir filepath ou result")
            result = self.extract_from_file(filepath)
        return {
            "file": str(filepath or result.get("metadata", {}).get("file", "")),
            "source": result.get("metadata", {}).get("source", "unknown"),
            "tables_count": len(result.get("tables", [])),
            "measures_count": len(result.get("measures", [])),
            "dax_measures_count": len(result.get("dax_measures", [])),
            "dimensions_count": len(result.get("dimensions", [])),
            "visuals_count": len(result.get("visuals", [])),
            "kpis_count": len(result.get("kpis", [])),
            "pages_count": len(result.get("pages", [])),
            "columns_count": len(result.get("columns", [])),
            "tables_data_count": len(result.get("tables_data", {})),
        }


# ============================================================
# TEST
# ============================================================

def extract_pbi_report(filepath: str, result: Dict = None) -> pd.DataFrame:
    """DataFrame plat pour la réconciliation. Passe result pour éviter un 2e appel au moteur."""
    if result is None:
        result = PBIExtractor().extract_from_file(filepath)

    data = []
    for kpi in result.get("kpis", []):
        data.append({
            "page": kpi.get("page", ""),
            "object_type": "KPI",
            "name": kpi.get("name", ""),
            "value": kpi.get("value", ""),
            "expression": kpi.get("expression", ""),
            "id": kpi.get("id", ""),
        })
    for visual in result.get("visuals", []):
        data.append({
            "page": visual.get("page", ""),
            "object_type": visual.get("type", "Visual"),
            "name": visual.get("name", ""),
            "value": visual.get("value", ""),
            "expression": ", ".join(visual.get("measures_used", []) or []),
            "id": visual.get("id", ""),
        })
    return pd.DataFrame(data)


if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("🚀 EXTRACTEUR POWER BI - MODULE A")
    print("=" * 70)

    if len(sys.argv) < 2:
        print("\nUsage :")
        print("  python pbi_extractor.py <chemin_fichier.pbix>")
        print("\nExemple :")
        print("  python pbi_extractor.py data/samples/case_encadrante_01/powerbi/sales_demo.pbix")
        sys.exit(1)

    test_file = Path(sys.argv[1])
    if not test_file.exists():
        print(f"\n❌ Fichier non trouvé : {test_file.resolve()}")
        sys.exit(1)

    print(f"\n📁 Fichier : {test_file.resolve()}")
    print(f"📄 Taille  : {test_file.stat().st_size:,} octets")
    print("=" * 70)

    extractor = PBIExtractor()
    result = extractor.extract_all(str(test_file))
    summary = extractor.get_summary(result=result)

    print(f"\n📈 RÉSULTATS ({summary.get('source')}):")
    print(f"   Pages        : {summary.get('pages_count', 0)}")
    print(f"   Visuels      : {summary.get('visuals_count', 0)}")
    print(f"   KPIs         : {summary.get('kpis_count', 0)}")
    print(f"   Mesures DAX  : {summary.get('dax_measures_count', 0)}")
    print(f"   Tables       : {summary.get('tables_count', 0)}")

    if result.get("kpis"):
        print(f"\n📈 KPIs ({len(result['kpis'])}):")
        for k in result["kpis"][:20]:
            val = k.get('value')
            val_str = f"value={val}" if val is not None else "no value"
            print(f"   - [{k.get('type', 'unknown')}] {k.get('name')} | {val_str}")

    out = test_file.parent / f"{test_file.stem}_pbi_extraction.json"
    with open(out, "w", encoding="utf-8") as f:
        export = {
            "metadata": result.get("metadata", {}),
            "pages": result.get("pages", []),
            "kpis": result.get("kpis", [])[:50],
            "visuals": result.get("visuals", [])[:30],
            "dax_measures": result.get("dax_measures", [])[:20],
            "tables": result.get("tables", []),
            "columns": result.get("columns", [])[:30],
            "summary": summary
        }
        json.dump(export, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Sauvegardé → {out.resolve()}")
    print("=" * 70)
    print("✅ Test terminé")
    print("=" * 70)