# Diário de pesquisa do robô de mesa proprietária (V8)

Cada experimento entra aqui com o que foi testado, o resultado fora da amostra e a decisão.
Regras fixas: tudo o que é escolhido (regra, filtro, política de risco) é escolhido em dados
anteriores ao período de teste; custos incluem spread, deslize, comissão e swap com a noite
tripla; a taxa de aprovação vem de 10.000 contas simuladas sorteando somente dias fora da
amostra (blocos de 6 dias), Fase 1 e Fase 2, perda diária de 5% e perda total de 10%.

Limite conhecido dos dados: os arquivos do MetaTrader 5 guardam um spread por barra, não cada
tick. Onde o spread da barra é usado, ele nunca fica abaixo da mediana do ativo e leva 25% de
deslize por cima.

Como reproduzir (a partir de `trader/`, com a pasta de dados exportada do MT5):

    python -m prop.research.nucleo_a <pasta>            # experimento 1
    python -m prop.research.nucleo_a <pasta> --seletivo # experimento 2
    python -m prop.research.stage2 <pasta>              # marco do Estágio 2 e Hipótese 1

---

## Experimento 1: Núcleo A, cestas cointegradas com Kalman e Ornstein-Uhlenbeck (27/11/2026)

**O que foi testado.** 20 cestas (pares e trios de forex, ouro/prata e índices), barras de 1 hora,
2010 a 2026. Para cada cesta, uma regressão dinâmica `y_t = a_t + b_t · x_t + e_t` com `a_t, b_t`
seguindo passeio aleatório (filtro de Kalman). O sinal é o erro de previsão `e_t` dividido pelo
seu desvio-padrão móvel (`z_t`). Entra contra o desvio quando `|z| > entrada`, sai em `|z| < 0,5`,
stop em `|z| > 4` ou 120 horas. Walk-forward: 42 meses calibram (teste de Engle-Granger a 10%,
meia-vida do spread de até 120 horas, 30 trades e resultado líquido positivo, melhor de uma grade
3 x 3) e os 18 meses seguintes são operados às cegas. Sinal com barras fechadas, execução na
abertura da barra seguinte.

**Resultado fora da amostra.**

| Métrica | Valor |
|---|---|
| Trades | 314 |
| Acerto líquido | 62,7% |
| Resultado médio bruto / líquido | +0,125R / -0,026R |
| Profit factor | 0,93 |
| Sharpe anual (treino / teste) | 0,54 / -0,06 |
| Aprovação Fase 1 + Fase 2 | 25,3% |
| Mesma simulação com média zero | 29,4% |

**Por que falhou.** O custo médio por trade (0,151R) é maior que a vantagem bruta (0,125R). O
ganho médio é 0,56 da perda média, então seria preciso acertar 64% para empatar. A cointegração
é instável: em 4 das 10 janelas nenhuma cesta passou no teste.

**Decisão: descartado.**

## Experimento 2: Núcleo A com abstinência seletiva (27/11/2026)

**O que foi testado.** O mesmo motor, entrando só com `|z|` de 2,5 a 3,5 e somente quando o
movimento esperado até a média vale ao menos 5 vezes o custo de ida e volta; stop 2 desvios além
da entrada.

**Resultado fora da amostra.** 382 trades, acerto líquido 56,8%, bruto +0,091R, líquido -0,055R,
Sharpe -0,21, aprovação 15,3% (média zero: 27,3%).

**Por que falhou.** Desvio maior nessas cestas costuma ser mudança real de preço, não exagero que
volta. Filtrar não cria vantagem que o sinal bruto não tem.

**Decisão: descartado. O Núcleo A não deve ser reajustado nestes dados.**

---

## Marco do Estágio 2: tendência de ouro e prata com as guardas de mesa (28/11/2026)

**Motor base.** Comprado em XAUUSD e XAGUSD enquanto a média exponencial de 50 dias está acima da
de 200; posição = 1% / volatilidade diária (teto 3x); peso igual. Regra escolhida com dados até
2018, julgada de 2019 a 2026. O tamanho da conta em cada dia vem de uma política de Bellman
resolvida somente com os dias anteriores a 2019.

**Sobre o número de 65,5%.** Ele veio do estudo de 26/11, com 4.000 contas e contando um dia de
calendário por dia de pregão. Refeito aqui com 10.000 contas e dias de calendário reais, o mesmo
motor dá **61,1%** (linha A). A diferença é da medição, não do motor. A comparação justa das
hipóteses é contra a linha C.

**Guardas aplicadas.**
- Caminho real dentro do dia, pelas mínimas das barras de 1 hora (antes era um pior ponto suposto).
- Ordens depois do rollover: execução na abertura da barra das 01:00 do servidor (17:00 de Nova
  York é 00:00 no relógio da corretora), com o spread dessa barra.
