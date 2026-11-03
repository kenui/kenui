// Gera docs/receitas-para-revisao.md: todas as receitas em texto corrido, com a nutrição
// calculada e o resultado do validador, para revisão humana.
// Uso: node scripts/gerar-revisao.mjs
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { carregarIngredientes, carregarProibidos, carregarReceitas, RAIZ } from './lib/fontes.mjs';
import { validarColecao } from './lib/validacao.mjs';

const ingredientes = carregarIngredientes();
const regras = carregarProibidos();
const resultados = validarColecao(carregarReceitas(), { ingredientes, regras });
const fmt = (n) => String(n).replace('.', ',');

const linhas = [];
const total = resultados.length;
const lowCarb = resultados.filter((r) => r.receita.etiquetas?.low_carb).length;
linhas.push('# Receitas para revisão', '');
linhas.push('Arquivo gerado por `npm run revisao`. Não edite à mão: edite os arquivos em `conteudo/receitas/`.', '');
linhas.push(`**${total} receitas**, ${lowCarb} low carb (${Math.round((lowCarb / total) * 100)}%).`, '');

linhas.push('## Contagem por categoria', '', '| Categoria | Receitas | Low carb |', '|---|---|---|');
for (const [id, nome] of Object.entries(regras.categorias)) {
  const da = resultados.filter((r) => r.receita.categoria === id);
  linhas.push(`| ${nome} | ${da.length} | ${da.filter((r) => r.receita.etiquetas?.low_carb).length} |`);
}

linhas.push('', '## Resumo', '', '| Receita | Categoria | Porção | kcal | Carboidratos | Low carb | Validador |', '|---|---|---|---|---|---|---|');
for (const { receita: r, erros, avisos } of resultados) {
  const status = erros.length ? `✗ ${erros.length} erro(s)` : avisos.length ? `✓ (${avisos.length} aviso)` : '✓';
  linhas.push(`| [${r.nome}](#${r.id}) | ${regras.categorias[r.categoria]} | ${r.porcao.descricao} | ${r.nutricao?.por_porcao.kcal ?? '—'} | ${fmt(r.nutricao?.por_porcao.carboidratos_g ?? '—')} g | ${r.etiquetas?.low_carb ? 'sim' : 'não'} | ${status} |`);
}

const avisosGerais = resultados.filter((r) => r.erros.length || r.avisos.length);
if (avisosGerais.length) {
  linhas.push('', '## Marcadas pelo validador', '');
  for (const { receita: r, erros, avisos } of avisosGerais) {
    for (const e of erros) linhas.push(`- **${r.id} ${r.nome}**: ERRO: ${e}`);
    for (const a of avisos) linhas.push(`- **${r.id} ${r.nome}**: ${a}`);
  }
}

for (const { receita: r } of resultados) {
  const t = r.tempo;
  linhas.push('', '---', '', `<a id="${r.id}"></a>`, `## ${r.nome}`, '');
  const etiquetas = ['0 açúcar adicionado', ...(r.etiquetas?.low_carb ? ['Low carb'] : [])];
  linhas.push(`*${r.descricao}*`, '');
  linhas.push(`\`${r.id}\` · ${regras.categorias[r.categoria]} · Etiquetas: ${etiquetas.join(', ')}`, '');
  const tempos = [`preparo ${t.preparo_min} min`, `cozimento ${t.cozimento_min} min`];
  if (t.descanso_min) tempos.push(`descanso ${t.descanso_min} min`);
  linhas.push(`- **Tempo total:** ${t.total_min} min (${tempos.join(', ')})`);
  linhas.push(`- **Rende:** ${fmt(r.rendimento.quantidade)} ${r.rendimento.unidade} · **${r.porcoes} porções** de ${r.porcao.descricao}`);
  linhas.push(`- **Por porção (valores aproximados):** ${r.nutricao.por_porcao.kcal} kcal · ${fmt(r.nutricao.por_porcao.carboidratos_g)} g de carboidratos · [cálculo](../${r.nutricao.arquivo_calculo})`);
  if (r.forno) linhas.push(`- **Forno:** ${r.forno.temperatura_c} °C, ${r.forno.tempo_min} min${r.forno.preaquecer ? ', preaquecido' : ''}`);
  linhas.push('', '**Ingredientes**', '');
  let grupo;
  for (const i of r.ingredientes) {
    if (i.grupo && i.grupo !== grupo) { grupo = i.grupo; linhas.push('', `*${grupo}*`, ''); }
    linhas.push(`- ${i.texto}${i.alternativa ? ` (${i.alternativa.texto}${i.alternativa.observacao ? '. ' + i.alternativa.observacao : ''})` : ''}`);
  }
  linhas.push('', '**Modo de preparo**', '');
  r.preparo.forEach((p, n) => linhas.push(`${n + 1}. ${p.texto}${p.aviso ? ` **Atenção:** ${p.aviso}` : ''}`));
  linhas.push('', '**Dicas**', '');
  const rotulo = { substituicao: 'Substituição', dica: 'Dica', conservacao: 'Como guardar' };
  for (const d of r.dicas) linhas.push(`- *${rotulo[d.tipo] ?? d.tipo}:* ${d.texto}`);
}

const destino = join(RAIZ, 'docs', 'receitas-para-revisao.md');
writeFileSync(destino, linhas.join('\n') + '\n');
console.log(`Gerado ${destino}`);
