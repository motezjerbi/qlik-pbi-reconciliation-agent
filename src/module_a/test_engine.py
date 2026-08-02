# test_engine.py
import json
from pathlib import Path

# --- client minimal (copie de ce que je t'ai donné) ---
import websocket

class QlikEngineClient:
    def __init__(self, host="localhost", port=4848):
        self.url = f"ws://{host}:{port}/app/"
        self.ws = None
        self._id = 0
        self.app_handle = None

    def connect(self):
        self.ws = websocket.create_connection(self.url, timeout=10)
        self._recv()  # OnConnected

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

    def get_doc_list(self):
        return self._send(-1, "GetDocList", []).get("qDocList", [])

    def open_app(self, app_path):
        result = self._send(-1, "OpenDoc", [str(Path(app_path).resolve())])
        self.app_handle = result["qReturn"]["qHandle"]
        return self.app_handle


# --- test ---
APP_PATH = r"C:\Users\DELL\Documents\Qlik\Sense\Apps\sales_demo.qvf"

client = QlikEngineClient()
try:
    client.connect()
    print("✅ Connecté à Qlik Sense Desktop\n")

    docs = client.get_doc_list()
    print(f"📁 Apps trouvées ({len(docs)}) :")
    for d in docs:
        print(f"  - {d.get('qDocName')}  |  titre: {d.get('qTitle')}")

    print(f"\n📂 Ouverture de : {APP_PATH}")
    handle = client.open_app(APP_PATH)
    print(f"✅ App ouverte avec succès (handle = {handle})")

except Exception as e:
    print(f"\n❌ Erreur : {e}")
    import traceback
    traceback.print_exc()
finally:
    client.close()