- Swap por noite com a noite tripla de quarta-feira.
- Corte da conta a 60% da perda diária (3% de 5%), com 5% de escorregão no corte.
- Metas de cada mesa lidas de `prop/config/prop_rules.json`.

**Resultado fora da amostra (2019 a 2026, Sharpe 0,58, 14 trades, acerto 28,6%, profit factor 2,70).**

| Caso | Mesa | Aprovação | Em 12 meses | Reprova perda diária | Reprova perda total | Dias (mediana) | Saques 12 meses |
|---|---|---|---|---|---|---|---|
| A. motor do estudo anterior | 8% + 5% | 61,1% | 37,6% | 0,0% | 36,9% | 289 | US$ 337 |
| A. motor do estudo anterior | FTMO / The5ers 10% + 5% | 59,0% | 31,3% | 0,0% | 38,2% | 343 | US$ 321 |
| B. A + caminho real + rollover + swap triplo | 8% + 5% | 64,7% | 40,0% | 0,0% | 33,9% | 290 | US$ 363 |
| B. idem | FTMO / The5ers | 62,4% | 33,2% | 0,0% | 35,2% | 342 | US$ 347 |
| **C. B + corte a 60% da perda diária** | 8% + 5% | **65,1%** | 40,3% | 0,0% | 33,5% | 289 | US$ 362 |
| **C. idem** | FTMO / The5ers | **62,7%** | 33,6% | 0,0% | 34,9% | 341 | US$ 346 |

**Leitura.** As guardas não custaram aprovação e as reprovações por perda diária ficaram em zero.
Sem o corte, o pior dia de 2019 a 2026 no maior tamanho da política teria sido -7,2%, acima do
limite de 5%, então o corte é necessário. O que reprova é a perda total de 10%: com Sharpe perto
de 0,6, um terço das contas encontra uma queda de 10% antes de somar a meta. Guarda nenhuma muda
isso; só uma vantagem maior ou um tamanho menor (mais tempo) mudam.

Poucos trades (14 em sete anos, porque a tendência fica meses comprada) significam que acerto e
profit factor têm pouca precisão estatística; o Sharpe diário é a medida mais confiável aqui.

**Decisão: aprovado como base (linha C). Meta do Estágio 2 de 65% atingida no limite na regra de
8% + 5% (65,1%) e não atingida na regra da FTMO (62,7%).**

## Hipótese 1: regimes por expoente de Hurst e volatilidade (28/11/2026)

**O que foi testado.** Hurst móvel de 250 dias pela lei de escala
`desvio(p_t - p_{t-k}) ~ k^H`, com `k` = 1, 2, 4, 8, 16 (H = 0,5 é passeio aleatório; acima disso
há memória direcional). Volatilidade de 20 dias comparada com os próprios 500 dias anteriores.
O motor só fica comprado quando o filtro permite. Cinco variantes, todas calculadas com dados até
o dia anterior.

**Resultado.**

| Filtro | Sharpe antes de 2019 | Sharpe 2019-2026 | Trades | Acerto | Profit factor | Aprovação 8% + 5% | Aprovação FTMO |
|---|---|---|---|---|---|---|---|
| sem filtro (linha C) | 0,51 | 0,58 | 14 | 28,6% | 2,70 | 65,1% | 62,7% |
| Hurst > 0,50 | 0,14 | 0,32 | 16 | 50,0% | 1,88 | 50,2% | 43,9% |
| Hurst > 0,55 | -0,31 | 0,43 | 5 | 60,0% | 4,73 | 50,9% | 45,4% |
| volatilidade abaixo do percentil 90 | 0,50 | 0,42 | 61 | 41,0% | 1,48 | 53,9% | 50,5% |
| Hurst > 0,50 e volatilidade < p90 | 0,06 | 0,26 | 27 | 48,1% | 1,48 | 42,0% | 36,3% |

**Por que falhou.** Nenhum filtro ganha do motor puro antes de 2019, então nenhum seria escolhido
sem olhar o futuro, e todos também perdem depois. O Hurst de 250 dias é ruidoso e atrasado: liga
depois que boa parte da tendência já andou e deixa o motor fora em 75% a 96% dos dias, incluindo
as grandes altas do ouro. O filtro de volatilidade tira o motor justamente dos dias de maior
movimento a favor e multiplica as entradas e saídas (61 trades contra 14), pagando mais custo.
Os filtros de Hurst sobem o acerto por trade, mas com 5 a 16 trades isso não tem significância.

**Decisão: descartada.** A linha C continua sendo a base.
