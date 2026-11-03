# Relatório da fase 3: as 500 receitas

## Resumo

- **500 receitas** no total: as 20 do piloto e mais 480 novas, escritas em 9 lotes temáticos. Cada lote rodou o validador e corrigiu os próprios erros; no fim, o validador rodou sobre as 500 juntas.
- **Validador:** 500 aprovadas, 0 reprovadas. Na checagem final ele barrou uma receita repetida ("Bolo de nozes" aparecia em Doces e em Ceia); a da ceia foi trocada por "Creme natalino com damasco".
- **Low carb:** 238 receitas (48%).
- **Nutrição:** calculada ingrediente por ingrediente. O cálculo de cada receita está em `conteudo/nutricao/rbl-NNNN.json`.

## Contagem por categoria

| Categoria | Pedido | Entregue | Low carb |
|---|---|---|---|
| Café da manhã + Pães e substitutos | 120 | 68 + 52 = 120 | 21 + 17 |
| Lanches | 100 | 100 | 56 |
| Almoço e jantar | 130 | 130 | 80 |
| Doces e bolos | 120 | 120 | 54 |
| Ceia | 30 | 30 | 10 |
| **Total** | **500** | **500** | **238 (48%)** |

## Para você revisar

### 1. Calorias acima do real nas carnes com osso

O cálculo usa o peso cru **com osso** (peru inteiro, pernil, costela, frango inteiro, coxa, sobrecoxa, asa, bisteca, peixe inteiro). As tabelas trazem o valor da parte comestível; por isso as calorias dessas receitas saem 20% a 45% acima do real. Os carboidratos quase não mudam, porque carne não tem carboidrato.

A USDA só traz o rendimento sem osso para dois cortes (frango inteiro: 61%; bisteca: 77%). Por isso deixei sem correção, em vez de usar fatores sem fonte. Receitas afetadas:

rbl-0012, 0232, 0235, 0236, 0241, 0242, 0245, 0247, 0248, 0264, 0276, 0278, 0279, 0284, 0291, 0311, 0473, 0474, 0475 (1.165 kcal por porção), 0476, 0477.

Se você aprovar, a correção é simples: aplico os rendimentos da USDA onde existem e, nos outros cortes, peço o peso sem osso na receita.

### 2. Ingredientes com valor nutricional aproximado

| Ingrediente | Valor usado no cálculo | Motivo |
|---|---|---|
| Polvilho azedo | fécula de mandioca | não está na TACO |
| Flocão de milho | farinha de milho amarela | não está na TACO |
| Mix de frutas vermelhas congeladas | amora congelada (USDA) | |
| Pasta de amendoim integral | amendoim torrado sem sal (USDA) | a pasta da USDA pode ter açúcar |
| Moranga | peso inteiro, com casca | rbl-0302, camarão na moranga |
| Pera cozida no suco de uva | inclui toda a calda | rbl-0471, carboidrato por porção superestimado |

Também têm peso estimado, porque nenhuma tabela traz a medida caseira: chia e coco ralado por colher, farinha de mandioca e flocão por xícara, farinha de amêndoas por xícara.

### 3. Receitas que pedem um teste na cozinha antes de divulgar

- **Massas de pão:**
  - Pão de queijo de abóbora, pãozinho de abóbora, de batata-doce e de mandioquinha, e pão de batata recheado: a farinha depende da umidade do purê.
  - Panetone caseiro com eritritol (rbl-0492).
- **Massas aeradas e confeitaria:**
  - Pão de ló e rocambole de morango com eritritol: a espuma de ovo fica menos firme sem açúcar.
  - Sequilhos de maisena, biscoito de polvilho assado e pão de nuvem.
  - Brownie de feijão-preto.
- **Doces sem leite condensado:**
  - Torta de limão firmada com gelatina.
  - Docinhos de leite em pó com eritritol.
  - Sorvete de coco.
- **Preparos de panela:**
  - Nhoque de abóbora e cuscuz paulista (proporção de flocão e água).
  - Mingau de milho-verde, que não leva amido.
- **Outros:**
  - Chips de maçã (140 °C por 50 min).
  - Barrinha de aveia sem ovo.
  - Coxinha com massa de batata, falafel de grão-de-bico cozido e dadinho de tapioca com queijo meia cura.

### 4. Ingredientes industrializados com aviso de rótulo

As receitas com estes ingredientes trazem "confira no rótulo: sem açúcar", porque muitas marcas levam açúcar:

- shoyu
- extrato e purê de tomate
- leite de coco
- linguiças
- damasco, ameixa e uva-passa
- coco ralado

A ervilha em lata não foi usada.

### 5. Plano de 4 semanas

O cardápio usa 112 receitas diferentes, sem repetir nenhuma. Por regra, ficaram fora do plano:

- **Acompanhamentos** (arroz, purê, farofa, vinagrete, refogados) e pratos com menos de 150 kcal: não entram como almoço ou jantar.
- **Bebidas muito leves:** não entram como lanche (menos de 80 kcal) nem como café da manhã (menos de 100 kcal).
- **Receitas de ceia:** não entram no plano.

