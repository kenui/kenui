// Extrai da base USDA FoodData Central (SR Legacy, abril/2018) só os alimentos usados no app.
// Uso: node scripts/fontes/extrair-usda.mjs <pasta-descompactada-do-sr-legacy>
// Download: https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lerCsv } from '../lib/csv.mjs';

const pasta = process.argv[2];
if (!pasta) {
  console.error('Informe a pasta do SR Legacy descompactado.');
  process.exit(1);
}

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const destino = join(raiz, 'conteudo', 'fontes', 'usda-sr-legacy.json');
const atual = JSON.parse(readFileSync(destino, 'utf8'));
const ids = new Set(Object.keys(atual.alimentos));
for (const extra of process.argv.slice(3)) ids.add(extra);

const NUTRIENTES = { 1008: 'kcal', 1005: 'carboidratos_g', 1079: 'fibra_g', 1003: 'proteina_g', 1004: 'lipidios_g' };

const ler = (arquivo) => lerCsv(readFileSync(join(pasta, arquivo), 'utf8'));
const alimentos = {};
for (const f of ler('food.csv')) {
  if (ids.has(f.fdc_id)) alimentos[f.fdc_id] = { descricao: f.description, porcoes: [] };
}
for (const n of ler('food_nutrient.csv')) {
  const chave = NUTRIENTES[n.nutrient_id];
  if (chave && alimentos[n.fdc_id]) alimentos[n.fdc_id][chave] = Number(n.amount);
}
for (const p of ler('food_portion.csv')) {
  if (alimentos[p.fdc_id]) {
    alimentos[p.fdc_id].porcoes.push({ quantidade: Number(p.amount), medida: p.modifier, gramas: Number(p.gram_weight) });
  }
}
const faltando = [...ids].filter((id) => !alimentos[id]);
if (faltando.length) {
  console.error('Não encontrados na base:', faltando.join(', '));
  process.exit(1);
}
const ordenado = Object.fromEntries(Object.entries(alimentos).sort(([a], [b]) => Number(a) - Number(b)));
writeFileSync(destino, JSON.stringify({ ...atual, alimentos: ordenado }, null, 2) + '\n');
console.log(`${Object.keys(ordenado).length} alimentos gravados em ${destino}`);
