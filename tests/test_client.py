"""
Tests du client LLM (src/llm/client.py).

Aucune dépendance réelle à Ollama : toutes les requêtes réseau sont mockées
via unittest.mock, pour que ces tests tournent en CI sans service externe.
"""
from unittest.mock import patch, MagicMock

import requests

from llm.client import LLMClient


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


class TestConnectionCheck:
    def test_connected_and_model_available(self):
        with patch("llm.client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(
                200, {"models": [{"name": "mistral:latest"}]}
            )
            client = LLMClient(model="mistral")
            assert client._connected is True
            assert client._model_available is True

    def test_model_not_installed(self):
        with patch("llm.client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, {"models": [{"name": "llama2"}]})
            client = LLMClient(model="mistral")
            assert client._connected is True
            assert client._model_available is False
            assert "non installé" in client._connection_error

    def test_ollama_unreachable(self):
        with patch("llm.client.requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
            client = LLMClient(model="mistral")
            assert client._connected is False
            assert "non accessible" in client._connection_error


class TestAsk:
    def _connected_client(self):
        with patch("llm.client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, {"models": [{"name": "mistral:latest"}]})
            return LLMClient(model="mistral")

    def test_ask_success(self):
        client = self._connected_client()
        with patch("llm.client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(200, {"response": "STATUT: COUVERT\nMESURE: X\nJUSTIFICATION: ok"})
            result = client.ask("un prompt")
            assert "COUVERT" in result

    def test_ask_timeout_returns_explicit_error(self):
        client = self._connected_client()
        with patch("llm.client.requests.post", side_effect=requests.exceptions.Timeout()):
            result = client.ask("un prompt", timeout=5)
            assert "ERREUR_PARSING" in result
            assert "Timeout" in result
            assert "5s" in result  # le timeout demandé doit apparaître dans le message

    def test_ask_empty_response_is_treated_as_error(self):
        client = self._connected_client()
        with patch("llm.client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(200, {"response": "ok"})  # < 5 caractères après strip -> trop court
            result = client.ask("un prompt")
            assert "ERREUR_PARSING" in result

    def test_ask_passes_custom_timeout_and_num_predict(self):
        client = self._connected_client()
        with patch("llm.client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(200, {"response": "réponse suffisamment longue"})
            client.ask("prompt", timeout=180, num_predict=400)
            _, kwargs = mock_post.call_args
            assert kwargs["timeout"] == 180
            assert kwargs["json"]["options"]["num_predict"] == 400

    def test_ask_when_ollama_down_returns_error_without_network_call(self):
        with patch("llm.client.requests.get", side_effect=requests.exceptions.ConnectionError()), \
             patch("llm.client.requests.post") as mock_post:
            client = LLMClient(model="mistral")
            result = client.ask("prompt")
            mock_post.assert_not_called()
            assert "ERREUR_PARSING" in result