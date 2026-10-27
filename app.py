"""EnergyGuard - Dashboard Streamlit.

Rodar:  streamlit run app.py
Config: variaveis de ambiente API_URL e API_KEY (ou pela barra lateral > Conexão).
"""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import requests
import streamlit as st

import tabs
from client import Api
from helpers import age_seconds, human_age, to_dataframe
from theme import build_css
from ui import banner

st.set_page_config(page_title="EnergyGuard", page_icon="⚡", layout="wide")

PERIODS = {"15 minutos": 0.25, "1 hora": 1, "6 horas": 6, "24 horas": 24}
THEME_OPTIONS = ["🌙 Escuro", "☀️ Claro (alto contraste)"]
OFFLINE_AFTER_S = 30

# ----------------------------- barra lateral (ordem visual) -----------------------------
with st.sidebar:
    st.title("⚡ EnergyGuard")
    theme_slot = st.container()
    device_slot = st.container()
    period_slot = st.container()
    refresh_slot = st.container()
    config_slot = st.expander("⚙️ Configurações")
    conn_slot = st.expander("🔌 Conexão com a API")

with conn_slot:
    api_url = st.text_input("URL da API", os.getenv("API_URL", "http://localhost:8000")).rstrip("/")
    api_key = st.text_input("API key", os.getenv("API_KEY", ""), type="password")
api = Api(api_url, api_key)

with theme_slot:
    if "tema_radio" not in st.session_state:
        st.session_state["tema_radio"] = THEME_OPTIONS[1 if st.query_params.get("tema") == "claro" else 0]
    choice = st.radio("Tema", THEME_OPTIONS, horizontal=True, key="tema_radio")
    theme = "light" if choice == THEME_OPTIONS[1] else "dark"
    st.query_params["tema"] = "claro" if theme == "light" else "escuro"

st.markdown(build_css(theme), unsafe_allow_html=True)

# configurações guardadas no backend (valem para qualquer navegador)
if "cfg_ready" not in st.session_state:
    cfg = {"tariff": 0.90, "nominal_voltage": 127, "monthly_goal_kwh": 0.0, "send_interval_s": 5}
    try:
        cfg.update(api.get("/api/settings"))
    except requests.RequestException:
        pass
    nominal0 = int(cfg["nominal_voltage"])
    st.session_state.update(
        cfg_tariff=float(cfg["tariff"]),
        cfg_nominal=nominal0 if nominal0 in (127, 220) else 127,
        cfg_goal=float(cfg["monthly_goal_kwh"]),
        cfg_interval=int(cfg["send_interval_s"]),
        cfg_ready=True,
    )

with config_slot:
    st.number_input("Tarifa (R$/kWh)", min_value=0.0, step=0.05, format="%.2f", key="cfg_tariff")
    st.selectbox("Tensão nominal da rede (V)", [127, 220], key="cfg_nominal")
    st.number_input("Meta mensal (kWh, 0 = sem meta)", min_value=0.0, step=10.0, key="cfg_goal")
    st.number_input("Intervalo de envio do ESP32 (s)", min_value=1, step=1, key="cfg_interval")
    if st.button("💾 Salvar configurações"):
        try:
            api.put("/api/settings", json={
                "tariff": float(st.session_state.cfg_tariff),
                "nominal_voltage": float(st.session_state.cfg_nominal),
                "monthly_goal_kwh": float(st.session_state.cfg_goal),
                "send_interval_s": float(st.session_state.cfg_interval),
            })
            st.success("Salvo.")
        except requests.RequestException as exc:
            st.error(f"Não consegui salvar: {exc}")

with period_slot:
    period_label = st.selectbox("Período", list(PERIODS), index=1)

with refresh_slot:
    auto = st.toggle("Atualizar automaticamente", value=True)
    every = st.slider("Intervalo (s)", 5, 60, 10) if auto else None
    st.button("🔄 Atualizar agora")

hours = PERIODS[period_label]

# ----------------------------- dispositivo -----------------------------
try:
    devices = api.get("/api/devices")
except requests.RequestException as exc:
    banner("danger", f"Não consegui falar com a API em {api_url}: {exc}")
    st.stop()

if not devices:
    banner("info", "Nenhuma leitura recebida ainda. Ligue o ESP32 ou rode scripts/simulate.py no backend.")
    st.stop()

with device_slot:
    device = st.selectbox("Dispositivo", [d["device_id"] for d in devices])

ctx = SimpleNamespace(
    api=api, device=device, theme=theme, auto=auto,
    tariff=float(st.session_state.cfg_tariff), nominal=int(st.session_state.cfg_nominal),
    goal=float(st.session_state.cfg_goal), interval=float(st.session_state.cfg_interval),
)


# ----------------------------- conteúdo -----------------------------
def render() -> None:
    hours_int = max(1, int(round(hours)))
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    try:
        latest = api.get("/api/readings/latest", device_id=device)
        rows = api.get("/api/readings", device_id=device, limit=20000, since=since)
        summary = api.get("/api/summary", device_id=device, hours=hours_int)
        anomalies = api.get("/api/anomalies", device_id=device, limit=200)
        model = api.get("/api/model/status")
    except requests.RequestException as exc:
        banner("danger", f"Erro ao consultar a API: {exc}")
        return

    data = dict(latest=latest, rows=rows, df=to_dataframe(rows), summary=summary, anomalies=anomalies,
                model=model, hours=hours, hours_int=hours_int)

    age = age_seconds(latest["created_at"])
    if age <= OFFLINE_AFTER_S:
        banner("ok", f"🟢 {device} online · última leitura há {human_age(age)}")
    else:
        banner("danger", f"🔴 {device} sem dados há {human_age(age)}")
    if latest["is_anomaly"]:
        banner("warn", f"⚠️ A última leitura foi marcada como anomalia (score {latest['anomaly_score']:.3f}).")

    t = st.tabs(["📊 Visão geral", "📈 Gráficos", "🔋 Consumo", f"⚠️ Anomalias ({len(anomalies)})",
                 "🔔 Alertas", "🩺 Qualidade e saúde", "🧪 Validação", "🤖 Modelo"])
    with t[0]:
        tabs.overview(ctx, data)
    with t[1]:
        tabs.charts_tab(ctx, data)
    with t[2]:
        tabs.consumption(ctx, data)
    with t[3]:
        tabs.anomalies_tab(ctx, data)
    with t[4]:
        tabs.alerts_tab(ctx, data)
    with t[5]:
        tabs.quality_health(ctx, data)
    with t[6]:
        tabs.validation(ctx, data)
    with t[7]:
        tabs.model_tab(ctx, data)


st.title("Monitoramento de energia")
if auto:
    st.fragment(run_every=every)(render)()
else:
    render()
