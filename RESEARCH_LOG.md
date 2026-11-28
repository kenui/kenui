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
    python -m prop.research.hypotheses <pasta>          # Hipóteses 2, 3 e 4 (precisa de lightgbm)
    python -m prop.research.new_engines <pasta>         # busca de outro motor
    python -m prop.fronts.portfolio <pasta>             # V9: Frentes 2 e 3 e o portão do portfólio

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

**Frequência e tempo (linha C).** 0,15 trade por mês (14 entradas completas em quase 8 anos; o
lote é reajustado em cerca de 11% dos dias). Tempo médio até a meta da Fase 1: 234 dias na regra
de 8% e 292 dias na de 10%. Tempo médio até aprovar nas duas fases: 369 e 422 dias.

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

---

As três hipóteses abaixo mudam uma coisa de cada vez sobre a linha C e passam pela mesma jornada.
Colunas de tempo em dias de calendário, média das contas que chegaram lá. "Sem decisão" são as
contas que em 4 anos simulados não aprovaram nem reprovaram.

## Hipótese 2: meta-labeling com predição conformal (28/11/2026)

**O que foi testado.** Para cada dia em que o motor está comprado em um metal, um LightGBM raso
(200 árvores, profundidade 3, 50 amostras por folha, regularização L2 = 5) estima
`p = P(retorno dos próximos 5 dias > 0)` a partir de 11 variáveis conhecidas no fechamento
(distância entre as médias, retornos de 20/60/120 dias em unidades de volatilidade, razão de
volatilidade, Hurst, distância da máxima de 50 dias, razão ouro/prata, tendência do outro metal,
esticamento sobre a média, dia da semana). Walk-forward anual desde 2010: o modelo de cada ano só
vê rótulos já encerrados. Predição conformal por divisão: os 25% finais do treino calibram o
escore `1 - p(classe verdadeira)`; com cobertura de 80% sai um conjunto de classes possíveis.
"Estrito" fica comprado só se o conjunto é {ganho}; "leve" sai só se o conjunto é {perda}.

| Caso | Sharpe 2010-18 (walk-forward) | Sharpe 2019-26 | Trades/mês | Acerto | Profit factor | Aprovação 8%+5% | Aprovação FTMO | Dias até meta F1 (8% / 10%) | Sem decisão |
|---|---|---|---|---|---|---|---|---|---|
| base (linha C) | 0,51 | 0,58 | 0,15 | 28,6% | 2,70 | 65,1% | 62,7% | 234 / 292 | 1,4% |
| H2 estrito | 0,55 | 0,47 | 1,37 | 56,9% | 1,75 | 47,9% | 38,9% | 660 / 763 | 50,3% |
| H2 leve | 0,53 | 0,39 | 1,58 | 59,3% | 1,41 | 57,3% | 53,4% | 339 / 417 | 9,0% |

**Por que falhou.** O filtro dobra o acerto por trade (de 29% para 57-59%), mas faz isso cortando
uma tendência longa em 130 a 150 pedaços curtos: os ganhos grandes, que pagam a estratégia de
tendência, desaparecem (profit factor cai de 2,70 para 1,41-1,75) e o custo de entrar e sair é
pago dez vezes mais. Antes de 2019 o filtro parecia ajudar um pouco (0,55 contra 0,51) e teria
sido escolhido; depois de 2019 ele piorou. É o padrão de sobreajuste que a validação cega existe
para pegar. Taxa de acerto alta não é o mesmo que taxa de aprovação alta.

**Decisão: descartada.**

## Hipótese 3: tamanho de posição (28/11/2026)

**O que foi testado.**
- *Volatilidade de queda:* posição = 1% / `sqrt(2 · média móvel de min(r, 0)²)`, isto é, o tamanho
  é medido só pelos dias de queda. Altas fortes não encolhem a posição; quedas fortes encolhem.
- *Política paciente:* a mesma programação dinâmica (Bellman) com menu de risco mais fino
  (0,05% a 0,6% ao dia) e desconto 0,9997 no lugar de 0,999, ou seja, menos pressa.
- *Tamanho fixo:* 0,2%, 0,3% e 0,4% da conta por dia, sem política, como referência.

