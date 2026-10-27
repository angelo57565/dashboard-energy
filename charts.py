"""Gráficos Plotly seguindo o tema escolhido."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from theme import PLOT

SERIES = {
    "Tensão": ("voltage", "V"),
    "Corrente": ("current", "A"),
    "Potência": ("power", "W"),
    "Aparente": ("apparent", "VA"),
    "Reativa": ("reactive", "var"),
}
DEFAULT_ROWS = ["Tensão", "Corrente", "Potência"]


def _style(fig, theme: str, height: int):
    c = PLOT[theme]
    fig.update_layout(
        template=c["template"], paper_bgcolor=c["paper"], plot_bgcolor=c["paper"],
        font=dict(color=c["text"], size=14), height=height,
        margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=1.1),
    )
    fig.update_xaxes(gridcolor=c["grid"], linecolor=c["text"], linewidth=2, zeroline=False)
    fig.update_yaxes(gridcolor=c["grid"], linecolor=c["text"], linewidth=2, zeroline=False)
    return fig


def timeseries(df, which: str, mark_anomalies: bool, theme: str):
    c = PLOT[theme]
    names = DEFAULT_ROWS if which == "Tudo" else [which]
    fig = make_subplots(
        rows=len(names), cols=1, shared_xaxes=True, vertical_spacing=0.07,
        subplot_titles=[f"{n} ({SERIES[n][1]})" for n in names],
    )
    anom = df[df["is_anomaly"]]
    for row, name in enumerate(names, start=1):
        col = SERIES[name][0]
        color = c.get(col, c["voltage"])
        fig.add_trace(go.Scatter(x=df["created_at"], y=df[col], mode="lines", name=name, showlegend=False,
                                 line=dict(color=color, width=c["width"])), row=row, col=1)
        if mark_anomalies and not anom.empty:
            fig.add_trace(go.Scatter(x=anom["created_at"], y=anom[col], mode="markers", name="Anomalia",
                                     showlegend=(row == 1),
                                     marker=dict(color=c["anomaly"], size=11, symbol="x", line=dict(width=2))),
                          row=row, col=1)
    return _style(fig, theme, 230 + 200 * len(names))


def score_chart(df, theme: str):
    c = PLOT[theme]
    d = df.dropna(subset=["anomaly_score"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["created_at"], y=d["anomaly_score"], mode="lines", name="Score",
                             line=dict(color=c["voltage"], width=c["width"])))
    flagged = d[d["is_anomaly"]]
    if not flagged.empty:
        fig.add_trace(go.Scatter(x=flagged["created_at"], y=flagged["anomaly_score"], mode="markers",
                                 name="Anomalia", marker=dict(color=c["anomaly"], size=11, symbol="x",
                                                              line=dict(width=2))))
    fig.add_hline(y=0, line_dash="dash", line_color=c["text"], line_width=2,
                  annotation_text="abaixo de 0 = anomalia", annotation_position="bottom right")
    fig.update_layout(title="Score do modelo (menor = mais estranho)")
    return _style(fig, theme, 320)


def bars(x, y, theme: str, title: str, ytitle: str = "kWh"):
    c = PLOT[theme]
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=c["bar"]))
    fig.update_layout(title=title, yaxis_title=ytitle)
    return _style(fig, theme, 300)


def validation_scatter(df, quantity: str, theme: str):
    c = PLOT[theme]
    d = df[df["quantity"] == quantity]
    top = max(d["reference"].max(), d["measured"].max()) * 1.05
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, top], y=[0, top], mode="lines", name="Ideal (y = x)",
                             line=dict(color=c["text"], dash="dash", width=2)))
    fig.add_trace(go.Scatter(x=d["reference"], y=d["measured"], mode="markers", name="Medidas",
                             marker=dict(color=c["voltage"], size=11)))
    fig.update_layout(xaxis_title="Instrumento de referência", yaxis_title="ESP32")
    return _style(fig, theme, 360)


def rssi_chart(df, theme: str):
    c = PLOT[theme]
    d = df.dropna(subset=["rssi"])
    fig = go.Figure(go.Scatter(x=d["created_at"], y=d["rssi"], mode="lines", name="RSSI",
                               line=dict(color=c["power"], width=c["width"])))
    fig.update_layout(title="Sinal Wi-Fi (dBm, mais perto de 0 = melhor)")
    return _style(fig, theme, 280)
