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

  // Todos os arquivos usda*.json da pasta de fontes (o principal e os extras de cada lote).
  const usda = {};
  for (const f of readdirSync(pastaFontes).filter((n) => /^usda.*\.json$/.test(n)).sort()) {
    Object.assign(usda, lerJson(join(pastaFontes, f)).alimentos);
  }
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

// O cadastro fica em conteudo/ingredientes/*.json (base.json e um arquivo por lote).
// Um id repetido entre arquivos vale o primeiro e é apontado como erro por validarCadastro.
export const ingredientesRepetidos = [];
export function carregarIngredientes() {
  const pasta = join(PASTA_CONTEUDO, 'ingredientes');
  const todos = {};
  ingredientesRepetidos.length = 0;
  for (const f of readdirSync(pasta).filter((n) => n.endsWith('.json')).sort()) {
    for (const i of lerJson(join(pasta, f)).ingredientes) {
      if (todos[i.id]) { ingredientesRepetidos.push(`${i.id} cadastrado em ${todos[i.id]._arquivo} e em ${f}`); continue; }
      todos[i.id] = { ...i, _arquivo: f };
    }
  }
  return todos;
}

// Filtro por faixa de id: argumentos --de rbl-0021 --ate rbl-0068
export function faixaDosArgumentos(args) {
  const valor = (nome) => { const i = args.indexOf(nome); return i >= 0 ? args[i + 1] : null; };
  const de = valor('--de');
  const ate = valor('--ate');
  // --ids rbl-0004,rbl-0011 (ou um arquivo com um id por linha: --ids @lista.txt)
  let ids = valor('--ids');
  if (ids?.startsWith('@')) ids = readFileSync(ids.slice(1), 'utf8').split(/\s+/).filter(Boolean).join(',');
  const lista = ids ? new Set(ids.split(',')) : null;
  return (id) => (!de || id >= de) && (!ate || id <= ate) && (!lista || lista.has(id));
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
