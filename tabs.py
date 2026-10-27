"""Conteudo de cada aba do dashboard. Cada funcao recebe `ctx` (api, device, tema, configuracoes...)."""
import pandas as pd
import requests
import streamlit as st

import charts
from helpers import (
    QUANTITY_PT, anomalies_table, availability_pct, fmt_pct, human_age, hourly_dataframe,
    daily_consumption, median_interval_s, month_projection, readings_csv, reasons_text, rssi_label,
    to_dataframe, today_vs_yesterday, validation_csv, validation_dataframe, validation_summary,
    validation_table,
)
from ui import banner, cards, progress, rerun, table

METRICS_PT = {
    "voltage": ("Tensão", "V"), "current": ("Corrente", "A"), "power": ("Potência", "W"),
    "power_factor": ("Fator de potência", ""), "frequency": ("Frequência", "Hz"),
    "apparent_power": ("Potência aparente", "VA"), "reactive_power": ("Potência reativa", "var"),
}
VOLTAGE_RANGES = {127: (117.0, 133.0), 220: (202.0, 231.0)}  # faixa adequada (PRODIST)


def _voltage_range(nominal: int) -> tuple[float, float]:
    return VOLTAGE_RANGES.get(nominal, (round(nominal * 0.92, 1), round(nominal * 1.05, 1)))


def _guard(ctx, fn):
    """Executa uma ação de escrita na API mostrando o erro, se houver."""
    try:
        fn()
        return True
    except requests.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        banner("danger", f"Erro: {detail}")
    except requests.RequestException as exc:
        banner("danger", f"Erro de conexão: {exc}")
    return False


# ----------------------------- Visão geral -----------------------------
def overview(ctx, d):
    latest, summary = d["latest"], d["summary"]
    s_va = latest["voltage"] * latest["current"]
    q_var = max(s_va ** 2 - latest["power"] ** 2, 0) ** 0.5
    st.subheader("Agora")
    cards([
        ("Tensão", f"{latest['voltage']:.1f} V"),
        ("Corrente", f"{latest['current']:.2f} A"),
        ("Potência ativa", f"{latest['power']:.0f} W"),
        ("Potência aparente", f"{s_va:.0f} VA"),
        ("Potência reativa", f"{q_var:.0f} var"),
        ("Fator de potência", f"{latest['power_factor']:.2f}"),
        ("Frequência", f"{latest['frequency']:.2f} Hz"),
        ("Energia total", f"{latest['energy']:.3f} kWh"),
    ])
    st.subheader(f"Resumo · últimas {d['hours_int']} h")
    kwh = summary["energy_kwh"] or 0.0
    cards([
        ("Consumo", f"{kwh:.3f} kWh"),
        ("Custo estimado", f"R$ {kwh * ctx.tariff:.2f}"),
        ("Potência média", f"{summary['power_avg'] or 0:.0f} W"),
        ("Pico de potência", f"{summary['power_max'] or 0:.0f} W"),
        ("Anomalias", str(summary["anomalies"])),
    ])


# ----------------------------- Gráficos -----------------------------
def charts_tab(ctx, d):
    rows, df = d["rows"], d["df"]
    c1, c2 = st.columns([3, 2])
    which = c1.radio("Mostrar", ["Tudo", *charts.SERIES], horizontal=True, key="serie")
    mark = c2.checkbox("Marcar anomalias", value=True, key="marcar")
    if df.empty:
        banner("info", "Sem leituras neste período.")
        return
    st.plotly_chart(charts.timeseries(df, which, mark, ctx.theme), theme=None, key="grafico")
    st.download_button(" Baixar leituras (CSV)", readings_csv(rows),
                       file_name=f"leituras_{ctx.device}.csv", mime="text/csv", key="dl_leituras")


