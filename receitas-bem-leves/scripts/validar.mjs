// Valida todas as receitas. Sai com código 1 se alguma quebrar as regras.
// Uso: node scripts/validar.mjs [pasta-de-receitas] [--json]
import { carregarIngredientes, carregarProibidos, carregarReceitas, PASTA_RECEITAS } from './lib/fontes.mjs';
import { validarColecao } from './lib/validacao.mjs';

const args = process.argv.slice(2);
const pasta = args.find((a) => !a.startsWith('--')) ?? PASTA_RECEITAS;
const comoJson = args.includes('--json');

const contexto = { ingredientes: carregarIngredientes(), regras: carregarProibidos() };
const resultados = validarColecao(carregarReceitas(pasta), contexto);
const reprovadas = resultados.filter((r) => r.erros.length);
const comAviso = resultados.filter((r) => r.avisos.length);

if (comoJson) {
  console.log(JSON.stringify(resultados.map(({ receita, erros, avisos }) => ({ id: receita.id, nome: receita.nome, erros, avisos })), null, 2));
} else {
  for (const { receita, erros, avisos } of resultados) {
    const marca = erros.length ? '✗' : '✓';
    console.log(`${marca} ${receita.id ?? '(sem id)'} ${receita.nome ?? ''}`);
    erros.forEach((e) => console.log(`    ERRO: ${e}`));
    avisos.forEach((a) => console.log(`    revisar: ${a}`));
  }
  console.log(`\n${resultados.length} receitas, ${resultados.length - reprovadas.length} aprovadas, ${reprovadas.length} reprovadas, ${comAviso.length} para revisar.`);
}
process.exit(reprovadas.length ? 1 : 0);