| Caso | Sharpe 2019-26 | Aprovação 8%+5% | Aprovação FTMO | Em 12 meses (8%+5%) | Reprova perda total | Sem decisão | Dias até meta F1 (8% / 10%) | Dias até aprovar | Saques 12 meses |
|---|---|---|---|---|---|---|---|---|---|
| base (linha C) | 0,58 | 65,1% | 62,7% | 40,3% | 33,5% | 1,4% | 234 / 292 | 369 | US$ 362 |
| volatilidade de queda | 0,60 | **66,8%** | **64,5%** | 41,1% | 31,8% | 1,4% | 231 / 294 | 370 | US$ 399 |
| política paciente | 0,58 | **68,1%** | **64,6%** | 30,9% | 11,3% | 20,6% | 331 / 383 | 511 | US$ 362 |
| fixo 0,2% | 0,58 | 40,3% | 30,0% | 0,8% | 4,8% | 54,9% | 718 / 833 | 970 | US$ 79 |
| fixo 0,3% | 0,58 | 62,5% | 55,6% | 8,0% | 18,3% | 19,2% | 521 / 622 | 756 | US$ 234 |
| fixo 0,4% | 0,58 | 64,9% | 61,3% | 20,5% | 31,2% | 3,9% | 372 / 463 | 569 | US$ 359 |

Trades por mês: 0,15 em todos (o tamanho não muda as entradas). Reprovação por perda diária: 0,0%
em todos.

**Leitura.**
- A volatilidade de queda ganha 1,7 ponto nas duas mesas, reduz a maior queda (47,5 contra 51,8
  dias normais) e não custa tempo. O ganho é pequeno: o erro da simulação é de cerca de 0,5 ponto
  e o período de teste é um só, então ele é real na medição mas não é uma certeza.
- A política paciente troca reprovação por espera: a perda total cai de 33,5% para 11,3%, mas
  20,6% das contas ainda estão sem decisão depois de 4 anos, a aprovação em 12 meses cai de 40,3%
  para 30,9% e a meta da Fase 1 demora 331 dias em vez de 234. A aprovação de 68,1% é um piso (parte
  das contas sem decisão ainda aprovaria), mas o preço é tempo.
- O tamanho fixo perde para a política de Bellman em tudo: a política rende mais porque arrisca
  mais longe dos limites e menos perto deles.

**Decisão: volatilidade de queda aprovada (nova base: 66,8% / 64,5%). Política paciente fica como
opção para quem aceita esperar mais; não é ganho de graça.**

## Hipótese 4: ouro e prata lidos juntos (28/11/2026)

**O que foi testado.** Duas ideias da estrutura própria dos dois metais. *Confirmação:* metade do
tamanho quando só um dos dois está em tendência de alta (alta de um metal sem o outro costuma ser
mais frágil). *Esticado:* metade do tamanho quando o preço está mais de 2 desvios acima da média
de 50 dias, `(P / EMA50 - 1) / (vol · sqrt(50)) > 2`, uma saída parcial adaptativa.

| Caso | Sharpe antes de 2019 | Sharpe 2019-26 | Aprovação 8%+5% | Aprovação FTMO |
|---|---|---|---|---|
| base (linha C) | 0,51 | 0,58 | 65,1% | 62,7% |
| confirmação ouro/prata | 0,51 | 0,50 | 60,1% | 57,9% |
| esticado acima da média | 0,50 | 0,59 | 64,8% | 62,7% |
| confirmação + esticado | 0,51 | 0,51 | 60,4% | 58,0% |

**Por que falhou.** De 2019 a 2026 o ouro subiu muito mais e por mais tempo que a prata; exigir
confirmação da prata cortou pela metade a posição justamente nas altas do ouro. Reduzir quando
está esticado não muda nada de mensurável: tendências fortes ficam esticadas por muito tempo e
a redução devolve o que economiza.

**Decisão: descartada.**

---

## Situação depois de quatro hipóteses (28/11/2026)

| | Aprovação 8%+5% | Aprovação FTMO |
|---|---|---|
| Marco (linha C) | 65,1% | 62,7% |
| Melhor resultado mantido (volatilidade de queda) | 66,8% | 64,5% |
| Meta do Estágio 3 | 85% a 90% | 85% a 90% |

Nenhuma técnica de filtro (Hurst, volatilidade, meta-labeling conformal, leitura cruzada dos
metais) aumentou a vantagem do motor fora da amostra; três delas a reduziram. O único ganho veio
de dimensionar melhor a posição, e ele é de 1 a 3 pontos. A distância até 85-90% não é de
blindagem nem de filtro: pela relação medida em 26/11 entre Sharpe e aprovação, ela pede um motor
com Sharpe perto de 1,5, e o melhor motor comprovado nestes mercados tem 0,6. Insistir em mais
variantes sobre os mesmos sete anos de teste passaria a ajustar o método ao período de teste.

