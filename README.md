# EnergyGuard – Dashboard (Streamlit) v2

Lê tudo pela API FastAPI (não acessa o MySQL direto). Precisa do backend v2.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export API_URL=http://localhost:8000   # Windows (cmd): set API_URL=http://localhost:8000
export API_KEY=a-mesma-chave-do-backend
streamlit run app.py
```

Abre em http://localhost:8501.

## Barra lateral

Tema (escuro / claro de alto contraste) · Dispositivo · Período · Atualização automática + "Atualizar agora" ·
⚙️ Configurações (tarifa, tensão nominal 127/220 V, meta mensal em kWh, intervalo de envio; ficam salvas no backend) ·
🔌 Conexão (URL e chave da API).

## Abas

| Aba | O que tem |
|---|---|
| 📊 Visão geral | Valores atuais (incl. potência aparente e reativa) e resumo do período com consumo e custo |
| 📈 Gráficos | Tensão, corrente, potência, aparente e reativa; anomalias marcadas; CSV |
| 🔋 Consumo | kWh por hora e por dia, hoje × ontem, projeção do mês, custo e barra da meta mensal |
| ⚠️ Anomalias | Score do modelo, motivo de cada anomalia, botões ✅ real / ❌ falso alarme, rotular qualquer leitura |
| 🔔 Alertas | Regras por limite, regras sugeridas, histórico, teste de Telegram/e-mail |
| 🩺 Qualidade e saúde | % do tempo com tensão/frequência fora da faixa; Wi-Fi, uptime, falhas de envio e disponibilidade do ESP32 |
| 🧪 Validação | Compara o ESP32 com multímetro/alicate: erro médio, viés, gráfico y = x e CSV |
| 🤖 Modelo | Estado, treinar agora, precisão/recall/F1 e matriz de confusão pelos seus rótulos |

## Tema

O tema escolhido fica no endereço (`?tema=claro`). As cores vêm de `theme.py`.

## Arquivos

`app.py` (layout e dados) · `tabs.py` (conteúdo das abas) · `charts.py` · `ui.py` · `client.py` · `helpers.py` · `theme.py`
