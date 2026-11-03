// Gera as ilustrações de todas as receitas e uma folha de contato em PNG.
// Também confere o tamanho de cada SVG (máx. 15 KB) e grava os relatórios:
// - receitas que caíram no prato genérico (prato_base sem desenho);
// - ingredientes sem enfeite correspondente;
// - enfeites pedidos que foram descartados porque a receita não tem o ingrediente.
// Uso: node scripts/folha-de-contato.mjs [--ids rbl-0001,rbl-0002] [--saida docs/folha.png] [--colunas 10]
import { writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement as h } from 'react';
import { createRequire } from 'node:module';
import { carregarIngredientes, carregarReceitas, RAIZ } from './lib/fontes.mjs';
import { Ilustracao, enfeitesDaReceita, pratoDaReceita } from '../ilustracoes/index.mjs';

const args = process.argv.slice(2);
const valor = (n, padrao) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : padrao; };
const ids = valor('--ids', null)?.split(',');
const saida = join(RAIZ, valor('--saida', 'docs/folha-de-contato.png'));
const colunas = Number(valor('--colunas', 10));
const LIMITE = 15 * 1024;

const ingredientes = carregarIngredientes();
const receitas = carregarReceitas().map((x) => x.receita).filter((r) => !ids || ids.includes(r.id));

const svgs = [];
const pesados = [];
const genericos = [];
const descartados = [];
for (const r of receitas) {
  const svg = renderToStaticMarkup(h(Ilustracao, { receita: r, ingredientes }));
  const bytes = Buffer.byteLength(svg);
  if (bytes > LIMITE) pesados.push(`${r.id} ${r.nome}: ${(bytes / 1024).toFixed(1)} KB`);
  if (pratoDaReceita(r).generico) genericos.push(`${r.id} ${r.nome} (prato pedido: ${r.ilustracao?.prato_base ?? 'nenhum'})`);
  const usados = enfeitesDaReceita(r, ingredientes);
  const fora = (r.ilustracao?.enfeites ?? []).filter((e) => !usados.includes(e));
  if (fora.length) descartados.push(`${r.id} ${r.nome}: ${fora.join(', ')}`);
  svgs.push({ r, svg, bytes });
}

// Ingredientes usados em receitas que não têm enfeite.
const semEnfeite = new Map();
for (const r of receitas) {
  for (const i of r.ingredientes) {
    const c = ingredientes[i.ingrediente];
    if (c && !c.enfeite && !c.proibido) semEnfeite.set(c.id, (semEnfeite.get(c.id) ?? 0) + 1);
  }
}

const maior = Math.max(...svgs.map((x) => x.bytes));
const media = svgs.reduce((s, x) => s + x.bytes, 0) / svgs.length;
const relatorio = [
  '# Relatório das ilustrações', '',
  `Ilustrações geradas: ${svgs.length}. Tamanho médio ${(media / 1024).toFixed(1)} KB, maior ${(maior / 1024).toFixed(1)} KB (limite 15 KB).`, '',
  '## Acima de 15 KB', '', ...(pesados.length ? pesados.map((x) => `- ${x}`) : ['Nenhuma.']), '',
  '## Receitas no prato genérico (sem mapeamento de prato base)', '', ...(genericos.length ? genericos.map((x) => `- ${x}`) : ['Nenhuma.']), '',
  '## Enfeites descartados (a receita não tem o ingrediente)', '', ...(descartados.length ? descartados.map((x) => `- ${x}`) : ['Nenhum.']), '',
  '## Ingredientes sem enfeite correspondente', '',
  'São ingredientes que não aparecem no desenho (temperos, farinhas, líquidos e itens misturados na massa entram aqui naturalmente).', '',
  '| Ingrediente | Receitas que usam |', '|---|---|',
  ...[...semEnfeite.entries()].sort((a, b) => b[1] - a[1]).map(([id, n]) => `| ${ingredientes[id].nome} | ${n} |`),
];
mkdirSync(join(RAIZ, 'docs'), { recursive: true });
if (!ids) writeFileSync(join(RAIZ, 'docs', 'relatorio-ilustracoes.md'), relatorio.join('\n') + '\n');

// Folha de contato: grade de miniaturas com o id e o nome embaixo.
const largura = colunas * 240;
const html = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#FBF3E8;font:13px/1.25 Arial,sans-serif;color:#2A1A1A}
.g{display:grid;grid-template-columns:repeat(${colunas},240px);width:${largura}px}
.c{padding:6px;box-sizing:border-box}.c svg{width:228px;height:171px;display:block;border-radius:8px}
.c div{height:32px;overflow:hidden;margin-top:3px}
</style><div class="g">${svgs.map(({ r, svg }) => `<div class="c">${svg}<div><b>${r.id.slice(4)}</b> ${r.nome}</div></div>`).join('')}</div>`;
const { chromium } = createRequire(import.meta.url)('playwright');
const navegador = await chromium.launch();
const pagina = await navegador.newPage({ viewport: { width: largura, height: 800 }, deviceScaleFactor: receitas.length > 60 ? 0.5 : 1 });
await pagina.setContent(html);
await pagina.screenshot({ path: saida, fullPage: true });
await navegador.close();

console.log(`${svgs.length} ilustrações. Média ${(media / 1024).toFixed(1)} KB, maior ${(maior / 1024).toFixed(1)} KB.`);
console.log(`Acima de 15 KB: ${pesados.length}. Prato genérico: ${genericos.length}. Enfeites descartados: ${descartados.length}.`);
console.log(`Folha de contato: ${saida}`);
if (pesados.length) process.exit(1);
