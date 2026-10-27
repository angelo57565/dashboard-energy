"""Funcoes de dados do dashboard (sem Streamlit, faceis de testar)."""
import math

import pandas as pd

TZ = "America/Sao_Paulo"

COLUMNS_PT = {
    "id": "ID",
    "created_at": "Horário",
    "device_id": "Dispositivo",
    "voltage": "Tensão (V)",
    "current": "Corrente (A)",
    "power": "Potência (W)",
    "power_factor": "FP",
    "frequency": "Freq. (Hz)",
    "anomaly_score": "Score",
    "energy": "Energia (kWh)",
    "is_anomaly": "Anomalia",
}

FEATURE_PT = {
    "voltage": ("Tensão", "V"),
    "current": ("Corrente", "A"),
    "power": ("Potência", "W"),
    "power_factor": ("FP", ""),
    "frequency": ("Frequência", "Hz"),
}
QUANTITY_PT = {"voltage": ("Tensão", "V"), "current": ("Corrente", "A"), "power": ("Potência", "W")}
FEEDBACK_PT = {"real": "✅ real", "false": "❌ falso alarme"}


# ----------------------------- leituras -----------------------------
def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Lista de leituras da API -> DataFrame com horário em Brasília e potências S e Q."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_convert(TZ)
    df = df.sort_values("created_at").reset_index(drop=True)
    return add_power_columns(df)


def add_power_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Potência aparente (VA) = V·I e reativa (var) = raiz(S² − P²)."""
    df["apparent"] = df["voltage"] * df["current"]
    df["reactive"] = (df["apparent"] ** 2 - df["power"] ** 2).clip(lower=0) ** 0.5
    return df


def reasons_text(reasons: list[dict] | None, top: int = 2) -> str:
    if not reasons:
        return ""
    parts = []
    for r in reasons[:top]:
        name, unit = FEATURE_PT.get(r["feature"], (r["feature"], ""))
        direction = "acima" if r["z"] >= 0 else "abaixo"
        parts.append(f"{name} {r['value']:.2f} {unit} (normal ≈ {r['mean']:.2f}; {abs(r['z']):.0f}σ {direction})".replace("  ", " "))
    return "; ".join(parts)


def anomalies_table(rows: list[dict]) -> pd.DataFrame:
    df = to_dataframe(rows)
    if df.empty:
        return df
    df = df.sort_values("created_at", ascending=False)
    df["created_at"] = df["created_at"].dt.strftime("%d/%m %H:%M:%S")
    df["motivo"] = [reasons_text(r) for r in df["reasons"]] if "reasons" in df else ""
    df["rotulo"] = df["feedback"].map(FEEDBACK_PT).fillna("—") if "feedback" in df else "—"
    cols = ["id", "created_at", "voltage", "current", "power", "power_factor", "motivo", "rotulo"]
    out = df[cols].rename(columns={**COLUMNS_PT, "motivo": "Motivo", "rotulo": "Rótulo"})
    return out.round({"Tensão (V)": 1, "Corrente (A)": 2, "Potência (W)": 1, "FP": 2})


def readings_csv(rows: list[dict]) -> bytes:
    """CSV pronto para o Excel em português (separador ; e vírgula decimal)."""
    df = to_dataframe(rows)
    if df.empty:
        return b""
    df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    cols = ["id", "created_at", "device_id", "voltage", "current", "power", "apparent", "reactive",
            "energy", "frequency", "power_factor", "is_anomaly", "anomaly_score"]
    out = df[cols].rename(columns={**COLUMNS_PT, "apparent": "Aparente (VA)", "reactive": "Reativa (var)"})
    out["Anomalia"] = out["Anomalia"].map({True: "sim", False: "não"})
    return out.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def age_seconds(created_at_iso: str) -> float:
    ts = pd.to_datetime(created_at_iso, utc=True)
    return (pd.Timestamp.now(tz="UTC") - ts).total_seconds()


def human_age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 86400:
        return f"{seconds // 3600} h {(seconds % 3600) // 60} min"
    return f"{seconds // 86400} d {(seconds % 86400) // 3600} h"


# ----------------------------- consumo -----------------------------
def hourly_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["period"] = pd.to_datetime(df["period"], utc=True).dt.tz_convert(TZ)
    return df.sort_values("period").reset_index(drop=True)


def daily_consumption(hourly: pd.DataFrame) -> pd.DataFrame:
    d = hourly.copy()
    d["day"] = d["period"].dt.normalize()
    return d.groupby("day", as_index=False)["kwh"].sum()


def today_vs_yesterday(hourly: pd.DataFrame, now_local: pd.Timestamp) -> tuple[float, float, float]:
    """(hoje até agora, ontem até a mesma hora, ontem inteiro) em kWh."""
    today = now_local.normalize()
    yday = today - pd.Timedelta(days=1)
    t = hourly.loc[hourly["period"] >= today, "kwh"].sum()
    y_total = hourly.loc[(hourly["period"] >= yday) & (hourly["period"] < today), "kwh"].sum()
    y_same = hourly.loc[(hourly["period"] >= yday) & (hourly["period"] < yday + (now_local - today)), "kwh"].sum()
    return float(t), float(y_same), float(y_total)


def month_projection(hourly: pd.DataFrame, now_local: pd.Timestamp) -> tuple[float, float, int]:
    """(kWh no mês até agora, projeção para o mês inteiro, dias do mês)."""
    start = now_local.normalize().replace(day=1)
    so_far = float(hourly.loc[hourly["period"] >= start, "kwh"].sum())
    days_in_month = int(now_local.days_in_month)
    elapsed_days = max((now_local - start).total_seconds() / 86400.0, 1 / 24)
    return so_far, so_far / elapsed_days * days_in_month, days_in_month


# ----------------------------- validação -----------------------------
def validation_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_convert(TZ)
    df["erro"] = df["measured"] - df["reference"]
    df["erro_pct"] = df["erro"] / df["reference"] * 100.0
    return df.sort_values("created_at", ascending=False).reset_index(drop=True)


def validation_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Por grandeza: nº de medidas, erro médio (viés) e erro absoluto médio percentual (MAPE)."""
    if df.empty:
        return df
    g = df.groupby("quantity")
    out = pd.DataFrame({
        "n": g.size(),
        "vies_pct": g["erro_pct"].mean(),
        "mape_pct": g["erro_pct"].apply(lambda s: s.abs().mean()),
    }).reset_index()
    return out


