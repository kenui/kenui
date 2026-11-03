# Receitas Bem Leves

App web instalável (PWA) com receitas sem açúcar adicionado.

Situação atual: **fase 2 (piloto de 20 receitas)**. O app em si (telas, login, offline) começa depois da aprovação do conteúdo.

## O que precisa estar instalado

- Node.js 20 ou mais novo. Não há dependências para instalar: os scripts usam só o Node.

## Comandos

Rode dentro da pasta `receitas-bem-leves/`:

| Comando | O que faz |
|---|---|
| `npm run nutricao` | Recalcula calorias e carboidratos de todas as receitas, grava o cálculo em `conteudo/nutricao/` e atualiza a etiqueta low carb |
| `npm run validar` | Confere todas as receitas contra as regras. Sai com erro se alguma quebrar |
| `npm test` | Testa o próprio validador (cada teste quebra uma regra de propósito) |
| `npm run revisao` | Gera `docs/receitas-para-revisao.md`, com todas as receitas em texto corrido para revisão |
| `npm run checar` | Roda os três primeiros em sequência |

## Como adicionar uma receita

1. Copie um arquivo de `conteudo/receitas/` parecido com a receita nova e renomeie para `rbl-NNNN-nome-da-receita.json`, com o próximo número livre.
2. Preencha nome, `slug` (o nome sem acento, com hífens), categoria, tempos, rendimento, porções, ingredientes, preparo, dicas e ilustração.
3. Cada ingrediente aponta para um `id` do cadastro `conteudo/ingredientes.json`. Se o ingrediente não existir lá, cadastre antes (veja abaixo).
4. Não preencha `nutricao` nem `etiquetas.low_carb` à mão. Rode `npm run nutricao`.
5. Rode `npm run validar` e corrija o que ele apontar.
6. Rode `npm run revisao` e leia a receita no arquivo gerado.

### Campos dos ingredientes da receita

```json
{
  "grupo": "Massa",
  "ingrediente": "aveia-em-flocos",
  "quantidade": 2,
  "medida": "xicara",
  "texto": "2 xícaras (chá) de aveia em flocos",
  "alternativa": { "ingrediente": "farinha-de-trigo", "texto": "ou 1 e 1/2 xícara de farinha de trigo" },
  "opcional": false
}
```

- `medida`: `unidade`, `xicara`, `colher_sopa`, `colher_cha`, `pitada`, `dente`, `g` ou `ml`. Quando o produto é vendido por peso (queijo, carne, ricota), prefira `g` e escreva a medida caseira no `texto`.
- `texto` é o que aparece na tela. `quantidade` e `medida` são usados no cálculo e na lista de compras.
- `grupo` é opcional e separa massa, recheio, calda etc.
- Itens `opcional: true` e as alternativas não entram no cálculo nutricional.

### Como cadastrar um ingrediente novo

Em `conteudo/ingredientes.json`:

```json
{
  "id": "ricota",
  "nome": "ricota",
  "sinonimos": [],
  "fonte_nutricao": "taco:469",
  "secao_mercado": "laticinios_frios",
  "facil_de_achar": true,
  "gramas_por_medida": {
    "xicara": { "g": 246, "fonte": "USDA 170851: 1 cup = 246 g" },
    "g": { "g": 1, "fonte": "grama" }
  },
  "proibido": false,
  "adocante": null,
  "enfeite": null
}
```

- `fonte_nutricao`: `taco:<número>` (arquivo `conteudo/fontes/taco-alimentos.csv`), `usda:<fdc_id>` (`conteudo/fontes/usda-sr-legacy.json`) ou `especial:<id>` (`conteudo/fontes/especiais.json`).
- Para um alimento da USDA que ainda não está no arquivo, baixe a base SR Legacy (link no topo de `scripts/fontes/extrair-usda.mjs`) e rode `node scripts/fontes/extrair-usda.mjs <pasta> <fdc_id>`.
- Toda medida caseira precisa dizer de onde veio o peso (`fonte`).
- Se a tabela não tiver um valor (por exemplo, carboidrato de óleo na TACO), use `ajuste_nutricao` com o valor e o motivo. Sem isso o cálculo recusa o ingrediente.
- Se `facil_de_achar` for `false`, toda receita que usar o ingrediente precisa trazer uma `alternativa`.

## Regras que o validador confere

Estão em `conteudo/regras.json` e `scripts/lib/validacao.mjs`:

- Nenhum ingrediente proibido (açúcar, mel, melado, rapadura, xaropes, leite condensado, achocolatado e outros). Os termos também são procurados no texto dos ingredientes, passos e dicas, com e sem acento. Expressões como "sem açúcar" são permitidas.
- Adoçantes aceitos: eritritol, xilitol, stevia, sucralose e fruta.
- Nutrição presente, calculada pelo script e igual ao arquivo de cálculo.
- Etiqueta low carb só com no máximo 15 g de carboidrato por porção. A etiqueta é conferida nos dois sentidos.
- Modo de preparo sem passos vazios; receita que usa forno precisa ter temperatura e tempo realistas.
- Pelo menos uma dica de substituição.
- Ingrediente difícil de achar precisa de alternativa.
- Nenhuma promessa de saúde (glicemia, cura, emagrecer e outros).
- Sem receitas repetidas: mesmo id, mesmo nome ou 85% ou mais dos ingredientes iguais na mesma categoria.
- A ilustração só pode desenhar enfeites de ingredientes que a receita tem.

## Fontes da nutrição

- **TACO**, Tabela Brasileira de Composição de Alimentos, 4ª edição revisada e ampliada (NEPA/Unicamp, 2011). Arquivos em `conteudo/fontes/taco-*.csv`, tirados da planilha original da Unicamp pelo projeto aberto [taco-api](https://github.com/raulfdm/taco-api). Nessa conversão, "Tr" (traço) virou 0 e "NA" e "*" (em reavaliação) ficaram vazios.
- **USDA FoodData Central**, SR Legacy (abril/2018), para o que a TACO não tem (cacau 100%, especiarias, fermento biológico) ou tem com valor em reavaliação (leite integral). Também é a fonte do peso das medidas caseiras.
- **Regra do app** (`conteudo/fontes/especiais.json`): eritritol, stevia e sucralose contam 0 kcal e 0 g de carboidrato. O xilitol conta 2,4 kcal/g e o carboidrato cheio.
- Na tela, os valores aparecem como "valores aproximados".

## Estrutura

```
conteudo/
  receitas/          uma receita por arquivo (fonte da verdade)
  ingredientes.json  cadastro único de ingredientes
  regras.json        categorias, medidas, termos proibidos
  fontes/            TACO, USDA e valores especiais
  nutricao/          cálculo linha por linha de cada receita (gerado)
scripts/
  calcular-nutricao.mjs
  validar.mjs
  gerar-revisao.mjs
  fontes/extrair-usda.mjs
  lib/               leitura de dados, cálculo e regras
testes/              testes do validador
docs/                proposta técnica e arquivo de revisão
```

## Publicar

Ainda não há o que publicar. As instruções de publicação (Hostinger, Supabase e Hotmart) entram aqui nas fases 5 e 6.
