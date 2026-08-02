"""
Client Engine API (QIX) pour Qlik Sense Desktop - Module A / Module B
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import websocket


class QlikEngineClient:
    def __init__(self, host: str = "localhost", port: int = 4848):
        self.url = f"ws://{host}:{port}/app/"
        self.ws: Optional[websocket.WebSocket] = None
        self._id = 0
        self.app_handle: Optional[int] = None

    def connect(self):
        self.ws = websocket.create_connection(self.url, timeout=15)
        self._recv()

    def close(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, handle: int, method: str, params: Any = None) -> Dict:
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "handle": handle,
            "method": method,
            "params": params if params is not None else [],
        }
        self.ws.send(json.dumps(msg))
        return self._recv_for_id(msg["id"])

    def _recv(self) -> Dict:
        return json.loads(self.ws.recv())

    def _recv_for_id(self, expected_id: int) -> Dict:
        while True:
            data = self._recv()
            if data.get("id") == expected_id:
                if "error" in data:
                    raise RuntimeError(f"Engine error: {data['error']}")
                return data.get("result", data)

    def open_app(self, app_path: str) -> int:
        result = self._send(-1, "OpenDoc", [str(Path(app_path).resolve())])
        self.app_handle = result["qReturn"]["qHandle"]
        return self.app_handle

    def get_script(self) -> str:
        """Récupère le script de chargement (LOAD script) de l'app Qlik ouverte."""
        result = self._send(self.app_handle, "GetScript", [])
        return result.get("qScript", "")

    def create_session_object(self, props: Dict) -> int:
        result = self._send(self.app_handle, "CreateSessionObject", [props])
        return result["qReturn"]["qHandle"]

    def get_layout(self, handle: int) -> Dict:
        result = self._send(handle, "GetLayout", [])
        return result.get("qLayout", result)

    def get_properties(self, handle: int) -> Dict:
        result = self._send(handle, "GetProperties", [])
        return result.get("qProp", result)

    def get_object(self, obj_id: str) -> int:
        result = self._send(self.app_handle, "GetObject", [obj_id])
        return result["qReturn"]["qHandle"]

    def destroy_session_object(self, handle: int):
        try:
            self._send(self.app_handle, "DestroySessionObject", [handle])
        except Exception:
            pass


def _extract_title(layout: Dict, props: Optional[Dict] = None, expression: str = "") -> str:
    candidates = []
    if layout.get("title"):
        candidates.append(layout["title"])
    meta = layout.get("qMeta") or {}
    if meta.get("title"):
        candidates.append(meta["title"])
    if props:
        if props.get("title"):
            candidates.append(props["title"])
        qmeta = props.get("qMetaDef") or {}
        if qmeta.get("title"):
            candidates.append(qmeta["title"])

    for t in candidates:
        if t and not (len(str(t)) <= 12 and str(t).replace("_", "").isalnum()):
            return str(t)

    if expression:
        return expression
    return layout.get("qInfo", {}).get("qId", "Sans titre")


def _extract_measure_expression(layout: Dict, props: Optional[Dict] = None) -> str:
    hc = layout.get("qHyperCube") or {}
    measures_info = hc.get("qMeasureInfo") or []
    if measures_info:
        return measures_info[0].get("qFallbackTitle") or ""

    if props:
        hc_def = props.get("qHyperCubeDef") or {}
        measures = hc_def.get("qMeasures") or []
        if measures:
            m = measures[0]
            if m.get("qDef", {}).get("qDef"):
                return m["qDef"]["qDef"]
            if m.get("qDef", {}).get("qLabel"):
                return m["qDef"]["qLabel"]
            if m.get("qLibraryId"):
                return f"[Master:{m['qLibraryId']}]"
    return ""


def extract_app_structure(app_path: str) -> Dict:
    """
    Extraction complète pour les Modules A et B.
    Nécessite Qlik Sense Desktop lancé et connecté.
    """
    client = QlikEngineClient()
    result = {
        "sheets": [],
        "kpis": [],
        "visuals": [],
        "measures": [],
        "dimensions": [],
        "variables": [],
        "tables": [],
        "script": "",
        "metadata": {
            "source": "engine_api",
            "file": Path(app_path).name,
            "type": "Qlik Sense Desktop (Engine API)",
        },
    }

    try:
        client.connect()
        print(f"🔌 Connecté à Qlik Sense Desktop")
        client.open_app(app_path)
        print(f"📂 App ouverte : {Path(app_path).name}")

        # --- Script de chargement (pour le Module B) ---
        try:
            result["script"] = client.get_script()
            n_lines = len(result["script"].splitlines())
            print(f"  📜 Script de chargement récupéré ({n_lines} lignes)")
        except Exception as e:
            print(f"  ⚠️ Impossible de récupérer le script : {e}")

        # --- Master Measures ---
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
                "expression": item.get("qData", {}).get("expression")
                              or item.get("qData", {}).get("labelExpression") or "",
                "tags": item.get("qMeta", {}).get("tags", []),
            })
        client.destroy_session_object(h)
        print(f"  📊 Mesures master : {len(result['measures'])}")

        # --- Master Dimensions ---
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
                "field": fields[0] if isinstance(fields, list) and fields else "",
                "tags": item.get("qMeta", {}).get("tags", []),
            })
        client.destroy_session_object(h)
        print(f"  📐 Dimensions master : {len(result['dimensions'])}")

        # --- Sheets + objets ---
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

            for cell in sheet_item.get("qData", {}).get("cells", []):
                obj_id = cell.get("name")
                if not obj_id:
                    continue
                try:
                    obj_handle = client.get_object(obj_id)
                    obj_layout = client.get_layout(obj_handle)
                    obj_props = client.get_properties(obj_handle)

                    obj_type = obj_layout.get("qInfo", {}).get("qType", "unknown")
                    expression = _extract_measure_expression(obj_layout, obj_props)
                    title = _extract_title(obj_layout, obj_props, expression)

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

                    hc = obj_layout.get("qHyperCube") or {}
                    if hc:
                        for d in hc.get("qDimensionInfo", []):
                            obj_info["dimensions"].append(
                                d.get("qFallbackTitle") or (d.get("qGroupFieldDefs") or [""])[0]
                            )
                        for m in hc.get("qMeasureInfo", []):
                            obj_info["measures"].append(m.get("qFallbackTitle") or "")

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
                        print(f"  ✅ KPI : {title} = {obj_info.get('value')}")
                    else:
                        result["visuals"].append(obj_info)

                except Exception as e:
                    print(f"  ⚠️ Objet {obj_id} : {e}")

        client.destroy_session_object(h)

        print(f"\n✅ Extraction Engine API terminée")
        print(f"  - Sheets: {len(result['sheets'])}")
        print(f"  - KPIs: {len(result['kpis'])}")
        print(f"  - Visuels: {len(result['visuals'])}")
        print(f"  - Mesures: {len(result['measures'])}")
        print(f"  - Dimensions: {len(result['dimensions'])}")

    finally:
        client.close()

    return result