---

## Busca de outro motor em MT5: famílias ainda não testadas (28/11/2026)

**O que foi testado.** 16 variantes novas, em barras diárias, com o mesmo protocolo (decisão no
fechamento, execução na abertura seguinte, custos da corretora, escolha antes de 2019).
- *Momento relativo:* comprado no terço mais forte e vendido no terço mais fraco de um grupo
  (8 índices; 7 moedas contra o dólar), janelas de 60/126/252 e 20/60/126 dias.
- *Reversão relativa:* o contrário, em 1, 3 e 5 dias.
- *Prêmio:* exposição comprada com alvo de volatilidade, sem sinal (US500; índices dos EUA; todos
  os índices; ouro).
Carry de moedas ficou de fora de propósito: os arquivos só têm as taxas de swap de hoje, e
ordenar o passado por elas usaria informação do futuro.

| Família | Melhor antes de 2019 | Sharpe antes | Sharpe 2019-26 |
|---|---|---|---|
| Momento relativo, índices | 126 dias | -0,21 | -0,94 |
| Momento relativo, moedas | 60 dias | -0,20 | -0,71 |
| Reversão relativa, índices | 1 dia | -1,37 | -1,65 |
| Reversão relativa, moedas | 5 dias | -0,24 | -0,49 |
| Prêmio, US500 | sem parâmetro | 0,28 | 0,46 |
| Prêmio, índices dos EUA | sem parâmetro | 0,25 | 0,27 |
| Prêmio, todos os índices | sem parâmetro | -0,09 | 0,35 |
| Prêmio, ouro | sem parâmetro | 0,36 | 0,88 |

**Leitura.** Momento e reversão relativos perdem nos dois períodos: o que existe de efeito é menor
que o giro que ele exige. O prêmio de ações é positivo nos dois períodos, mas pequeno depois do
financiamento do CFD (cerca de 6% ao ano embutidos no swap). Juntar o prêmio do US500 à tendência
dos metais não melhorou o conjunto antes de 2019 de forma confiável e, na jornada, baixou a
aprovação (55,1% contra 62,9% da base na mesma medição), porque aumenta a queda máxima. O prêmio
do ouro tem correlação 0,81 com a Frente 1, então não é uma frente nova.

**Decisão: nenhuma das 16 variantes aprovada.** Somando os estudos anteriores, são 198 variantes
testadas nestes mercados.

---

# V9: portfólio de várias frentes (28/11/2026)

Estrutura no repositório: `prop/fronts/` tem um módulo por frente (`asia.py`, `ny_open.py`), o
custo por barra em `common.py` e, em `portfolio.py`, o portão de entrada e a divisão de risco.
Regra do portão, aplicada só com dados anteriores a 2019: uma frente entra se (a) o Sharpe líquido
dela é positivo, (b) a correlação diária com cada frente já ativa é menor que 0,25 e (c) o Sharpe
do conjunto sobe. O risco entre as frentes aprovadas é dividido por paridade de risco hierárquica
(HRP). A Frente 1 (tendência de ouro e prata com volatilidade de queda) é a âncora e foi levada ao
robô `prop/live/mt5_trend.py`.

## Frente 2: reversão calma na sessão asiática

**O que foi testado.** EURGBP, USDCAD e AUDNZD (montado com AUDUSD e NZDUSD, pagando dois spreads),
barras de 1 hora desde 2010. O preço é comparado com o próprio nível móvel (média exponencial de
12, 24 ou 48 horas, que é o filtro de Kalman em regime estacionário de um modelo de nível local):
`z = (preço - nível) / desvio do resíduo`. Entra contra o desvio com `|z|` > 1,5 ou 2,0 entre 01:00
e 06:00 do servidor, sai quando `z` volta a zero, no stop (`|z|` > entrada + 2,5) ou, de qualquer
forma, na abertura da barra das 09:00, uma hora antes de Londres. Nada dorme aberto, então não há
swap nem janela de rollover.

| Variante | Sharpe antes de 2019 | Sharpe 2019-26 | Trades/mês | Acerto líquido | Profit factor | Dias positivos |
|---|---|---|---|---|---|---|
| nível 12h, z 1,5 | -4,06 | -2,83 | 13,2 | 38,6% | 0,45 | 18,1% |
| nível 12h, z 2,0 | -3,23 | -2,16 | 6,4 | 35,3% | 0,40 | 8,5% |
| nível 24h, z 1,5 | -3,63 | -2,27 | 12,9 | 38,6% | 0,49 | 18,1% |
| nível 24h, z 2,0 | -2,52 | -1,98 | 5,6 | 37,2% | 0,42 | 8,4% |
| nível 48h, z 1,5 | -2,91 | -2,19 | 13,2 | 40,6% | 0,53 | 19,5% |
| nível 48h, z 2,0 (melhor antes de 2019) | -1,64 | -1,39 | 5,6 | 40,7% | 0,55 | 8,7% |

