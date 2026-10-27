"""Temas do dashboard: escuro e claro de alto contraste (CSS + cores dos graficos)."""
from string import Template

THEMES = {
    "dark": dict(
        bg="#0E1117", surface="#1A1F2B", field="#232A3A", text="#F5F7FA", muted="#B8C0CF",
        border="#3A4256", bw="1px", accent="#5AA9FF", accent_text="#001A33", focus="#FFD43B",
        ok="#4ADE80", ok_bg="#0F2E1C", warn="#FBBF24", warn_bg="#33270A",
        danger="#FF8A8A", danger_bg="#3A1214", info="#5AA9FF", info_bg="#10243D", fs="1rem",
    ),
    "light": dict(
        bg="#FFFFFF", surface="#F2F2F2", field="#FFFFFF", text="#000000", muted="#262626",
        border="#000000", bw="2px", accent="#0033CC", accent_text="#FFFFFF", focus="#FF6A00",
        ok="#004D00", ok_bg="#E3F6E3", warn="#6B3F00", warn_bg="#FFF0C2",
        danger="#8F0000", danger_bg="#FFE0E0", info="#002A99", info_bg="#E1E9FF", fs="1.06rem",
    ),
}

# cores dos graficos (Plotly)
PLOT = {
    "dark": dict(template="plotly_dark", text="#F5F7FA", grid="#3A4256", paper="rgba(0,0,0,0)",
                 voltage="#5AA9FF", current="#FFB347", power="#4ADE80", anomaly="#FF5C5C", width=1.8,
                 apparent="#C792EA", reactive="#FF9CC8", bar="#5AA9FF"),
    "light": dict(template="plotly_white", text="#000000", grid="#9A9A9A", paper="#FFFFFF",
                  voltage="#0033CC", current="#B34700", power="#006600", anomaly="#D00000", width=2.6,
                  apparent="#6A1B9A", reactive="#AD1457", bar="#0033CC"),
}

_CSS = Template(r"""
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stToolbar"] {
  background: $bg !important; color: $text !important; font-size: $fs;
}
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
  background: $surface !important; border-right: $bw solid $border;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp li, .stApp label, .stApp small,
.stApp [data-testid="stWidgetLabel"] p, .stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stCaptionContainer"] { color: $text !important; }
.stApp a { color: $accent !important; text-decoration: underline; }

input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"] {
  background: $field !important; color: $text !important; border-color: $border !important;
}
input, textarea { -webkit-text-fill-color: $text !important; }
[data-baseweb="select"] div, [data-baseweb="select"] span, [data-baseweb="select"] svg { color: $text !important; fill: $text !important; }
[data-baseweb="popover"] ul, [data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"] { background: $field !important; }
[data-baseweb="popover"] li, [data-baseweb="popover"] li * { color: $text !important; }

.stButton > button, .stDownloadButton > button {
  background: $accent !important; color: $accent_text !important; border: 2px solid $border !important;
  border-radius: 10px; font-weight: 700; min-height: 2.8rem; width: 100%;
}
.stButton > button *, .stDownloadButton > button * { color: $accent_text !important; }
:focus-visible { outline: 3px solid $focus !important; outline-offset: 2px; }

button[data-baseweb="tab"] p { color: $text !important; font-weight: 700; }
button[data-baseweb="tab"][aria-selected="true"] p { color: $accent !important; }
[data-baseweb="tab-highlight"] { background: $accent !important; height: 4px !important; }
[data-baseweb="tab-border"] { background: $border !important; }

[data-testid="stExpander"] details { border: $bw solid $border !important; background: $surface !important; border-radius: 10px; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: $text !important; }

.eg-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 6px 0 16px; }
.eg-card { background: $surface; border: $bw solid $border; border-radius: 12px; padding: 12px 14px; }
.eg-label { color: $muted; font-size: .85em; font-weight: 700; }
.eg-value { color: $text; font-size: 1.6em; font-weight: 800; line-height: 1.25; }

.stApp .eg-banner { border: 2px solid; border-radius: 10px; padding: 10px 14px; margin: 6px 0 12px; font-weight: 700; }
.stApp .eg-ok { color: $ok !important; background: $ok_bg; border-color: $ok; }
.stApp .eg-warn { color: $warn !important; background: $warn_bg; border-color: $warn; }
.stApp .eg-danger { color: $danger !important; background: $danger_bg; border-color: $danger; }
.stApp .eg-info { color: $info !important; background: $info_bg; border-color: $info; }

.eg-bar { background: $surface; border: $bw solid $border; border-radius: 10px; height: 22px; overflow: hidden; margin: 4px 0 4px; }
.eg-bar > div { background: $accent; height: 100%; }
.eg-bar.over > div { background: $danger; }
.eg-scroll { overflow-x: auto; margin-bottom: 10px; }
.eg-table { width: 100%; border-collapse: collapse; }
.eg-table th { background: $surface; color: $text; border: $bw solid $border; padding: 6px 10px; text-align: left; white-space: nowrap; }
.eg-table td { color: $text; border: $bw solid $border; padding: 6px 10px; white-space: nowrap; }
""")


def build_css(name: str) -> str:
    return "<style>" + _CSS.substitute(THEMES[name]) + "</style>"
