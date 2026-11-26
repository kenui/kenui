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

## Quant V5, versão final (pasta `prop/`) — 2026-11-26

Tudo roda com um comando (precisa de `pip install -r requirements-quant.txt`):

```bash
python -m prop.quant_main              # relatório completo e painel em prop/output/
python -m prop.quant_main --rebuild    # reajusta todos os modelos (cerca de 25 minutos, mais 40 do CPCV)
python -m prop.live.rehearsal          # ensaia o robô de listagem no histórico real
python -m prop.live.listing_paper      # robô de listagem com dinheiro de mentira
```

Peças:

- `prop/features/`, `prop/models/`, `prop/labeling/`: features estacionárias, microestrutura (Amihud, VPIN), diferenciação fracionária, Hurst, meia-vida OU, HMM de 3 regimes com probabilidades filtradas (sem olhar o futuro), rótulos de tripla barreira com limite de calor (MAE), ensemble XGBoost + regressão logística + extra trees com intervalo conformal.
- `prop/extensions/atemporal_aci.py`: assinaturas de caminho de ordem 3 (41 features) e o controlador conformal adaptativo (ACI). O ACI aprende com todo sinal cujo resultado já é conhecido, operado ou não.
- `prop/risk/`: controlador de Bellman para as fases do desafio, solver de saques para a conta financiada, CUSUM de deriva, trava diária de 3,2%.
- `prop/backtest/walk_forward.py`: treina em 6 meses, testa no mês seguinte, com purga e embargo. `prop/validation/`: CPCV, Deflated Sharpe e PBO.
- `prop/backtest/monte_carlo_prop.py`: 10.000 contas pela jornada inteira (Fase 1, Fase 2, 12 meses financiada), com bootstrap em blocos.
- `prop/persistence/state_store.py` (SQLite em modo WAL), `prop/execution/mt5_socket_bridge.py` e `prop/mql5/PropGuardV5_Executor.mq5`: ponte e robô executor para MetaTrader 5. O EA ainda não foi compilado nem testado num MetaTrader.
- `prop/live/listing_paper.py`: teste ao vivo com dinheiro de mentira do único alfa com vantagem medida, numa conta de desafio simulada.

Resultado (jan/2023 a nov/2026, 39 meses fora da amostra, EUR/USD, ouro e BTC por substitutos da Binance):

| Versão | Trades | Resultado médio por trade (em risco) | Aprovação nas 2 fases | Valor esperado por tentativa de US$ 50 |
|---|---|---|---|---|
| V1 sinais primários | 1.597 | -0,08 | 4% | -US$ 40 |
| V2 HMM + meta | 387 | -0,09 | 4% | -US$ 40 |
| V3 calibrado + fases | 44 | -0,05 | 9% | -US$ 38 |
| V4 conformal + Bellman | 465 | -0,09 | 1% | -US$ 48 |
| V5 base | 56 | +0,02 | 14% (em 7 anos) | -US$ 38 |
| V5 + assinaturas e ACI | 13 | -0,10 | não opera o suficiente | -US$ 50 |
| V5 + alfa de listagem | 190 | +0,24 | 99% (87% com metade da vantagem) | cerca de +US$ 1.100 (teórico) |

- Os sinais de rompimento e reversão em euro, ouro e BTC não têm vantagem depois dos custos, e nenhum filtro de aprendizado de máquina criou uma. Deflated Sharpe de todas as versões: 0. No CPCV, o V5 base perdeu nos 5 caminhos; com assinaturas e ACI, 2 de 5 positivos e média negativa.
- O ACI fez o que deve: percebeu que as probabilidades do modelo não se confirmavam e fechou a porta (13 operações em 3 anos).
- O controlador V5 funciona quando recebe um alfa de verdade. Com o short de listagem (custos e funding incluídos), começando um desafio em cada listagem real: 83% chegaram à conta financiada, nenhuma reprovação, 17% ficaram sem histórico suficiente, mediana de 124 dias. Com risco fixo de 1%: 78%.
- Ressalvas do alfa de listagem: regra escolhida entre 36 variantes no mesmo histórico (Deflated Sharpe 0,90, PBO 0,29, todas as 36 positivas); 2024 e 2026 foram fracos (+0,09 e +0,07 por trade); cerca de 50 operações por ano; exige mesa de cripto com contratos perpétuos, não serve para MetaTrader com euro e ouro.

