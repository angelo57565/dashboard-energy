"""Cliente da API do EnergyGuard."""
import requests
import streamlit as st


def _request(base: str, key: str, method: str, path: str, params=None, json=None):
    headers = {"X-API-Key": key} if key else {}
    resp = requests.request(method, base + path, params=params, json=json, headers=headers, timeout=8)
    resp.raise_for_status()
    return None if resp.status_code == 204 or not resp.content else resp.json()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_get(base: str, key: str, path: str, params_items: tuple):
    return _request(base, key, "GET", path, params=dict(params_items))


class Api:
    def __init__(self, base: str, key: str):
        self.base, self.key = base.rstrip("/"), key

    @staticmethod
    def _clean(params: dict) -> dict:
        return {k: v for k, v in params.items() if v is not None}

    def get(self, path: str, **params):
        return _request(self.base, self.key, "GET", path, params=self._clean(params))

    def cached_get(self, path: str, **params):
        """GET com cache de 30 s (para dados pesados que mudam devagar)."""
        return _cached_get(self.base, self.key, path, tuple(sorted(self._clean(params).items())))

    def post(self, path: str, json=None):
        st.cache_data.clear()
        return _request(self.base, self.key, "POST", path, json=json)

    def put(self, path: str, json=None):
        st.cache_data.clear()
        return _request(self.base, self.key, "PUT", path, json=json)

    def delete(self, path: str):
        st.cache_data.clear()
        return _request(self.base, self.key, "DELETE", path)
