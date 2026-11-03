// Recalcula a nutrição de todas as receitas e grava:
// - conteudo/nutricao/<id>.json (cálculo linha por linha, para conferência)
// - na receita: nutricao.por_porcao e etiquetas.low_carb
// Uso: node scripts/calcular-nutricao.mjs [--de rbl-0021] [--ate rbl-0068]
import { writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { carregarIngredientes, carregarProibidos, carregarReceitas, faixaDosArgumentos, PASTA_NUTRICAO, RAIZ } from './lib/fontes.mjs';
import { calcularNutricao } from './lib/nutricao.mjs';

const ingredientes = carregarIngredientes();
const { low_carb_max_carboidratos_g: limite } = carregarProibidos();
let falhas = 0;
const naFaixa = faixaDosArgumentos(process.argv.slice(2));

for (const { arquivo, receita } of carregarReceitas()) {
  if (!naFaixa(receita.id)) continue;
  const { erros, calculo } = calcularNutricao(receita, ingredientes);
  if (erros.length || !calculo.por_porcao) {
    falhas++;
    console.error(`✗ ${receita.id ?? arquivo}: ${erros.join('; ') || 'porções inválidas'}`);
    continue;
  }
  const destino = join(PASTA_NUTRICAO, `${receita.id}.json`);
  writeFileSync(destino, JSON.stringify(calculo, null, 2) + '\n');

  receita.nutricao = {
    por_porcao: calculo.por_porcao,
    calculado_com: 'ingredientes principais (sem alternativas e sem opcionais)',
    fonte: 'TACO 4ª ed. (Unicamp) e USDA FoodData Central',
    arquivo_calculo: relative(RAIZ, destino),
    aproximado: true,
  };
  receita.etiquetas = {
    ...receita.etiquetas,
    sem_acucar_adicionado: true,
    low_carb: calculo.por_porcao.carboidratos_g <= limite,
  };
  writeFileSync(arquivo, JSON.stringify(receita, null, 2) + '\n');
  console.log(`✓ ${receita.id} ${receita.nome}: ${calculo.por_porcao.kcal} kcal, ${calculo.por_porcao.carboidratos_g} g carb${receita.etiquetas.low_carb ? ' (low carb)' : ''}`);
}

if (falhas) {
  console.error(`\n${falhas} receita(s) sem cálculo.`);
  process.exit(1);
}
