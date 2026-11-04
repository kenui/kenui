// Gera os PDFs dos produtos extras (para cadastrar na Hotmart e para quem prefere papel):
//   docs/produtos/caderno-de-receitas-para-imprimir.pdf
//   docs/produtos/cardapio-de-12-semanas.pdf
//   docs/produtos/guia-de-marmitas-da-semana.pdf
// Uso: node scripts/gerar-extras.mjs && node scripts/gerar-pdfs.mjs
import { mkdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { carregarIngredientes, carregarProibidos, carregarReceitas, PASTA_CONTEUDO, RAIZ } from './lib/fontes.mjs';
import { Ilustracao } from '../ilustracoes/index.mjs';

const ingredientes = carregarIngredientes();
const regras = carregarProibidos();
const receitas = carregarReceitas().map((x) => x.receita);
const porId = Object.fromEntries(receitas.map((r) => [r.id, r]));
const extra = (nome) => JSON.parse(readFileSync(join(PASTA_CONTEUDO, 'extras', `${nome}.json`), 'utf8'));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (n) => String(n).replace('.', ',');
const RODAPE = 'Receitas Bem Leves · Kenui Cabral · CNPJ 52.594.756/0001-00 · As receitas e valores nutricionais são informativos e não substituem a orientação do seu médico ou nutricionista.';
const DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
const REF = [['cafe_da_manha', 'Café da manhã'], ['lanche', 'Lanche'], ['almoco', 'Almoço'], ['jantar', 'Jantar']];

const ESTILO = `
@page { size: A4; margin: 16mm 14mm 18mm; }
* { box-sizing: border-box; }
body { font-family: 'Atkinson Hyperlegible', Arial, sans-serif; color: #2A1A1A; font-size: 13.5pt; line-height: 1.4; margin: 0; }
h1, h2, h3 { font-family: 'DM Serif Display', Georgia, serif; font-weight: 400; color: #7B1E2C; margin: 0 0 6px; }
.pagina { break-after: page; }
.capa { height: 255mm; display: flex; flex-direction: column; justify-content: center; gap: 14px; background: #FBF3E8; padding: 30mm 20mm; border-radius: 6mm; }
.capa h1 { font-size: 40pt; line-height: 1.05; }
.capa p { font-size: 15pt; }
.marca { font-family: 'DM Serif Display', Georgia, serif; color: #7B1E2C; font-size: 18pt; }
.receita h2 { font-size: 24pt; }
.ilus { float: right; width: 72mm; margin: 0 0 4mm 5mm; border-radius: 3mm; overflow: hidden; }
.ilus svg { display: block; width: 100%; height: auto; }
.meta { font-size: 11pt; color: #5A4644; margin-bottom: 4mm; }
.etq { display: inline-block; font-size: 10pt; font-weight: 700; color: #fff; background: #137A3D; border-radius: 99px; padding: 1px 8px; margin-right: 4px; }
.etq.v { background: #7B1E2C; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1.5mm; }
.grupo { font-weight: 700; margin-top: 2mm; }
.anot { margin-top: 5mm; color: #777; border-top: 1px dashed #bbb; padding-top: 2mm; font-size: 11pt; }
table { width: 100%; border-collapse: collapse; font-size: 11pt; }
th, td { border: 1px solid #D9C4A8; padding: 2.2mm; text-align: left; vertical-align: top; }
th { background: #F3E4CF; }
.rodape { font-size: 9pt; color: #777; margin-top: 4mm; }
.colunas { columns: 2; column-gap: 8mm; font-size: 11.5pt; }
.colunas h3 { break-after: avoid; font-size: 13pt; margin-top: 2mm; }
.caixas li { list-style: none; margin-left: -6mm; }
.caixas li:before { content: '☐  '; }
`;

function paginaReceita(r) {
  const svg = renderToStaticMarkup(h(Ilustracao, { receita: r, ingredientes }));
  let grupo = null;
  const ings = r.ingredientes.map((i) => {
    let cab = '';
    if (i.grupo && i.grupo !== grupo) { grupo = i.grupo; cab = `</ul><div class="grupo">${esc(i.grupo)}</div><ul>`; }
    return `${cab}<li>${esc(i.texto)}${i.alternativa ? ` <i>(${esc(i.alternativa.texto)})</i>` : ''}</li>`;
  }).join('');
  return `<section class="pagina receita">
    <div class="ilus">${svg}</div>
    <h2>${esc(r.nome)}</h2>
    <div><span class="etq">0 açúcar adicionado</span>${r.etiquetas.low_carb ? '<span class="etq v">Low carb</span>' : ''}</div>
    <p class="meta">${r.tempo.total_min} min · rende ${num(r.rendimento.quantidade)} ${esc(r.rendimento.unidade)} · por porção (${esc(r.porcao.descricao)}): ${r.nutricao.por_porcao.kcal} kcal e ${num(r.nutricao.por_porcao.carboidratos_g)} g de carboidratos (valores aproximados)${r.forno ? ` · forno ${r.forno.temperatura_c} °C` : ''}</p>
    <h3>Ingredientes</h3><ul>${ings}</ul>
    <h3>Modo de preparo</h3><ol>${r.preparo.map((p) => `<li>${esc(p.texto)}${p.aviso ? ` <b>Atenção:</b> ${esc(p.aviso)}` : ''}</li>`).join('')}</ol>
    <h3>Dica</h3><p>${esc((r.dicas.find((d) => d.tipo === 'substituicao') ?? r.dicas[0])?.texto)}</p>
    <div class="anot">Anotações: ______________________________________________________________</div>
  </section>`;
}

function tabelaSemana(semana, titulo) {
  return `<h3>${esc(titulo)}</h3><table><tr><th>Dia</th>${REF.map(([, n]) => `<th>${n}</th>`).join('')}</tr>
    ${DIAS.map((d, i) => `<tr><th>${d}</th>${REF.map(([k]) => `<td>${esc(porId[semana[i][k]]?.nome)}</td>`).join('')}</tr>`).join('')}</table>`;
}

// Soma os ingredientes de uma lista de receitas (uma receita de cada) por seção do mercado.
const MED = { xicara: ['xícara', 'xícaras'], colher_sopa: ['colher (sopa)', 'colheres (sopa)'], colher_cha: ['colher (chá)', 'colheres (chá)'], pitada: ['pitada', 'pitadas'], dente: ['dente', 'dentes'] };
const fr = (q) => { const i = Math.floor(q + 1e-9); const r = Math.round((q - i) * 100) / 100; const f = [[0.25, '1/4'], [0.33, '1/3'], [0.5, '1/2'], [0.67, '2/3'], [0.66, '2/3'], [0.75, '3/4']].find(([v]) => Math.abs(v - r) < 0.02); return r === 0 ? String(i) : f ? (i ? `${i} e ${f[1]}` : f[1]) : num(Math.round(q * 10) / 10); };
function listaCompras(ids) {
  const soma = {};
  for (const id of ids) for (const i of porId[id].ingredientes) {
    if (i.opcional || i.ingrediente === 'agua') continue;
    (soma[i.ingrediente] ??= {})[i.medida] = ((soma[i.ingrediente] ??= {})[i.medida] ?? 0) + i.quantidade;
  }
  const grupos = {};
  for (const [id, m] of Object.entries(soma)) {
    const c = ingredientes[id];
    const partes = Object.entries(m).map(([k, q]) => (k === 'g' ? (q >= 1000 ? `${num(Math.round(q / 100) / 10)} kg` : `${Math.round(q)} g`) : k === 'ml' ? `${Math.round(q)} ml` : k === 'unidade' ? fr(q) : `${fr(q)} ${(MED[k] ?? [k, k])[q > 1 ? 1 : 0]}`));
    const texto = Object.keys(m).length === 1 && m.unidade ? `${partes[0]} ${m.unidade > 1 && c.nome_plural ? c.nome_plural : c.nome}` : `${partes.join(' + ')} de ${c.nome}`;
    (grupos[c.secao_mercado] ??= []).push(texto);
  }
  return Object.keys(regras.secoes_mercado).filter((s) => grupos[s])
    .map((s) => `<h3>${regras.secoes_mercado[s]}</h3><ul class="caixas">${grupos[s].sort((a, b) => a.localeCompare(b, 'pt-BR')).map((t) => `<li>${esc(t)}</li>`).join('')}</ul>`).join('');
}

function blocosTexto(blocos) {
  return blocos.map((b) => {
    if (b.t === 'p') return `<p>${esc(b.texto)}</p>`;
    if (b.t === 'h') return `<h2>${esc(b.texto)}</h2>`;
    if (b.t === 'lista') return `<ul>${b.itens.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>`;
    if (b.t === 'tabela') return `<table><tr>${b.cabecalho.map((c) => `<th>${esc(c)}</th>`).join('')}</tr>${b.linhas.map((l) => `<tr>${l.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</table>`;
    if (b.t === 'receitas_ids') return `<ul class="colunas">${b.ids.map((id) => `<li>${esc(porId[id]?.nome)}</li>`).join('')}</ul>`;
    if (b.t === 'domingos') return `<table><tr><th>Domingo</th><th>Pratos principais</th><th>Acompanhamento</th><th>Lanche</th></tr>${b.domingos.map((d, i) => `<tr><th>${i + 1}</th><td>${d.principais.map((id) => esc(porId[id]?.nome)).join(' e ')}</td><td>${esc(porId[d.acompanhamento]?.nome ?? '—')}</td><td>${esc(porId[d.lanche]?.nome ?? '—')}</td></tr>`).join('')}</table>`;
    return '';
  }).join('');
}

const capa = (titulo, sub) => `<section class="pagina capa"><div class="marca">Receitas Bem Leves</div><h1>${esc(titulo)}</h1><p>${esc(sub)}</p><p class="rodape">${RODAPE}</p></section>`;

const plano = JSON.parse(readFileSync(join(PASTA_CONTEUDO, 'plano.json'), 'utf8')).semanas;
const caderno = extra('caderno');
const idsCaderno = caderno.blocos.find((b) => b.t === 'imprimir_receitas').ids;
const card = extra('cardapio12');
const marm = extra('marmitas');
const docs = {
  'caderno-de-receitas-para-imprimir': capa(caderno.titulo, caderno.resumo)
    + `<section class="pagina">${tabelaSemana(plano[0], 'Cardápio da geladeira: semana 1')}<p class="rodape">Cole na porta da geladeira. O cardápio completo de 4 semanas está no app, na tela Plano.</p></section>`
    + idsCaderno.map((id) => paginaReceita(porId[id])).join(''),
  'cardapio-de-12-semanas': capa(card.titulo, card.resumo)
    + card.blocos.find((b) => b.t === 'plano_semanas').semanas.map((sem, n) => {
      const ids = [...new Set(sem.flatMap((d) => REF.map(([k]) => d[k])))];
      return `<section class="pagina">${tabelaSemana(sem, `Semana ${n + 1}`)}<p class="rodape">As receitas estão no app: busque pelo nome.</p></section>
        <section class="pagina"><h2>Lista de compras da semana ${n + 1}</h2><p class="meta">Uma receita de cada prato. Confira o que já tem em casa antes de sair.</p><div class="colunas">${listaCompras(ids)}</div></section>`;
    }).join(''),
  'guia-de-marmitas-da-semana': capa(marm.titulo, marm.resumo) + `<section>${blocosTexto(marm.blocos)}<p class="rodape">${RODAPE}</p></section>`,
};

const pasta = join(RAIZ, 'docs', 'produtos');
mkdirSync(pasta, { recursive: true });
const { chromium } = createRequire(import.meta.url)('playwright');
const navegador = await chromium.launch();
const pagina = await navegador.newPage();
for (const [nome, corpo] of Object.entries(docs)) {
  await pagina.setContent(`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=DM+Serif+Display&display=swap" rel="stylesheet"><style>${ESTILO}</style><body>${corpo}</body></html>`, { waitUntil: 'networkidle' });
  await pagina.pdf({ path: join(pasta, `${nome}.pdf`), format: 'A4', printBackground: true, displayHeaderFooter: true, headerTemplate: '<span></span>', footerTemplate: '<div style="font-size:8px;color:#888;width:100%;text-align:center">Receitas Bem Leves · página <span class="pageNumber"></span> de <span class="totalPages"></span></div>', margin: { top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' } });
  console.log(`docs/produtos/${nome}.pdf`);
}
await navegador.close();
