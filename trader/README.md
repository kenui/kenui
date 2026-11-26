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
| Mesmo sinal com ordem limite em pares FDUSD (taxa zero de maker) | Piora: a ordem só executa quando o preço continua caindo, e os pares são pouco líquidos. Fica ordem a mercado no par USDT. |
| Regra simples de repique pós-liquidação (queda forte + volume + funding/open interest) | Inconsistente: perde na pesquisa, só as versões mais extremas ficam positivas. O ML faz uma versão mais afiada disso. |
| Rompimento da faixa de abertura de Nova York | Perde: -0,22% por operação na pesquisa e -0,39% no período trancado (t = -5,9 e -5,1). |
| Cash-and-carry, funding negativo, arbitragem entre corretoras | Não testável na conta atual: a Binance não oferece futuros a residentes no Brasil. |

Como reproduzir:

```bash
python -m research.universe && python -m research.panel     # baixa os dados (~2 GB)
python -m research.scan                                      # varredura de sinais
python -m research.listings && python -m research.listings_short
python -m research.dataset && python -m research.ml          # ML no período de pesquisa
python -m research.rules                                     # operações e custos
python -m research.ml holdout                                # prova final (não reutilizar para ajustar nada)
```

## Passo 3: robô de papel (`paper_bot.py`)

Roda o candidato do passo 2 ao vivo com dinheiro fictício: a cada 5 minutos baixa dados públicos, calcula os mesmos sinais (teste `tests/test_live_parity.py` garante que batem com a pesquisa), e simula compra/venda no preço real de compra/venda com taxa de 0,075% por lado. Sem chave de API, sem ordens reais.

Instalar num servidor Ubuntu fora dos EUA (como root):

```bash
curl -fsSL https://raw.githubusercontent.com/kenui/kenui/master/trader/deploy/install.sh | bash
```

O robô roda com usuário próprio, sem abrir portas, limitado a meia CPU e 1,5 GB de RAM. Usa cerca de 0,65 GB e 5 segundos de CPU a cada 5 minutos. Ver o resultado: `sudo -u kenuibot /opt/kenui-trader/trader/.venv/bin/python /opt/kenui-trader/trader/paper_bot.py --report`. Remover tudo: `bash /opt/kenui-trader/trader/deploy/uninstall.sh`.

Ensaio sem rede: `python -m research.replay` confere que a previsão do robô é idêntica à da pesquisa e que a contabilidade bate com o backtest.

## Próximos passos

4. Dinheiro real com travas de risco e chave de API sem permissão de saque.

## Concentrated liquidity research (`defi/`) — 2026-11-26

Question: with US$ 60, do pool fees beat impermanent loss + gas + rebalancing costs
when a volatility forecast sets the range? Read-only research, no wallet.

Data: exact on-chain history from Base (archive RPC `mainnet.base.org`, one Multicall per
snapshot: `slot0`, `liquidity`, `feeGrowthGlobal0/1X128`), 370 days, 10-20 minute bars.
`feeGrowthGlobal` is the real fee paid per unit of in-range liquidity, so no volume/TVL guessing.

Key test (independent of range width): fees earned by one unit of in-range liquidity vs its
loss against simply holding the coins (`(Δ√p)²/√p`, i.e. about `return²/8`).

| pool | fee/loss 12 months | fee/loss holdout (Aug 25 - Nov 26) |
|---|---|---|
| Uniswap v3 Base WETH/USDC 0.05% | 0.92 | 0.81 |
| Uniswap v3 Base WETH/USDC 0.30% | 1.15 | 1.06 |
| Uniswap v3 Base cbBTC/USDC 0.05% | 0.84 | 0.77 |
| Aerodrome WETH/USDC, staked (AERO rewards / loss, Jul-Nov 2026 only) | 0.54 old pool, 1.07 new pool | - |
| Orca SOL/USDC 0.04% (approximation from DefiLlama fees, validated on Base: 0.89 vs exact 0.92) | ~0.9 | - |

Findings:
- Fees and loss are almost equal everywhere: the market prices liquidity efficiently.
- Next-4h volatility (corr 0.54-0.85) and fees (0.62-0.89) are both predictable out of sample,
  but they move together, so the fee/loss ratio is not: no quintile of "predicted good hours" is reliably above 1.
- Narrow or frequently re-centred ranges lose heavily (each exit locks in the loss); the least bad
  choice is a wide passive range, which ends within a few % of holding 50/50.
- Gas on Base is ~US$ 0.01 per transaction and is not the problem.

Run: `python -m defi.download`, `python -m defi.research <pool> [--holdout]`, `python -m defi.solana_proxy`.
The holdout has been looked at once; do not tune on it.
