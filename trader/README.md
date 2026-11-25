# Kenui Trader

Laboratório para encontrar e validar estratégias de day trade nas criptos mais voláteis da Binance.

## Passo 1: dados e backtest (este código)

- `kenui_trader/data.py` baixa velas históricas públicas da Binance (sem chave de API) e ranqueia as moedas mais voláteis com liquidez.
- `kenui_trader/backtest.py` simula operações vela a vela, de forma honesta:
  - o sinal de uma vela só é executado na abertura da vela seguinte (nada de "ver o futuro");
  - taxa de 0,1% e slippage de 0,05% em cada entrada e saída;
  - se stop e alvo são tocados na mesma vela, conta o stop (pior caso);
  - respeita o mínimo de US$ 5 por ordem da Binance e uma trava de perda diária.
- `walk_forward` otimiza parâmetros num pedaço do histórico e mede o resultado só no pedaço seguinte, que a estratégia nunca viu.
- `kenui_trader/strategies.py` tem quatro estratégias de referência (cruzamento de médias, rompimento de canal, reversão por RSI, compressão de volatilidade). Elas são a régua: qualquer ideia nova precisa vencer essas depois dos custos.

## Como rodar

```bash
cd trader
pip install -r requirements.txt
python -m pytest -q tests          # confere o simulador
python run_baselines.py            # ranqueia moedas, baixa histórico e testa as estratégias
```

O relatório sai em `data/baseline_report.csv`.

Observação: a Binance bloqueia acesso a partir dos EUA. Rode num computador ou servidor fora dos EUA, ou num ambiente de nuvem que libere `data.binance.vision` e `data-api.binance.vision`.

## Próximos passos

2. Caça à vantagem: livro de ordens, liquidações, listagens novas, sentimento, on-chain e modelos de ML.
3. Bot 24h com dinheiro fictício no servidor.
4. Dinheiro real com travas de risco e chave de API sem permissão de saque.