**Por que falhou.** Sem custo nenhum o resultado já é zero (Sharpe entre -0,8 e +0,1, acerto de
49% a 52%): nesses pares, um desvio de 2 sigmas durante a madrugada não volta mais do que continua.
Com custo fica muito negativo, porque o movimento típico da sessão asiática é da ordem do próprio
spread. A sessão é calma, mas calma não é o mesmo que previsível.

**Decisão: descartada. Não entra no portfólio.**

## Frente 3: rompimento da faixa de abertura de Nova York

**O que foi testado.** US500, US30, USTEC (só tem dados desde 2022) e XAUUSD. O servidor está em
Nova York + 7 horas, então a abertura das 09:30 cai na barra das 16:00. Com barras de 1 hora não dá
para cortar 90 minutos exatos: a faixa é a máxima e a mínima da barra das 16:00 (ou das 16:00 e
17:00). Depois dela, até as 21:00, há uma ordem stop em cada lado da faixa; a primeira tocada é o
trade, o outro lado é o stop-loss físico e o que estiver aberto fecha na abertura das 22:00, antes
do rollover. Barra que toca os dois lados conta como stop. Variante com Hurst de 250 dias > 0,5.

| Variante | Sharpe antes de 2019 | Sharpe 2019-26 | Trades/mês | Acerto líquido | Profit factor | Dias positivos |
|---|---|---|---|---|---|---|
| faixa de 1h, sem filtro | -0,47 | 0,00 | 52,1 | 43,4% | 0,97 | 43,8% |
| faixa de 1h, com Hurst | -0,07 | 0,10 | 10,2 | 43,6% | 1,00 | 43,5% |
| faixa de 2h, sem filtro | -0,25 | -0,71 | 44,8 | 44,8% | 0,92 | 43,2% |
| faixa de 2h, com Hurst (melhor antes de 2019) | -0,03 | -0,27 | 8,7 | 44,4% | 0,97 | 43,6% |

**Sensibilidade ao custo (faixa de 1h, sem filtro, Sharpe antes / depois de 2019).**

| Custo por lado | US500 | US30 | XAUUSD | USTEC (só depois) |
|---|---|---|---|---|
| zero | 1,18 / 0,82 | 0,62 / 0,28 | 1,19 / 0,83 | 1,45 |
| só meio spread gravado | 0,74 / 0,59 | 0,39 / 0,16 | 0,36 / 0,66 | 1,34 |
| spread gravado + 25% de deslize, sem piso nem comissão | 0,25 / 0,22 | 0,18 / 0,07 | -0,17 / 0,53 | 1,15 |
| protocolo deste diário (piso de 1 ponto-base, deslize, comissão) | -0,32 / -0,04 | -0,49 / -0,45 | -0,46 / -0,02 | 0,88 |

**Leitura.** Aqui existe um efeito bruto de verdade: o rompimento da abertura rende de 1 a 3
pontos-base por trade antes do custo, nos dois períodos. O problema é que o custo de ida e volta
no protocolo é de cerca de 2 pontos-base, do mesmo tamanho. A frente vive ou morre pela qualidade
da execução, e ordens stop em rompimento costumam ser executadas pior que a média, não melhor. O
histórico não resolve essa dúvida, porque não tem ticks. O USTEC parece bom, mas só tem dados de
2022 em diante, sem período de escolha, então não pode ser aprovado pelo protocolo. O filtro de
Hurst reduz os trades a um quinto e não muda o resultado.

**Decisão: não aprovada no protocolo. Fica como a única candidata que merece medição ao vivo:
rodar em conta demo sem dinheiro por algumas semanas mede o custo real de execução, que é
exatamente a variável que decide.**

## Portão do portfólio e resultado do V9

| Frente candidata | Sharpe próprio antes de 2019 | Sharpe próprio 2019-26 | Maior correlação com as ativas | Decisão |
|---|---|---|---|---|
| Frente 2 (Ásia), nível 48h, z 2,0 | -1,64 | -1,39 | 0,10 | fica fora |
| Frente 3 (abertura NY), faixa de 2h com Hurst | -0,03 | -0,27 | 0,03 | fica fora |