# ----------------------------- Consumo -----------------------------
def consumption(ctx, d):
    try:
        raw = ctx.api.cached_get("/api/consumption/hourly", device_id=ctx.device, hours=24 * 31)
    except requests.RequestException as exc:
        banner("danger", f"Erro ao consultar o consumo: {exc}")
        return
    hourly = hourly_dataframe(raw)
    if hourly.empty:
        banner("info", "Ainda não há consumo registrado.")
        return

    now = pd.Timestamp.now(tz="America/Sao_Paulo")
    today, y_same, y_total = today_vs_yesterday(hourly, now)
    so_far, projected, days = month_projection(hourly, now)

    delta = f"{(today - y_same) / y_same * 100:+.0f}% vs ontem" if y_same > 0.001 else "—"
    st.subheader("Hoje")
    cards([
        ("Hoje até agora", f"{today:.2f} kWh"),
        ("Ontem até a mesma hora", f"{y_same:.2f} kWh"),
        ("Diferença", delta),
        ("Ontem inteiro", f"{y_total:.2f} kWh"),
    ])

    st.subheader("Mês")
    cards([
        ("Consumo no mês", f"{so_far:.2f} kWh"),
        ("Projeção do mês", f"{projected:.1f} kWh"),
        ("Custo até agora", f"R$ {so_far * ctx.tariff:.2f}"),
        ("Custo projetado", f"R$ {projected * ctx.tariff:.2f}"),
    ])
    if ctx.goal > 0:
        frac = so_far / ctx.goal
        progress(frac, f"Meta de {ctx.goal:.0f} kWh: {so_far:.1f} kWh usados ({frac * 100:.0f}%)")
        if projected > ctx.goal:
            banner("warn", f"Nesse ritmo você chega a {projected:.1f} kWh e passa da meta de {ctx.goal:.0f} kWh.")
        else:
            banner("ok", f"Nesse ritmo você fecha o mês com {projected:.1f} kWh, dentro da meta.")
    else:
        st.caption("Defina uma meta mensal em  Configurações para ver a barra de progresso.")

    last24 = hourly[hourly["period"] >= now - pd.Timedelta(hours=24)]
    st.plotly_chart(charts.bars(last24["period"], last24["kwh"], ctx.theme, "Consumo por hora (últimas 24 h)"),
                    theme=None, key="barras_hora")
    daily = daily_consumption(hourly).tail(14)
    st.plotly_chart(charts.bars(daily["day"].dt.strftime("%d/%m"), daily["kwh"], ctx.theme,
                                "Consumo por dia (últimos 14 dias)"), theme=None, key="barras_dia")


# ----------------------------- Anomalias -----------------------------
def anomalies_tab(ctx, d):
    df, anomalies = d["df"], d["anomalies"]
    if not d["model"]["ready"]:
        banner("warn", "O modelo ainda não foi treinado, então nada foi classificado. Veja a aba Modelo.")
    if not df.empty and df["anomaly_score"].notna().any():
        st.plotly_chart(charts.score_chart(df, ctx.theme), theme=None, key="grafico_score")

    if not anomalies:
        banner("info", "Nenhuma anomalia registrada.")
    else:
        st.subheader("Últimas anomalias")
        table(anomalies_table(anomalies).head(30))
        st.download_button(" Baixar anomalias (CSV)", readings_csv(anomalies),
                           file_name=f"anomalias_{ctx.device}.csv", mime="text/csv", key="dl_anomalias")

        pending = [a for a in anomalies if not a.get("feedback")][:8]
        st.subheader("Avalie as anomalias")
        st.caption("Suas respostas calculam a precisão do modelo (aba Modelo) e as anomalias reais saem do próximo treino.")
        if not pending:
            banner("ok", "Todas as anomalias recentes já foram avaliadas.")
        for a in pending:
            local = pd.to_datetime(a["created_at"], utc=True).tz_convert("America/Sao_Paulo")
            st.markdown(f"**#{a['id']}** · {local:%d/%m %H:%M:%S} · {a['voltage']:.0f} V · "
                        f"{a['current']:.2f} A · {a['power']:.0f} W")
            why = reasons_text(a.get("reasons"))
            if why:
                st.caption(why)
            b1, b2 = st.columns(2)
            if b1.button("É real", key=f"real_{a['id']}"):
                if _guard(ctx, lambda: ctx.api.put(f"/api/readings/{a['id']}/feedback", json={"label": "real"})):
                    rerun(ctx.auto)
            if b2.button(" Falso alarme", key=f"false_{a['id']}"):
                if _guard(ctx, lambda: ctx.api.put(f"/api/readings/{a['id']}/feedback", json={"label": "false"})):
                    rerun(ctx.auto)

    with st.expander("Rotular qualquer leitura (inclusive as que o modelo deixou passar)"):
        with st.form("form_rotulo", clear_on_submit=False):
            rid = st.number_input("ID da leitura", min_value=1, step=1, value=1)
            choice = st.selectbox("Rótulo", ["Anomalia real (o modelo perdeu)", "Normal (não é anomalia)",
                                             "Remover rótulo"])
            if st.form_submit_button("Salvar rótulo"):
                label = {"Anomalia real (o modelo perdeu)": "real", "Normal (não é anomalia)": "false",
                         "Remover rótulo": None}[choice]
                if _guard(ctx, lambda: ctx.api.put(f"/api/readings/{int(rid)}/feedback", json={"label": label})):
                    banner("ok", f"Leitura #{int(rid)} atualizada.")


