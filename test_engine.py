# test_engine.py
import json
from pathlib import Path
import websocket

class QlikEngineClient:
    def __init__(self, host="localhost", port=4848):
        self.url = f"ws://{host}:{port}/app/"
        self.ws = None
        self._id = 0
        self.app_handle = None

    def connect(self):
        self.ws = websocket.create_connection(self.url, timeout=15)
        self._recv()

    def close(self):
        if self.ws:
            self.ws.close()

    def _next_id(self):
        self._id += 1
        return self._id

    def _send(self, handle, method, params=None):
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "handle": handle,
            "method": method,
            "params": params if params is not None else [],
        }
        self.ws.send(json.dumps(msg))
        return self._recv_for_id(msg["id"])

    def _recv(self):
        return json.loads(self.ws.recv())

    def _recv_for_id(self, expected_id):
        while True:
            data = self._recv()
            if data.get("id") == expected_id:
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data.get("result", data)

    def open_app(self, app_path):
        result = self._send(-1, "OpenDoc", [str(Path(app_path).resolve())])
        self.app_handle = result["qReturn"]["qHandle"]
        return self.app_handle

    def create_session_object(self, props):
        result = self._send(self.app_handle, "CreateSessionObject", [props])
        return result["qReturn"]["qHandle"]

    def get_layout(self, handle):
        result = self._send(handle, "GetLayout", [])
        return result.get("qLayout", result)

    def get_properties(self, handle):
        result = self._send(handle, "GetProperties", [])
        return result.get("qProp", result)

    def get_object(self, obj_id):
        result = self._send(self.app_handle, "GetObject", [obj_id])
        return result["qReturn"]["qHandle"]

    def destroy_session_object(self, handle):
        try:
            self._send(self.app_handle, "DestroySessionObject", [handle])
        except Exception:
            pass


def extract_title(layout, props=None):
    """Récupère le meilleur titre possible d'un objet."""
    # 1. titre direct
    if layout.get("title"):
        return layout["title"]
    # 2. qMeta
    meta = layout.get("qMeta") or {}
    if meta.get("title"):
        return meta["title"]
    # 3. depuis les properties
    if props:
        if props.get("title"):
            return props["title"]
        qmeta = props.get("qMetaDef") or {}
        if qmeta.get("title"):
            return qmeta["title"]
    # 4. fallback
    return layout.get("qInfo", {}).get("qId", "Sans titre")


def extract_measure_expression(layout, props=None):
    """Récupère l'expression de la première mesure."""
    # Depuis le hypercube (layout)
    hc = layout.get("qHyperCube") or {}
    measures_info = hc.get("qMeasureInfo") or []
    if measures_info:
        # qFallbackTitle est souvent le label
        return measures_info[0].get("qFallbackTitle") or ""

    # Depuis les properties (définition réelle)
    if props:
        hc_def = props.get("qHyperCubeDef") or {}
        measures = hc_def.get("qMeasures") or []
        if measures:
            m = measures[0]
            # expression directe
            if m.get("qDef", {}).get("qDef"):
                return m["qDef"]["qDef"]
            # ou label
            if m.get("qDef", {}).get("qLabel"):
                return m["qDef"]["qLabel"]
            # master measure
            if m.get("qLibraryId"):
                return f"[Master:{m['qLibraryId']}]"
    return ""


APP_PATH = r"C:\Users\DELL\Documents\Qlik\Sense\Apps\sales_demo.qvf"

client = QlikEngineClient()
result = {
    "sheets": [],
    "kpis": [],
    "visuals": [],
    "measures": [],
    "dimensions": [],
    "metadata": {"source": "engine_api", "file": "sales_demo.qvf"}
}