## MetaTrader 5 com dados reais (pasta `prop/research/` e `prop/live/mt5_trend.py`) — 2026-11-26

Pergunta: dá para chegar a 90% a 96% de aprovação em mesa usando forex, ouro e índices no MetaTrader 5?
Resposta medida: não. O melhor resultado honesto ficou em cerca de 65%.

Como foi medido (`python -m prop.research.mt5_study <pasta com os CSV do MT5>`): 83 variantes de 5 famílias,
com spread, comissão e swap reais da corretora. Cada regra é escolhida só com dados antes de 2019 e julgada
de 2019 a 2026.

| Família | Sharpe antes de 2019 | Sharpe 2019 a 2026 | Aprova as 2 fases | Em até 12 meses |
|---|---|---|---|---|
| Tendência em ouro e prata, só compra (médias 50/200) | 0,56 | 0,59 | 65,5% | 45% |
| Reversão de movimento extremo em índices | 0,58 | 0,09 | 56,9% | 53% |
| Tendência em forex | 0,55 | -0,63 | 2,7% | 0,7% |
| Pares com filtro de Kalman (núcleo A da "V8") | negativo | negativo | | |
| Horário da semana | negativo | negativo | | |

O mapa de aprovação (`python -m prop.research.approval_map`) mostra o que seria preciso: Sharpe 1,5 para 95%.
Uma estratégia sem vantagem nenhuma já passa em cerca de um terço das tentativas, então parte dos números
acima é sorte. Os saques simulados supõem que a mesa sempre paga.

Robô para o MetaTrader 5 (roda no Windows, com o terminal aberto e logado; nunca vê a senha):

```
python -m prop.live.mt5_trend --solve C:\caminho\mt5data   # uma vez: política de tamanho com dados antes de 2019
python -m prop.live.mt5_trend                              # só mostra o plano
python -m prop.live.mt5_trend --live --reset               # começa a Fase 1 e envia ordens (conta demo)
python -m prop.live.mt5_trend --live --loop                # fica rodando
python -m prop.live.mt5_trend --mesa ftmo                  # regras em prop/config/prop_rules.json
```

Proteções: sem `--live` nenhuma ordem sai; conta que não é demo é recusada sem `--conta-real`; freio em 60% da
perda diária da mesa fecha tudo e trava o dia; cada posição leva stop no servidor; nada de ordens na virada do
dia nem com spread anormal; estado em SQLite (WAL). As regras das mesas no JSON são um resumo e precisam ser
conferidas no site de cada mesa.

## Short de listagens na Bybit, para mesa de cripto (`prop/live/listing_bybit.py`) — 2026-11-26

A única vantagem medida acima de 90% de aprovação é o short de moedas recém-listadas. Ela foi refeita com os
preços, as taxas e o financiamento da própria Bybit (`python -m prop.research.bybit_check`, que precisa rodar
de uma conexão de casa porque a Bybit bloqueia servidores de nuvem): 163 das 190 operações existiam na Bybit,
média de +0,287R (t = 4,3), positivo em 2023, 2024, 2025 e 2026, cerca de 3,8 operações por mês.

O robô segue as regras da Crypto Fund Trader (2 fases, 8% + 5%, perda de 5% no dia e 10% no total):

```
python -m prop.live.listing_bybit --check          # testa as conexões, não envia nada
python -m prop.live.listing_bybit                  # só mostra o plano
python -m prop.live.listing_bybit --live --loop    # conta DEMO da Bybit, fica rodando
python -m prop.live.listing_bybit --report
```

A chave de API vem das variáveis de ambiente `BYBIT_API_KEY` e `BYBIT_API_SECRET` (chave da conta demo, sem
permissão de saque). Nunca coloque a chave em arquivo do repositório. Sem `--conta-real` o robô só fala com a
API de demonstração.