As duas têm correlação baixa com a Frente 1, mas correlação baixa só ajuda quando a frente ganha
dinheiro. Somar uma frente de resultado zero ou negativo dilui a âncora.

| | Aprovação 8%+5% | Aprovação FTMO | Trades/mês | Dias até a meta da Fase 1 (8% / 10%) |
|---|---|---|---|---|
| Frente 1 isolada | 66,8% | 64,5% | 0,15 | 231 / 294 |
| Portfólio multi-motor (Frentes 1 + 2 + 3 + orquestrador) | 66,8% | 64,5% | 0,15 | 231 / 294 |

O portfólio é igual à Frente 1 porque nenhuma outra frente passou no portão. O orquestrador
(HRP) está implementado e testado, mas com uma frente só ele não tem o que dividir. Meta-labeling
conformal não foi reaplicado: na Hipótese 2 ele piorou a Frente 1, e as Frentes 2 e 3 não têm
vantagem líquida para ele filtrar.

**Situação.** A ideia de somar frentes descorrelacionadas é correta em princípio: duas frentes
independentes de Sharpe 0,6 dariam cerca de 0,85 juntas. O que falta não é o orquestrador, é uma
segunda frente com vantagem líquida, e 220 variantes testadas nestes mercados ainda não produziram
uma. Os dois caminhos com chance real são a Frente 4 (listagens em cripto, +0,29R por trade e
correlação naturalmente baixa com metais) e a medição ao vivo do custo da Frente 3.

---

# Ciclo 1 de medição ao vivo: custo real da Frente 3 (registrado em 28/11/2026, antes de qualquer dado)

**Por que este teste.** A Frente 3 (rompimento da abertura de Nova York) foi a única com efeito
bruto nos dois períodos, e foi reprovada só pelo custo. O histórico tem um spread por barra de 1
hora e nenhum tick, então o custo de verdade é desconhecido. Quem perde do outro lado, se o efeito
for real: quem fornece liquidez na primeira hora do pregão e é atropelado quando o fluxo do dia
toma direção. Isso só vira lucro se a execução custar menos que o efeito.

**Regra congelada (não muda depois de ver resultado).** Símbolos US500 e XAUUSD. Faixa = máxima e
mínima do bid das 09:00 às 10:00 de Nova York (é a barra das 16:00 do servidor usada no backtest
"faixa de 1h, sem filtro"). Das 10:00 às 15:00, o primeiro lado que o bid tocar é o trade (compra
no topo, venda no fundo), o outro lado é o stop, e o que estiver aberto fecha às 15:00. Um trade
por símbolo por dia. Sem filtro de Hurst, de notícia ou de spread. Lote mínimo, só em conta demo.
Código: `trader/prop/live/ny_open_demo.py`.

**O que é medido.** Para cada lado do trade, custo = diferença entre o preço executado e o preço
que o backtest assume (o nível da faixa na entrada e no stop, o bid às 15:00 na saída por hora),
em pontos-base. Onde o servidor não deixa negociar o símbolo, o trade é simulado na cotação ao
vivo (compra no ask, venda no bid) e marcado como simulado. O robô também grava bid e ask de
US500, XAUUSD, US30, USTEC e XAGUSD.

**Limite conhecido.** A cotação da demo é real, mas a execução da demo é melhor que a de uma conta
de verdade. Por isso o custo usado na decisão soma uma folga: custo por lado = média medida + 25%
do spread medido + comissão do protocolo (0,3 ponto-base).

**Critério de aprovação, fixado antes.** Backtest da mesma regra com custo fixo por lado (Sharpe
antes de 2019 / 2019-2026):

| Custo por lado (pb) | US500 | XAUUSD |
|---|---|---|
| 0,00 | 1,18 / 0,82 | 1,19 / 0,83 |
| 0,25 | 0,94 / 0,65 | 1,00 / 0,64 |
| 0,50 | 0,70 / 0,49 | 0,80 / 0,44 |
| 0,75 | 0,46 / 0,32 | 0,61 / 0,25 |
| 1,00 | 0,22 / 0,15 | 0,42 / 0,05 |
| 1,50 | -0,26 / -0,18 | 0,03 / -0,34 |