Todas essas continuam no app normalmente.

## Avisos do validador (parecidas, mas não iguais)

O validador aponta pares de receitas com o mesmo prato base e 60% ou mais dos ingredientes iguais. Conferimos e são pratos diferentes, mas vale uma olhada:

- **rbl-0048 Focaccia de alecrim**: parecida com rbl-0044 (Pão de batata-doce com alecrim): 60% dos ingredientes iguais e mesmo prato
- **rbl-0055 Broinha de fubá com queijo**: parecida com rbl-0030 (Chipa): 63% dos ingredientes iguais e mesmo prato
- **rbl-0056 Pão de minuto de iogurte**: parecida com rbl-0051 (Pão de amêndoas): 67% dos ingredientes iguais e mesmo prato
- **rbl-0085 Ovo na rodela de pimentão**: parecida com rbl-0074 (Omelete de legumes picadinhos): 60% dos ingredientes iguais e mesmo prato
- **rbl-0110 Mingau de fubá com canela**: parecida com rbl-0108 (Mingau de milho-verde): 60% dos ingredientes iguais e mesmo prato
- **rbl-0134 Coxinha de batata com frango de forno**: parecida com rbl-0068 (Pão de batata recheado com frango): 62% dos ingredientes iguais e mesmo prato
- **rbl-0149 Chips de batata-doce assados**: parecida com rbl-0060 (Torradas de batata-doce): 67% dos ingredientes iguais e mesmo prato
- **rbl-0187 Vitamina de banana com pasta de amendoim**: parecida com rbl-0115 (Overnight oats de banana e pasta de amendoim): 67% dos ingredientes iguais e mesmo prato
- **rbl-0188 Vitamina de maçã com aveia e canela**: parecida com rbl-0116 (Overnight oats de maçã e canela): 67% dos ingredientes iguais e mesmo prato
- **rbl-0269 Carne moída com repolho**: parecida com rbl-0256 (Carne moída com abobrinha): 63% dos ingredientes iguais e mesmo prato
- **rbl-0273 Fígado acebolado**: parecida com rbl-0252 (Coração de frango na frigideira): 67% dos ingredientes iguais e mesmo prato
- **rbl-0276 Bisteca acebolada**: parecida com rbl-0252 (Coração de frango na frigideira): 67% dos ingredientes iguais e mesmo prato
- **rbl-0276 Bisteca acebolada**: parecida com rbl-0273 (Fígado acebolado): 67% dos ingredientes iguais e mesmo prato
- **rbl-0293 Estrogonofe de carne**: parecida com rbl-0237 (Estrogonofe de frango): 60% dos ingredientes iguais e mesmo prato
- **rbl-0299 Atum refogado com legumes**: parecida com rbl-0256 (Carne moída com abobrinha): 67% dos ingredientes iguais e mesmo prato
- **rbl-0301 Escondidinho de peixe com mandioquinha**: parecida com rbl-0251 (Escondidinho de abóbora com frango): 62% dos ingredientes iguais e mesmo prato
- **rbl-0361 Bolo de fubá cremoso**: parecida com rbl-0357 (Bolo de cenoura com cobertura de cacau): 60% dos ingredientes iguais e mesmo prato
- **rbl-0368 Bolo de banana com cacau**: parecida com rbl-0357 (Bolo de cenoura com cobertura de cacau): 67% dos ingredientes iguais e mesmo prato
- **rbl-0369 Bolo de chocolate com abobrinha**: parecida com rbl-0367 (Bolo de abóbora): 63% dos ingredientes iguais e mesmo prato
- **rbl-0370 Bolo de café**: parecida com rbl-0363 (Bolo de maçã com canela): 71% dos ingredientes iguais e mesmo prato
- **rbl-0372 Bolo mármore**: parecida com rbl-0357 (Bolo de cenoura com cobertura de cacau): 67% dos ingredientes iguais e mesmo prato
- **rbl-0372 Bolo mármore**: parecida com rbl-0368 (Bolo de banana com cacau): 75% dos ingredientes iguais e mesmo prato
- **rbl-0374 Cuca de banana**: parecida com rbl-0368 (Bolo de banana com cacau): 60% dos ingredientes iguais e mesmo prato
- **rbl-0374 Cuca de banana**: parecida com rbl-0373 (Bolo de aveia com uva-passa): 60% dos ingredientes iguais e mesmo prato
- **rbl-0377 Bolo de amendoim**: parecida com rbl-0360 (Bolo de coco gelado): 63% dos ingredientes iguais e mesmo prato
- **rbl-0377 Bolo de amendoim**: parecida com rbl-0368 (Bolo de banana com cacau): 63% dos ingredientes iguais e mesmo prato
- **rbl-0377 Bolo de amendoim**: parecida com rbl-0372 (Bolo mármore): 63% dos ingredientes iguais e mesmo prato
- **rbl-0381 Pão de ló**: parecida com rbl-0362 (Bolo de iogurte): 83% dos ingredientes iguais e mesmo prato
- **rbl-0381 Pão de ló**: parecida com rbl-0375 (Bolo de maracujá): 67% dos ingredientes iguais e mesmo prato
- **rbl-0383 Bolo de batata-doce**: parecida com rbl-0377 (Bolo de amendoim): 63% dos ingredientes iguais e mesmo prato
- **rbl-0386 Bolo de caneca de pasta de amendoim**: parecida com rbl-0384 (Bolo de caneca de cacau): 71% dos ingredientes iguais e mesmo prato
- **rbl-0397 Cookie de coco**: parecida com rbl-0396 (Cookie de cacau): 63% dos ingredientes iguais e mesmo prato
- **rbl-0399 Biscoito amanteigado**: parecida com rbl-0397 (Cookie de coco): 71% dos ingredientes iguais e mesmo prato
- **rbl-0400 Sequilhos de maisena**: parecida com rbl-0399 (Biscoito amanteigado): 67% dos ingredientes iguais e mesmo prato
- **rbl-0406 Rosca de canela**: parecida com rbl-0405 (Rosca doce de laranja): 67% dos ingredientes iguais e mesmo prato
- **rbl-0410 Bolinho de chuva assado**: parecida com rbl-0391 (Muffin de maçã com nozes): 60% dos ingredientes iguais e mesmo prato
- **rbl-0412 Bolo de goiaba**: parecida com rbl-0360 (Bolo de coco gelado): 63% dos ingredientes iguais e mesmo prato
- **rbl-0412 Bolo de goiaba**: parecida com rbl-0368 (Bolo de banana com cacau): 63% dos ingredientes iguais e mesmo prato
- **rbl-0412 Bolo de goiaba**: parecida com rbl-0372 (Bolo mármore): 63% dos ingredientes iguais e mesmo prato
- **rbl-0412 Bolo de goiaba**: parecida com rbl-0377 (Bolo de amendoim): 71% dos ingredientes iguais e mesmo prato
- **rbl-0412 Bolo de goiaba**: parecida com rbl-0383 (Bolo de batata-doce): 63% dos ingredientes iguais e mesmo prato
- **rbl-0413 Bolo de ameixa-preta**: parecida com rbl-0360 (Bolo de coco gelado): 63% dos ingredientes iguais e mesmo prato
- **rbl-0413 Bolo de ameixa-preta**: parecida com rbl-0368 (Bolo de banana com cacau): 63% dos ingredientes iguais e mesmo prato
- **rbl-0413 Bolo de ameixa-preta**: parecida com rbl-0372 (Bolo mármore): 63% dos ingredientes iguais e mesmo prato
- **rbl-0413 Bolo de ameixa-preta**: parecida com rbl-0377 (Bolo de amendoim): 71% dos ingredientes iguais e mesmo prato
- **rbl-0413 Bolo de ameixa-preta**: parecida com rbl-0383 (Bolo de batata-doce): 63% dos ingredientes iguais e mesmo prato
- **rbl-0413 Bolo de ameixa-preta**: parecida com rbl-0412 (Bolo de goiaba): 71% dos ingredientes iguais e mesmo prato
- **rbl-0426 Pudim de banana**: parecida com rbl-0422 (Pudim de chocolate): 63% dos ingredientes iguais e mesmo prato
- **rbl-0439 Sorvete de banana com canela**: parecida com rbl-0106 (Mingau de aveia com banana e canela): 60% dos ingredientes iguais e mesmo prato
- **rbl-0450 Compota de maçã com canela**: parecida com rbl-0229 (Chips de maçã com canela): 75% dos ingredientes iguais e mesmo prato
- **rbl-0466 Torta de banana com farofa de aveia**: parecida com rbl-0463 (Torta de maçã): 60% dos ingredientes iguais e mesmo prato
- **rbl-0475 Costela bovina assada**: parecida com rbl-0264 (Costela bovina no forno): 80% dos ingredientes iguais e mesmo prato
- **rbl-0477 Peixe assado inteiro com batatas**: parecida com rbl-0296 (Peixe ao molho de tomate): 60% dos ingredientes iguais e mesmo prato
- **rbl-0484 Lentilha de Ano-Novo com legumes**: parecida com rbl-0314 (Sopa de lentilha): 70% dos ingredientes iguais e mesmo prato
- **rbl-0490 Couve-flor gratinada**: parecida com rbl-0352 (Brócolis gratinado): 75% dos ingredientes iguais e mesmo prato
- **rbl-0491 Rabanada assada com pão de aveia**: parecida com rbl-0406 (Rosca de canela): 78% dos ingredientes iguais e mesmo prato
- **rbl-0491 Rabanada assada com pão de aveia**: parecida com rbl-0408 (Pão de minuto doce): 60% dos ingredientes iguais e mesmo prato
- **rbl-0498 Docinho de tâmara, nozes e cacau**: parecida com rbl-0220 (Bolinhas de tâmara e castanha): 60% dos ingredientes iguais e mesmo prato
- **rbl-0500 Rocambole de carne recheado**: parecida com rbl-0263 (Rocambole de carne moída recheado): 73% dos ingredientes iguais e mesmo prato