# ----------------------------- Alertas -----------------------------
def alerts_tab(ctx, d):
    try:
        channels = ctx.api.get("/api/alerts/channels")
        rules = ctx.api.get("/api/alerts/rules")
        events = ctx.api.get("/api/alerts/events", device_id=ctx.device, limit=50)
    except requests.RequestException as exc:
        banner("danger", f"Erro ao consultar alertas: {exc}")
        return

    on = [n for n, v in (("Telegram", channels["telegram"]), ("E-mail", channels["email"])) if v]
    if on:
        banner("ok", "Avisos enviados por: " + ", ".join(on))
        if st.button(" Enviar mensagem de teste", key="teste_notif"):
            _guard(ctx, lambda: banner("info", "Teste enviado." if ctx.api.post("/api/alerts/test")["sent"]
                                       else "Nenhum canal conseguiu enviar."))
    else:
        banner("warn", "Telegram e e-mail não configurados: os alertas só aparecem aqui. "
                       "Preencha o .env do backend para receber no celular.")

    st.subheader("Regras")
    if not rules:
        banner("info", "Nenhuma regra ainda. Crie uma abaixo ou use as sugeridas.")
    for rule in rules:
        label, unit = METRICS_PT[rule["metric"]]
        scope = rule["device_id"] or "todos os dispositivos"
        state = "" if rule["enabled"] else " (desligada)"
        st.markdown(f"**{rule['name']}**{state}  \n{label} {rule['operator']} {rule['threshold']:g} {unit} · "
                    f"aviso a cada {rule['cooldown_s'] // 60} min · {scope}")
        b1, b2 = st.columns(2)
        if b1.button("⏸ Desligar" if rule["enabled"] else "▶ Ligar", key=f"tog_{rule['id']}"):
            body = {k: rule[k] for k in ("name", "metric", "operator", "threshold", "cooldown_s", "device_id")}
            body["enabled"] = not rule["enabled"]
            if _guard(ctx, lambda: ctx.api.put(f"/api/alerts/rules/{rule['id']}", json=body)):
                rerun(ctx.auto)
        if b2.button("Excluir", key=f"del_{rule['id']}"):
            if _guard(ctx, lambda: ctx.api.delete(f"/api/alerts/rules/{rule['id']}")):
                rerun(ctx.auto)

    vmin, vmax = _voltage_range(ctx.nominal)
    if st.button(f"Criar regras sugeridas ({ctx.nominal} V)", key="sugeridas"):
        base = {"cooldown_s": 600, "enabled": True, "device_id": None}
        suggested = [
            {"name": "Tensão baixa", "metric": "voltage", "operator": "<", "threshold": vmin},
            {"name": "Tensão alta", "metric": "voltage", "operator": ">", "threshold": vmax},
            {"name": "Frequência baixa", "metric": "frequency", "operator": "<", "threshold": 59.5},
            {"name": "Frequência alta", "metric": "frequency", "operator": ">", "threshold": 60.5},
        ]
        # a tensão/frequência 0 significa "sem rede": o ESP32 offline já tem o seu próprio aviso
        if _guard(ctx, lambda: [ctx.api.post("/api/alerts/rules", json={**base, **r}) for r in suggested]):
            rerun(ctx.auto)

    with st.expander(" Nova regra"):
        with st.form("form_regra", clear_on_submit=True):
            name = st.text_input("Nome", "Corrente alta")
            metric = st.selectbox("Grandeza", list(METRICS_PT), format_func=lambda m: f"{METRICS_PT[m][0]} ({METRICS_PT[m][1]})".replace(" ()", ""))
            op = st.radio("Dispara quando for", [">", "<"], horizontal=True,
                          format_func=lambda o: "maior que" if o == ">" else "menor que")
            thr = st.number_input("Limite", value=30.0, step=1.0)
            cool = st.number_input("Intervalo mínimo entre avisos (min)", min_value=0, value=10, step=1)
            only = st.checkbox(f"Só para {ctx.device}", value=False)
            if st.form_submit_button("Criar regra"):
                body = {"name": name, "metric": metric, "operator": op, "threshold": float(thr),
                        "cooldown_s": int(cool) * 60, "enabled": True, "device_id": ctx.device if only else None}
                if _guard(ctx, lambda: ctx.api.post("/api/alerts/rules", json=body)):
                    rerun(ctx.auto)

    st.subheader("Histórico")
    if not events:
        banner("info", "Nenhum alerta disparado ainda.")
        return
    kinds = {"rule": "regra", "anomaly": "anomalia", "offline": "offline"}
    ev = pd.DataFrame(events)
    ev["created_at"] = pd.to_datetime(ev["created_at"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.strftime("%d/%m %H:%M")
    out = pd.DataFrame({
        "Horário": ev["created_at"], "Tipo": ev["kind"].map(kinds), "Mensagem": ev["message"],
        "Enviado": ev["notified"].map({True: "sim", False: "não"}),
    })
    table(out)


# ----------------------------- Qualidade e saúde -----------------------------
def quality_health(ctx, d):
    latest, df, hours_int = d["latest"], d["df"], d["hours_int"]
    vmin, vmax = _voltage_range(ctx.nominal)

    st.subheader(f"Qualidade da energia · últimas {hours_int} h")
    try:
        q = ctx.api.cached_get("/api/quality", device_id=ctx.device, hours=hours_int, vmin=vmin, vmax=vmax)
    except requests.RequestException as exc:
        banner("danger", f"Erro ao consultar a qualidade: {exc}")
        q = None
    if q and q["readings_with_mains"]:
        v, f = q["voltage"], q["frequency"]
        cards([
            ("Tensão mínima", f"{v['min']:.1f} V"),
            ("Tensão média", f"{v['avg']:.1f} V"),
            ("Tensão máxima", f"{v['max']:.1f} V"),
            (f"Abaixo de {vmin:g} V", fmt_pct(v["low_pct"])),
            (f"Acima de {vmax:g} V", fmt_pct(v["high_pct"])),
            ("Frequência mín–máx", f"{f['min']:.2f}–{f['max']:.2f} Hz" if f["min"] is not None else "—"),
            ("Frequência fora de 59,5–60,5 Hz", fmt_pct(f["out_pct"])),
        ])
        st.caption(f"Faixa adequada para {ctx.nominal} V: {vmin:g} a {vmax:g} V. Mude a tensão nominal em ⚙️ Configurações.")
    elif q:
        banner("info", "Sem leituras com a rede ligada neste período.")

    st.subheader("Saúde do ESP32")
    rssi = latest.get("rssi")
    n = len(d["rows"])
    avail = availability_pct(n, d["hours"], ctx.interval)
    interval = median_interval_s(df)
    cards([
        ("Sinal Wi-Fi", f"{rssi} dBm ({rssi_label(rssi)})" if rssi is not None else "—"),
        ("Ligado há", human_age(latest["uptime_s"]) if latest.get("uptime_s") is not None else "—"),
        ("Falhas de envio", str(latest["send_failures"]) if latest.get("send_failures") is not None else "—"),
        ("Disponibilidade", f"{avail:.0f}%"),
        ("Intervalo entre leituras", f"{interval:.1f} s" if interval else "—"),
    ])
    if latest.get("uptime_s") is not None and latest["uptime_s"] < 120:
        banner("info", "O ESP32 reiniciou há pouco tempo.")
    if rssi is not None and rssi < -80:
        banner("warn", "Sinal Wi-Fi ruim: aproxime o ESP32 do roteador para evitar falhas de envio.")
    if not df.empty and "rssi" in df and df["rssi"].notna().any():
        st.plotly_chart(charts.rssi_chart(df, ctx.theme), theme=None, key="grafico_rssi")


# ----------------------------- Validação -----------------------------
def validation(ctx, d):
    st.caption("Meça a mesma grandeza com multímetro (tensão) ou alicate amperímetro (corrente) e digite o valor. "
               "O sistema guarda a média das últimas 6 leituras do ESP32 para comparar.")
    with st.form("form_validacao", clear_on_submit=True):
        c1, c2 = st.columns(2)
        quantity = c1.selectbox("Grandeza", list(QUANTITY_PT),
                                format_func=lambda q: f"{QUANTITY_PT[q][0]} ({QUANTITY_PT[q][1]})")
        ref = c2.number_input("Valor do instrumento", min_value=0.0, value=0.0, step=0.1, format="%.3f")
        note = st.text_input("Observação (carga, instrumento...)", "")
        if st.form_submit_button("Registrar comparação"):
            if ref <= 0:
                banner("warn", "Digite o valor medido pelo instrumento.")
            else:
                body = {"device_id": ctx.device, "quantity": quantity, "reference": float(ref), "note": note or None}
                if _guard(ctx, lambda: ctx.api.post("/api/validations", json=body)):
                    rerun(ctx.auto)

    try:
        rows = ctx.api.get("/api/validations", device_id=ctx.device)
    except requests.RequestException as exc:
        banner("danger", f"Erro ao consultar validações: {exc}")
        return
    df = validation_dataframe(rows)
    if df.empty:
        banner("info", "Nenhuma comparação registrada ainda.")
        return

    summary = validation_summary(df)
    items = []
    for _, r in summary.iterrows():
        name = QUANTITY_PT[r["quantity"]][0]
        items.append((f"{name}: erro médio absoluto", f"{r['mape_pct']:.2f}% ({int(r['n'])} medidas)"))
        items.append((f"{name}: viés", f"{r['vies_pct']:+.2f}%"))
    cards(items)

    present = [q for q in QUANTITY_PT if q in set(df["quantity"])]
    q_sel = st.radio("Gráfico de", present, horizontal=True, key="val_q",
                     format_func=lambda q: QUANTITY_PT[q][0])
    st.plotly_chart(charts.validation_scatter(df, q_sel, ctx.theme), theme=None, key="val_scatter")
    table(validation_table(df).head(30))
    st.download_button("Baixar validação (CSV)", validation_csv(df), file_name=f"validacao_{ctx.device}.csv",
                       mime="text/csv", key="dl_val")

    with st.expander("Apagar um registro"):
        rid = st.selectbox("ID", list(df["id"]), key="val_del_id")
        if st.button("🗑 Apagar", key="val_del"):
            if _guard(ctx, lambda: ctx.api.delete(f"/api/validations/{int(rid)}")):
                rerun(ctx.auto)


# ----------------------------- Modelo -----------------------------
def model_tab(ctx, d):
    model = d["model"]
    if model["ready"]:
        cards([
            ("Estado", "Treinado"),
            ("Leituras no treino", str(model["n_samples"])),
            ("Contaminação", str(model["contamination"])),
        ])
        st.caption(f"Último treino: {model['trained_at']} (UTC). Leituras marcadas como anomalia real ficam fora do treino.")
    else:
        banner("warn", "Ainda não treinado. Treina sozinho ao juntar leituras suficientes, ou clique abaixo.")
    if st.button("Treinar agora", key="treinar"):
        try:
            info = ctx.api.post("/api/model/train")
            banner("ok", f"Modelo treinado com {info['n_samples']} leituras.")
        except requests.HTTPError as exc:
            banner("danger", exc.response.json().get("detail", str(exc)))
        except requests.RequestException as exc:
            banner("danger", str(exc))

    st.subheader("Avaliação pelos seus rótulos")
    try:
        ev = ctx.api.get("/api/model/evaluation", device_id=ctx.device)
    except requests.RequestException as exc:
        banner("danger", f"Erro ao consultar a avaliação: {exc}")
        return
    if not ev["labeled"]:
        banner("info", "Marque anomalias como  real ou  falso alarme na aba Anomalias para ver a precisão.")
        return

    def pct(x):
        return "—" if x is None else f"{x * 100:.0f}%"

    cards([
        ("Precisão", pct(ev["precision"])),
        ("Recall", pct(ev["recall"])),
        ("F1", pct(ev["f1"])),
        ("Leituras rotuladas", str(ev["labeled"])),
    ])
    st.caption("Precisão = das que o modelo marcou, quantas eram anomalia de verdade. "
               "Recall = das anomalias reais que você rotulou, quantas o modelo pegou "
               "(só é confiável se você rotular também as que ele deixou passar).")
    matrix = pd.DataFrame(
        {"Modelo marcou anomalia": [ev["tp"], ev["fp"]], "Modelo não marcou": [ev["fn"], ev["tn"]]},
        index=["Era anomalia real", "Era normal"],
    ).reset_index().rename(columns={"index": ""})
    table(matrix)