def validation_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = pd.DataFrame({
        "ID": df["id"],
        "Horário": df["created_at"].dt.strftime("%d/%m %H:%M"),
        "Grandeza": df["quantity"].map(lambda q: QUANTITY_PT[q][0] + f" ({QUANTITY_PT[q][1]})"),
        "Referência": df["reference"].round(3),
        "ESP32": df["measured"].round(3),
        "Erro": df["erro"].round(3),
        "Erro (%)": df["erro_pct"].round(2),
        "Obs.": df["note"].fillna(""),
    })
    return out


def validation_csv(df: pd.DataFrame) -> bytes:
    if df.empty:
        return b""
    out = validation_table(df)
    return out.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


# ----------------------------- saúde -----------------------------
def rssi_label(rssi: int | None) -> str:
    if rssi is None:
        return "—"
    if rssi >= -60:
        return "excelente"
    if rssi >= -70:
        return "bom"
    if rssi >= -80:
        return "fraco"
    return "ruim"


def availability_pct(n_readings: int, hours: float, interval_s: float) -> float:
    expected = hours * 3600.0 / max(interval_s, 1.0)
    return min(100.0, 100.0 * n_readings / expected) if expected > 0 else 0.0


def median_interval_s(df: pd.DataFrame) -> float | None:
    if df is None or len(df) < 3:
        return None
    return float(df["created_at"].diff().dt.total_seconds().median())


def fmt_pct(x: float | None, nd: int = 1) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}%"