Um símbolo segue para o portão de soma (correlação com a Frente 1 abaixo de 0,25 e aprovação do
conjunto maior) somente se, com o custo por lado definido acima, o backtest der Sharpe de pelo
menos 0,5 antes de 2019 e acima de zero em 2019-2026. Na prática isso exige custo por lado de até
cerca de 0,70 pb no US500 e 0,90 pb no ouro. Também são exigidos pelo menos 30 trades ao vivo por
símbolo, e o resultado líquido ao vivo é comparado com a tabela fixa do protocolo.

**Parada antecipada.** Depois de 10 pregões, se o custo por lado medido (já com a folga) estiver
acima de 1,5 pb em um símbolo, ele é encerrado, porque nesse custo o backtest é negativo nos dois
períodos.

**Ressalvas registradas.** Aplicar o custo de hoje a todo o histórico supõe que o custo antigo era
parecido, o que favorece a frente. Se ela passar, o passo seguinte é continuar na demo dentro do
portfólio, não ir para um desafio. Este é o pivô 0 da hipótese; nenhum parâmetro foi escolhido
olhando dados de 2019 em diante além do que já está na seção "Frente 3".

**Prazo.** A regra dá cerca de 0,8 trade por pregão no US500 e 1 no ouro. Primeira leitura de
custo depois de 10 pregões (por volta de 11/12/2026). Conclusão com 30 trades por símbolo, cerca
de 8 semanas (fim de janeiro de 2027, por causa dos feriados).

Reprodução: `python -m prop.live.ny_open_demo --live --loop` (coleta) e
`python -m prop.live.ny_open_demo --report` (leitura).

---

# Janela curta: aprovação da Frente 1 com prazo (28/11/2026)

**Pergunta do Kenui.** Quanto dá para aprovar em 30 a 60 dias, e não em 8 a 10 meses.

**O que foi medido.** Dias de 2019-2026 da Frente 1 (tamanho pela volatilidade de queda), sorteados
em blocos de 10 dias, 20.000 contas, meta de 8% e depois 5%, perda total de 10%, dia encerrado em
-3% quando o pior ponto do dia chega lá. Tamanho fixo, escolhido o melhor de oito para cada prazo
(isso favorece o resultado). "Sorte" é a mesma série com média zero. Medição simples, menos
detalhada que a jornada completa do Estágio 2.

| Prazo para as duas fases | Melhor tamanho (vol. diária da conta) | Aprova | Reprova | Sorte aprova |
|---|---|---|---|---|
| 30 dias | 3,0% | 24,3% | 33,5% | 19,8% |
| 60 dias | 3,0% | 37,7% | 50,2% | 29,4% |
| 90 dias | 3,0% | 42,2% | 54,4% | 32,5% |
| 6 meses | 1,5% | 49,2% | 44,6% | 35,8% |

Referência teórica, retornos normais sem saltos: Sharpe 1,5 aprova cerca de 36% em 30 dias e 53%
em 60; Sharpe 3,0 aprova cerca de 52% e 72%.

**Leitura.** Ganhar 13% em 30 a 60 dias com perda máxima de 10% exige risco alto por dia. Com a
vantagem que temos (Sharpe 0,6), prazo curto é quase só aposta: a diferença para a sorte é de 5 a 8
pontos. Nem uma vantagem de Sharpe 3, que não temos, garantiria aprovação em 30 dias. O prazo longo
não é defeito do robô, é o preço de arriscar pouco por dia.

**Decisão.** Não existe versão de prazo curto aprovada. As mesas do arquivo de regras não impõem
prazo máximo no desafio, então o prazo curto é preferência, não regra.

---

# Mudança da fonte de medição da Frente 3 (28/11/2026, antes de qualquer dado)

O Kenui decidiu deixar o teste ao vivo para o fim do projeto. A regra, a definição de custo e o
critério do "Ciclo 1 de medição ao vivo" continuam os mesmos. Muda só a fonte: em vez de esperar
semanas de pregão, o comando `python -m prop.live.ny_open_demo --replay 500` pede ao terminal os
ticks que o servidor da demo guarda dos últimos pregões e aplica a regra neles. A execução é
simulada no tick seguinte ao gatilho (compra no ask, venda no bid).

O que isso mede e o que não mede: o spread real no instante do rompimento e o quanto o preço
escapa do nível, sim; a qualidade de execução de uma conta de verdade, não. A folga do critério
(25% do spread e 0,3 pb de comissão por lado) continua valendo. Não se sabe quantos pregões de
ticks o servidor guarda; o resultado só conta com 30 trades por símbolo. Os trades do replay são
um período recente dentro de 2019-2026, então servem para medir custo, não para escolher regra.
