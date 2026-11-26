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

## Passo 2: caça à vantagem (pasta `research/`)

Dados: 40 moedas mais negociadas em dez/2024 (escolhidas sem olhar o futuro), velas de 5 minutos de jan/2025 a nov/2026, spot e futuros: fluxo de compra/venda agressiva, prêmio do perpétuo, funding, open interest, razões long/short. Pesquisa em jan/2025 a jun/2026; jul a nov/2026 ficou trancado e só foi aberto uma vez, no fim.

Custos usados: spot com taxa em BNB, 0,075% + 0,03% de spread por lado (0,21% ida e volta). Na Binance, para conta comum, ordem limite paga a mesma taxa que ordem a mercado no spot, então ela só economiza o spread.

| Ideia | Resultado |
|---|---|
| ~60 sinais x 5 prazos (1.625 testes) | Vários efeitos reais, mas de ~1 ponto-base por operação em 5 min. O custo é 20x maior. |
| ML (LightGBM) prevendo 1h, 4h e 24h, treinado mês a mês só com o passado | Operar sempre que o modelo está otimista perde dinheiro depois dos custos. |
| ML só nos momentos extremos (previsão de 1h acima de +0,5%) | Candidato. Pesquisa: +18,8% em 12 meses, 406 operações, pior queda -18%. Prova final trancada: +8,8% em 5 meses (mercado -7,5%), 87 operações em 16 dias, média +0,49% por operação já com custos, t=2,4. Amostra pequena. |
| Vender (short) moedas recém-listadas 24h após a listagem, 7 dias, stop de 30% | +7% por operação depois de custos e funding, 190 casos desde 2023, t=3,7. Exige futuros ou margem (não é spot) e não é day trade. |
| Comprar listagens novas | Perde: em média -7% contra o BTC na primeira semana. |

Como reproduzir:

```bash
python -m research.universe && python -m research.panel     # baixa os dados (~2 GB)
python -m research.scan                                      # varredura de sinais
python -m research.listings && python -m research.listings_short
python -m research.dataset && python -m research.ml          # ML no período de pesquisa
python -m research.rules                                     # operações e custos
python -m research.ml holdout                                # prova final (não reutilizar para ajustar nada)
```

## Próximos passos

3. Bot 24h com dinheiro fictício no servidor.
4. Dinheiro real com travas de risco e chave de API sem permissão de saque.