try:
    client.connect()
    print("✅ Connecté à Qlik Sense Desktop")
    client.open_app(APP_PATH)
    print("📂 App ouverte\n")

    # ---------- 1. Master Measures ----------
    measure_props = {
        "qInfo": {"qType": "MeasureList"},
        "qMeasureListDef": {
            "qType": "measure",
            "qData": {
                "title": "/qMetaDef/title",
                "tags": "/qMetaDef/tags",
                "labelExpression": "/qMeasure/qLabelExpression",
                "expression": "/qMeasure/qDef",
            },
        },
    }
    h = client.create_session_object(measure_props)
    layout = client.get_layout(h)
    for item in layout.get("qMeasureList", {}).get("qItems", []):
        result["measures"].append({
            "id": item.get("qInfo", {}).get("qId"),
            "name": item.get("qMeta", {}).get("title") or item.get("qData", {}).get("title"),
            "expression": item.get("qData", {}).get("expression") or item.get("qData", {}).get("labelExpression") or "",
            "tags": item.get("qMeta", {}).get("tags", []),
        })
    client.destroy_session_object(h)
    print(f"📊 Mesures master : {len(result['measures'])}")
    for m in result["measures"]:
        print(f"   - {m['name']}  →  {m['expression'][:80] if m['expression'] else '(vide)'}")

    # ---------- 2. Master Dimensions ----------
    dim_props = {
        "qInfo": {"qType": "DimensionList"},
        "qDimensionListDef": {
            "qType": "dimension",
            "qData": {
                "title": "/qMetaDef/title",
                "tags": "/qMetaDef/tags",
                "field": "/qDim/qFieldDefs",
            },
        },
    }
    h = client.create_session_object(dim_props)
    layout = client.get_layout(h)
    for item in layout.get("qDimensionList", {}).get("qItems", []):
        fields = item.get("qData", {}).get("field") or []
        result["dimensions"].append({
            "id": item.get("qInfo", {}).get("qId"),
            "name": item.get("qMeta", {}).get("title") or item.get("qData", {}).get("title"),
            "field": fields[0] if fields else "",
            "tags": item.get("qMeta", {}).get("tags", []),
        })
    client.destroy_session_object(h)
    print(f"\n📐 Dimensions master : {len(result['dimensions'])}")
    for d in result["dimensions"]:
        print(f"   - {d['name']}  (field: {d['field']})")

    # ---------- 3. Sheets + objets ----------
    sheet_props = {
        "qInfo": {"qType": "SheetList"},
        "qAppObjectListDef": {
            "qType": "sheet",
            "qData": {
                "title": "/qMetaDef/title",
                "cells": "/cells",
                "rank": "/rank",
            },
        },
    }
    h = client.create_session_object(sheet_props)
    layout = client.get_layout(h)
    sheets = layout.get("qAppObjectList", {}).get("qItems", [])

    for sheet_item in sheets:
        sheet_id = sheet_item.get("qInfo", {}).get("qId")
        sheet_title = (
            sheet_item.get("qMeta", {}).get("title")
            or sheet_item.get("qData", {}).get("title")
            or sheet_id
        )
        sheet_info = {"id": sheet_id, "name": sheet_title, "objects": []}
        result["sheets"].append(sheet_info)
        print(f"\n📑 Feuille : {sheet_title}")

        cells = sheet_item.get("qData", {}).get("cells", [])
        for cell in cells:
            obj_id = cell.get("name")
            if not obj_id:
                continue
            try:
                obj_handle = client.get_object(obj_id)
                obj_layout = client.get_layout(obj_handle)
                obj_props = client.get_properties(obj_handle)

                obj_type = obj_layout.get("qInfo", {}).get("qType", "unknown")
                title = extract_title(obj_layout, obj_props)
                expression = extract_measure_expression(obj_layout, obj_props)

                obj_info = {
                    "id": obj_id,
                    "type": obj_type,
                    "name": title,
                    "sheet": sheet_title,
                    "expression": expression,
                    "dimensions": [],
                    "measures": [],
                    "value": None,
                }

                # Hypercube
                hc = obj_layout.get("qHyperCube") or {}
                if hc:
                    for d in hc.get("qDimensionInfo", []):
                        obj_info["dimensions"].append(
                            d.get("qFallbackTitle") or (d.get("qGroupFieldDefs") or [""])[0]
                        )
                    for m in hc.get("qMeasureInfo", []):
                        obj_info["measures"].append(m.get("qFallbackTitle") or "")

                    # Valeur (KPI ou total)
                    data_pages = hc.get("qDataPages", [])
                    if data_pages and data_pages[0].get("qMatrix"):
                        matrix = data_pages[0]["qMatrix"]
                        if matrix and matrix[0]:
                            cell0 = matrix[0][0]
                            obj_info["value"] = (
                                cell0.get("qNum")
                                if cell0.get("qNum") is not None
                                else cell0.get("qText")
                            )

                sheet_info["objects"].append(obj_info)

                if obj_type == "kpi":
                    result["kpis"].append(obj_info)
                    print(f"   ✅ KPI : {title}")
                    print(f"        valeur     = {obj_info.get('value')}")
                    print(f"        expression = {expression[:100] if expression else '(vide)'}")
                else:
                    result["visuals"].append(obj_info)
                    print(f"   📊 {obj_type} : {title}")

            except Exception as e:
                print(f"   ⚠️ Objet {obj_id} : {e}")

    client.destroy_session_object(h)

    # ---------- Résumé ----------
    print("\n" + "=" * 60)
    print("✅ EXTRACTION AMÉLIORÉE TERMINÉE")
    print(f"  Sheets     : {len(result['sheets'])}")
    print(f"  KPIs       : {len(result['kpis'])}")
    print(f"  Visuels    : {len(result['visuals'])}")
    print(f"  Mesures    : {len(result['measures'])}")
    print(f"  Dimensions : {len(result['dimensions'])}")
    print("=" * 60)

    # Affichage détaillé des KPIs
    print("\n📋 Détail des KPIs :")
    for kpi in result["kpis"]:
        print(f"  • [{kpi['sheet']}] {kpi['name']} = {kpi['value']}")
        if kpi["expression"]:
            print(f"      expr: {kpi['expression'][:90]}")

    # Sauvegarde
    out = Path("qlik_extraction_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Résultat sauvegardé → {out.resolve()}")

except Exception as e:
    print(f"\n❌ Erreur : {e}")
    import traceback
    traceback.print_exc()
finally:
    client.close()