# src/module_a/extractors/qlik_extractor.py
"""
Extracteur Qlik Sense - Module A (Data Reconciliation)

Support principal : .qvf binaire via Engine API (Qlik Sense Desktop)
Fallback : JSON / Excel / CSV

Prérequis :
  - Qlik Sense Desktop lancé et connecté (pour .qvf)
  - pip install websocket-client pandas

Usage test :
  python src/module_a/extractors/qlik_extractor.py <chemin_fichier.qvf>
"""

import sys
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import du client Engine API (fonctionne en package et en script direct)
_EXTRACTORS_DIR = Path(__file__).resolve().parent
if str(_EXTRACTORS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXTRACTORS_DIR))

try:
    from .qlik_engine_client import extract_app_structure
except ImportError:
    from qlik_engine_client import extract_app_structure


class QlikExtractor:
    """
    Extrait les objets d'un rapport Qlik Sense.
    Module A : KPIs (+ valeurs), visuels, mesures, dimensions, sheets.
    """

    def __init__(self):
        self.kpis = []
        self.visuals = []
        self.tables = []
        self.measures = []
        self.dimensions = []
        self.variables = []
        self.sheets = []

    def extract_from_file(self, filepath: str) -> Dict:
        """Point d'entrée : n'importe quel chemin fourni par l'appelant."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Fichier introuvable : {filepath}")

        suffix = filepath.suffix.lower()

        if suffix == ".qvf":
            return self._extract_from_qvf(filepath)
        if suffix in (".json", ".txt"):
            return self._extract_from_json(filepath)
        if suffix in (".xlsx", ".xls", ".csv"):
            return self._extract_from_export(filepath)
        raise ValueError(
            f"Format non supporté pour le Module A: {suffix}. "
            "Utilisez un .qvf (recommandé) ou un export JSON/Excel/CSV."
        )

    # ============================================================
    # EXTRACTION .QVF (via Engine API)
    # ============================================================

    def _extract_from_qvf(self, filepath: Path) -> Dict:
        with open(filepath, "rb") as f:
            header = f.read(8)

        is_json = (
            header.startswith(b"{")
            or header.startswith(b"[")
            or header.startswith(b"\xef\xbb\xbf{")
        )

        if is_json:
            print(f"📄 Fichier JSON détecté → parsing classique")
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._parse_legacy_json(data, filepath)

        print(f"🔌 Extraction via Engine API : {filepath.name}")
        print("   (Qlik Sense Desktop doit être ouvert et connecté)")

        try:
            return extract_app_structure(str(filepath.resolve()))
        except ConnectionRefusedError:
            raise RuntimeError(
                "Impossible de se connecter à Qlik Sense Desktop.\n"
                "→ Vérifiez que Qlik Sense Desktop est lancé et connecté.\n"
                "→ URL attendue : ws://localhost:4848"
            )
        except Exception as e:
            raise RuntimeError(f"Erreur Engine API : {e}") from e

    def _parse_legacy_json(self, data: Dict, filepath: Path) -> Dict:
        result = {
            "tables": [],
            "measures": [],
            "dimensions": [],
            "visuals": [],
            "kpis": [],
            "sheets": [],
            "variables": [],
            "metadata": {
                "source": "json",
                "file": str(filepath.name),
                "type": "Qlik JSON Export (legacy)",
            },
        }

        for sheet in data.get("sheets", []):
            sheet_info = {
                "id": sheet.get("id", ""),
                "name": sheet.get("name", ""),
                "objects": [],
            }
            result["sheets"].append(sheet_info)

            for obj in sheet.get("objects", []):
                obj_type = obj.get("type", "")
                obj_info = {
                    "id": obj.get("id", ""),
                    "type": obj_type,
                    "name": obj.get("name", ""),
                    "expression": obj.get("expression", ""),
                    "dimensions": obj.get("dimensions", []),
                    "measures": obj.get("measures", []),
                    "sheet": sheet.get("name", ""),
                    "value": obj.get("value"),
                }
                sheet_info["objects"].append(obj_info)

                if obj_type == "kpi":
                    result["kpis"].append(obj_info)
                elif obj_type in (
                    "bar-chart",
                    "line-chart",
                    "pie-chart",
                    "scatter-plot",
                    "table",
                    "pivot-table",
                    "barchart",
                    "linechart",
                    "piechart",
                ):
                    result["visuals"].append(obj_info)

        for measure in data.get("measures", []):
            result["measures"].append(
                {
                    "name": measure.get("name", ""),
                    "expression": measure.get("expression", ""),
                    "tags": measure.get("tags", []),
                }
            )

        for dim in data.get("dimensions", []):
            result["dimensions"].append(
                {
                    "name": dim.get("name", ""),
                    "field": dim.get("field", ""),
                    "tags": dim.get("tags", []),
                }
            )

        for var in data.get("variables", []):
            result["variables"].append(
                {
                    "name": var.get("name", ""),
                    "value": var.get("value", ""),
                    "type": var.get("type", ""),
                }
            )

        result["metadata"]["app_name"] = data.get("app_name", "")
        result["metadata"]["app_id"] = data.get("app_id", "")
        return result

    # ============================================================
    # FALLBACK JSON / Excel / CSV
    # ============================================================

    def _extract_from_json(self, filepath: Path) -> Dict:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._parse_json_data(data, filepath)

    def _extract_from_export(self, filepath: Path) -> Dict:
        if filepath.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath)
        return self._parse_dataframe(df, filepath)

    def _parse_json_data(self, data: Any, filepath: Path) -> Dict:
        result = {
            "tables": [],
            "measures": [],
            "dimensions": [],
            "visuals": [],
            "kpis": [],
            "sheets": [],
            "variables": [],
            "metadata": {
                "source": "json",
                "file": str(filepath.name),
                "type": "Qlik Export",
            },
        }
        if isinstance(data, list) and data:
            return self._parse_dataframe(pd.DataFrame(data), filepath)
        return result

    def _parse_dataframe(self, df: pd.DataFrame, filepath: Path) -> Dict:
        result = {
            "tables": [],
            "measures": [],
            "dimensions": [],
            "visuals": [],
            "kpis": [],
            "sheets": [],
            "variables": [],
            "metadata": {
                "source": "export",
                "file": str(filepath.name),
                "type": "Data Export",
                "rows": len(df),
                "columns": len(df.columns),
            },
        }
        result["tables"].append(
            {
                "name": "Data",
                "type": "EXPORT",
                "columns": list(df.columns),
                "rows": len(df),
            }
        )
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                result["measures"].append(
                    {
                        "name": col,
                        "expression": f"SUM({col})",
                        "type": "measure",
                    }
                )
            else:
                result["dimensions"].append(
                    {
                        "name": col,
                        "field": col,
                        "type": "dimension",
                    }
                )
        return result

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def extract_kpis(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("kpis", []))

    def extract_measures(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("measures", []))

    def extract_dimensions(self, filepath: str) -> pd.DataFrame:
        return pd.DataFrame(self.extract_from_file(filepath).get("dimensions", []))

    def extract_all(self, filepath: str) -> Dict:
        return self.extract_from_file(filepath)

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
            "dimensions_count": len(result.get("dimensions", [])),
            "visuals_count": len(result.get("visuals", [])),
            "kpis_count": len(result.get("kpis", [])),
            "sheets_count": len(result.get("sheets", [])),
            "variables_count": len(result.get("variables", [])),
        }


def extract_qlik_report(filepath: str, result: Dict = None) -> pd.DataFrame:
    """DataFrame plat pour la réconciliation. Passe result pour éviter un 2e appel API."""
    if result is None:
        result = QlikExtractor().extract_from_file(filepath)

    data = []
    for kpi in result.get("kpis", []):
        data.append(
            {
                "sheet": kpi.get("sheet", ""),
                "object_type": "KPI",
                "name": kpi.get("name", ""),
                "value": kpi.get("value", ""),
                "expression": kpi.get("expression", ""),
                "id": kpi.get("id", ""),
            }
        )
    for measure in result.get("measures", []):
        data.append(
            {
                "sheet": "Global",
                "object_type": "Measure",
                "name": measure.get("name", ""),
                "value": "",
                "expression": measure.get("expression", ""),
                "id": measure.get("id", ""),
            }
        )
    for visual in result.get("visuals", []):
        data.append(
            {
                "sheet": visual.get("sheet", ""),
                "object_type": visual.get("type", "Visual"),
                "name": visual.get("name", ""),
                "value": visual.get("value", ""),
                "expression": visual.get("expression", ""),
                "id": visual.get("id", ""),
            }
        )
    return pd.DataFrame(data)


# ============================================================
# TEST — chemin uniquement via la ligne de commande
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 EXTRACTEUR QLIK - MODULE A (Engine API)")
    print("=" * 70)

    if len(sys.argv) < 2:
        print("\nUsage :")
        print("  python src/module_a/extractors/qlik_extractor.py <chemin_fichier.qvf>")
        print("\nExemple :")
        print(
            r'  python src/module_a/extractors/qlik_extractor.py "C:\Users\DELL\Documents\Qlik\Sense\Apps\sales_demo.qvf"'
        )
        sys.exit(1)

    qvf_file = Path(sys.argv[1])

    if not qvf_file.exists():
        print(f"\n❌ Fichier non trouvé : {qvf_file.resolve()}")
        sys.exit(1)

    print(f"\n📁 Fichier : {qvf_file.resolve()}")
    print(f"📄 Taille  : {qvf_file.stat().st_size:,} octets")
    print("=" * 70)

    extractor = QlikExtractor()

    try:
        result = extractor.extract_from_file(str(qvf_file))
        summary = extractor.get_summary(result=result)

        print(f"\n📊 RÉSULTATS :")
        print(f"   - Sheets     : {summary.get('sheets_count', 0)}")
        print(f"   - KPIs       : {summary.get('kpis_count', 0)}")
        print(f"   - Visuels    : {summary.get('visuals_count', 0)}")
        print(f"   - Mesures    : {summary.get('measures_count', 0)}")
        print(f"   - Dimensions : {summary.get('dimensions_count', 0)}")
        print(f"   - Variables  : {summary.get('variables_count', 0)}")
        print(f"   - Source     : {summary.get('source', '')}")

        if result.get("sheets"):
            print(f"\n📑 Sheets :")
            for sheet in result["sheets"]:
                print(
                    f"   - {sheet.get('name', 'Sans nom')} "
                    f"({len(sheet.get('objects', []))} objets)"
                )

        if result.get("kpis"):
            print(f"\n📋 KPIs :")
            for kpi in result["kpis"]:
                print(
                    f"   - [{kpi.get('sheet')}] {kpi.get('name')} = {kpi.get('value')}"
                )
                if kpi.get("expression"):
                    print(f"       expr: {str(kpi.get('expression'))[:80]}")

        if result.get("measures"):
            print(f"\n📊 Mesures master :")
            for m in result["measures"]:
                print(f"   - {m.get('name')} → {str(m.get('expression', ''))[:60]}")

        if result.get("dimensions"):
            print(f"\n📐 Dimensions master :")
            for d in result["dimensions"]:
                print(f"   - {d.get('name')} (field: {d.get('field', '')})")

        df = extract_qlik_report(str(qvf_file), result=result)
        print(f"\n📊 DataFrame : {len(df)} lignes")
        if not df.empty:
            print(df.head(12).to_string(index=False))

        # JSON à côté du fichier source (pas de chemin projet en dur)
        out = qvf_file.parent / f"{qvf_file.stem}_qlik_extraction.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "sheets": result.get("sheets", []),
                    "kpis": result.get("kpis", []),
                    "visuals": result.get("visuals", []),
                    "measures": result.get("measures", []),
                    "dimensions": result.get("dimensions", []),
                    "variables": result.get("variables", []),
                    "metadata": result.get("metadata", {}),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\n💾 Sauvegardé → {out.resolve()}")

    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 70)
    print("✅ Test terminé")
    print("=" * 70)