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

## Mesa proprietária (pasta `prop/`) — 2026-11-26

Objetivo: um robô que passe num desafio de mesa proprietária de 2 fases (meta de 8% e depois 5%, perda diária máxima de 5%, perda total máxima de 10%) e depois renda na conta financiada.

Estrutura:

- `prop/config/settings.py`: mercados, custos simulados, regras da mesa e limites de risco.
- `prop/data/data_loader.py`: velas de 15 minutos de jan/2023 a nov/2026. A nuvem só alcança a Binance, então cada mercado usa um substituto: EURUSDT para EUR/USD, PAXGUSDT (ouro tokenizado, correlação de 0,98 com o contrato de ouro) para XAU/USD e BTCUSDT. Fins de semana são removidos de euro e ouro.
- `prop/strategies/`: detector de regime (ADX, ATR, largura de Bollinger), Motor 1 (rompimento após compressão, Londres e Nova York), Motor 2 (reversão à média na sessão asiática) e o controlador híbrido. Cada motor pode rodar em 15 min, 1 h ou 4 h, com as ordens sempre simuladas nas velas de 15 min.
- `prop/risk/risk_manager.py`: risco fixo por operação, trava diária de 3%, trava total de 6%, metade do risco após 2 stops no dia, bloqueio em horário de notícia e após vela muito larga.
- `prop/backtest/engine.py`: simulação da conta vela a vela, compra e venda, com custo, swap, stop antes do alvo e pior caso dentro da vela para os limites da mesa.
- `prop/backtest/montecarlo.py`: desafio simulado milhares de vezes (fase 1, fase 2 e 6 meses de conta financiada).
- `prop/main.py`: ajusta parâmetros só nos primeiros 70% do histórico e julga nos 30% finais.

```bash
python -m prop.main --optimize     # reajusta os parâmetros (cerca de 6 minutos)
python -m prop.main                # usa prop/config/best_params.json
python -m prop.robustness          # mede o quanto o ajuste "decorou o passado"
python -m prop.candidates.listing_short
```

Resultado da versão 1 (fora da amostra, set/2025 a nov/2026, conta com os 3 mercados):

| Simulação | Trades | Retorno | Pior queda | Profit factor | Mesa |
|---|---|---|---|---|---|
| 1 Rompimento | 129 | -24,5% | -27,2% | 0,70 | reprovou |
| 2 Reversão | 186 | -24,2% | -25,7% | 0,75 | reprovou |
| 3 Híbrido | 46 | +1,9% | -5,7% | 1,08 | não bateu a meta |
| 4 Híbrido + travas | 45 | +0,9% | -4,0% | 1,07 | não bateu a meta |

- Em velas de 15 minutos o custo consome de 0,15 a 0,25 do risco de cada operação, e tudo perde. Em 1 h e 4 h o custo cai para poucos centésimos.
- O ajuste decorou o passado: das 576 configurações, o ranking de dentro da amostra quase não prevê o de fora (correlação de 0,19), e só 44% das lucrativas dentro continuaram lucrativas fora.
- Monte Carlo com as operações de fora da amostra: 19% de chance de passar a fase 1 em um ano e 8% de chegar à conta financiada. Valor esperado por tentativa: cerca de -US$ 47 para uma taxa de US$ 60.
- Régua: operações de cara ou coroa sem custo passam a fase 1 em 50% das vezes. Perder 0,05 do risco por operação derruba para 28%; ganhar 0,10 sobe para 89%. A trava total de 6% reduz a chance de passar, porque encerra tentativas que ainda poderiam se recuperar.

Candidato da pesquisa anterior nas regras da mesa (`prop/candidates/listing_short.py`): vender o contrato perpétuo 24 h após a listagem na Binance, segurar 7 dias, stop de 30%. Com 1% de risco: 190 operações, +0,28 do risco por operação (t = 4,2), pior queda de -8,9%. Começando o desafio em cada dia real desde 2023, passou a fase 1 em 83% dos inícios e as duas fases em 80%, mediana de 143 dias, sem nenhuma reprovação (o resto não bateu a meta em um ano). Ressalvas: a regra foi escolhida olhando esse mesmo histórico, o funding não está incluído, e ela exige uma mesa de cripto com contratos perpétuos e API.
