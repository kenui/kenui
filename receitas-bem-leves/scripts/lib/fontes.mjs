// Carrega as tabelas de composição (TACO, USDA e especiais) e o cadastro de ingredientes.
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lerCsv } from './csv.mjs';

export const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const PASTA_CONTEUDO = join(RAIZ, 'conteudo');
export const PASTA_RECEITAS = join(PASTA_CONTEUDO, 'receitas');
export const PASTA_NUTRICAO = join(PASTA_CONTEUDO, 'nutricao');

const lerJson = (caminho) => JSON.parse(readFileSync(caminho, 'utf8'));
const numeroOuNulo = (v) => (v === '' || v === undefined ? null : Number(v));

let cache;

export function carregarFontes() {
  if (cache) return cache;
  const pastaFontes = join(PASTA_CONTEUDO, 'fontes');

  const taco = {};
  const nomes = lerCsv(readFileSync(join(pastaFontes, 'taco-alimentos.csv'), 'utf8'));
  const nutrientes = lerCsv(readFileSync(join(pastaFontes, 'taco-nutrientes.csv'), 'utf8'));
  const porId = Object.fromEntries(nutrientes.map((n) => [n.foodId, n]));
  for (const a of nomes) {
    const n = porId[a.id] ?? {};
    taco[a.id] = {
      descricao: a.name,
      kcal: numeroOuNulo(n.kcal),
      carboidratos_g: numeroOuNulo(n.carbohydrates),
      fibra_g: numeroOuNulo(n.dietaryFiber),
    };
  }

  const usda = lerJson(join(pastaFontes, 'usda-sr-legacy.json')).alimentos;
  const especiais = lerJson(join(pastaFontes, 'especiais.json')).alimentos;
  cache = { taco, usda, especiais };
  return cache;
}

// "taco:489" | "usda:171265" | "especial:eritritol"
export function buscarNaFonte(referencia) {
  const { taco, usda, especiais } = carregarFontes();
  const [tabela, codigo] = String(referencia).split(':');
  const alimento = { taco, usda, especial: especiais }[tabela]?.[codigo];
  if (!alimento) return null;
  const nomeTabela = { taco: 'TACO 4ª ed.', usda: 'USDA SR Legacy', especial: 'Regra do app' }[tabela];
  return { ...alimento, rotulo: `${nomeTabela} ${tabela === 'especial' ? '' : codigo + ' '}${alimento.descricao}`.trim() };
}

export function carregarIngredientes() {
  const lista = lerJson(join(PASTA_CONTEUDO, 'ingredientes.json')).ingredientes;
  return Object.fromEntries(lista.map((i) => [i.id, i]));
}

export function carregarProibidos() {
  return lerJson(join(PASTA_CONTEUDO, 'regras.json'));
}

export function listarArquivosReceita(pasta = PASTA_RECEITAS) {
  return readdirSync(pasta).filter((f) => f.endsWith('.json')).sort().map((f) => join(pasta, f));
}

export function carregarReceitas(pasta = PASTA_RECEITAS) {
  return listarArquivosReceita(pasta).map((arquivo) => ({ arquivo, receita: lerJson(arquivo) }));
}
