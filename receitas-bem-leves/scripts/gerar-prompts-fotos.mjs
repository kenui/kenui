// Monta o prompt da foto de cada receita a partir dos dados dela (nome, ingredientes visíveis e louça).
// Gera docs/fotos/prompts.jsonl, uma linha por receita: {"id","nome","prompt"}. Uso: node scripts/gerar-prompts-fotos.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { carregarIngredientes, carregarReceitas, RAIZ } from './lib/fontes.mjs';

const LOUCA = {
  tigela: 'a simple ceramic bowl', vitamina_copo: 'a tall clear glass', carne: 'a white ceramic dinner plate', pao_forma: 'a wooden cutting board, a loaf with two slices cut',
  legumes_assados: 'a ceramic oven dish', bolo_forma: 'a loaf cake on a wooden board, one slice cut', bolinhos_salgados: 'a ceramic plate', sopa: 'a deep ceramic soup bowl with a spoon',
  cookie: 'a small ceramic plate', salada: 'a large ceramic salad bowl', travessa_gratinada: 'a rectangular glass oven dish', frango: 'a white ceramic dinner plate', mousse_taca: 'a small clear glass dessert cup',
  muffin: 'a ceramic plate, muffins without paper wrappers', arroz_graos: 'a deep ceramic serving dish', bolo_redondo: 'a round cake on a simple ceramic cake plate, one slice cut', omelete: 'a white ceramic plate',
  torta: 'a round ceramic pie dish, one slice cut', pate_com_palitos: 'a small ceramic bowl with vegetable sticks beside it', pao_frigideira: 'a small dark non-stick frying pan on a wooden board', peixe: 'a white ceramic dinner plate',
  pudim: 'a simple ceramic plate', bolo_caneca: 'a ceramic mug', docinhos: 'a small ceramic plate', tapioca: 'a white ceramic plate', wrap: 'a white ceramic plate, wrap cut in half', geleia_pote: 'a small glass jar with a spoon',
  pave: 'a clear glass dish', picole: 'a ceramic plate with homemade popsicles', xicara_bebida: 'a ceramic cup with saucer', pao_de_queijo: 'a small basket lined with a cloth', panqueca_pilha: 'a white ceramic plate, a small stack',
  crepioca: 'a white ceramic plate, folded in half', ovos_mexidos: 'a white ceramic plate', pizza: 'a round wooden board, one slice cut', sanduiche: 'a white ceramic plate, cut in half', panqueca_enrolada: 'a ceramic oven dish',
  pure: 'a ceramic serving bowl', brownie: 'a small ceramic plate', waffle: 'a white ceramic plate', ceia_peru: 'a large oval ceramic platter', salpicao: 'a large ceramic bowl', misto_quente: 'a white ceramic plate, cut in half',
};
// Não aparecem na foto: temperos secos, líquidos e fermento.
const INVISIVEIS = /^(sal|pimenta|fermento|oleo|azeite|agua|eritritol|xilitol|stevia|sucralose|baunilha|bicarbonato|vinagre|gelatina|caldo|alho|cebola$|noz-moscada|cominho|colorau|paprica|curcuma|acafrao|louro|manteiga|leite|limao-suco)/;
const cadastro = carregarIngredientes();
const nomeIngrediente = (i) => cadastro[i.ingrediente]?.nome ?? i.ingrediente.replaceAll('-', ' ');

const linhas = carregarReceitas().map(({ receita: r }) => {
  const visiveis = [...new Set(r.ingredientes.filter((i) => !i.opcional && !INVISIVEIS.test(i.ingrediente)).map(nomeIngrediente).filter(Boolean))].slice(0, 7);
  const louca = LOUCA[r.ilustracao.prato_base] ?? 'a white ceramic plate';
  const prompt = [
    `Realistic homemade food photograph of the Brazilian dish "${r.nome}" (${r.descricao})`,
    `Presentation: ${louca}.`,
    `Only these visible ingredients: ${visiveis.join(', ')}.`,
    'Natural window daylight, 3/4 view, simple Brazilian home kitchen table, cotton cloth, shallow depth of field, appetizing and honest home cooking, not over-styled.',
    'Single dish in frame, 4:3. No text, no labels, no logos, no people, no hands. No powdered sugar, no honey, no syrup, no milk chocolate, no white bread, no ingredient that is not listed.',
  ].join(' ');
  return JSON.stringify({ id: r.id, nome: r.nome, prompt });
});
const pasta = join(RAIZ, 'docs', 'fotos');
mkdirSync(pasta, { recursive: true });
writeFileSync(join(pasta, 'prompts.jsonl'), linhas.join('\n') + '\n');
console.log(`${linhas.length} prompts em docs/fotos/prompts.jsonl`);
