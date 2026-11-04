// Gera o conteúdo dos produtos extras do funil, no mesmo formato de blocos dos bônus:
//   conteudo/extras/caderno.json     (order bump)  Caderno de Receitas para Imprimir: 100 receitas + cardápio da geladeira
//   conteudo/extras/cardapio12.json  (upsell e downsell) Cardápio de 12 Semanas com lista de compras por semana
//   conteudo/extras/marmitas.json    (upsell) Guia de Marmitas da Semana: preparar no domingo e congelar
// Uso: node scripts/gerar-extras.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { carregarReceitas, PASTA_CONTEUDO } from './lib/fontes.mjs';
import { ehAcompanhamento } from './lib/acompanhamento.mjs';
import { criarSorteio } from '../ilustracoes/base.mjs';

const receitas = carregarReceitas().map((x) => x.receita);
const porId = Object.fromEntries(receitas.map((r) => [r.id, r]));
const pasta = join(PASTA_CONTEUDO, 'extras');
mkdirSync(pasta, { recursive: true });
const gravar = (nome, dados) => writeFileSync(join(pasta, `${nome}.json`), JSON.stringify(dados, null, 2) + '\n');
const normal = receitas.filter((r) => r.categoria !== 'ceia');

// ---------- Caderno: 100 receitas escolhidas ----------
// Primeiro as 6 da página de vendas; depois, por categoria, as mais simples (menos ingredientes e menos tempo).
const COTAS = { paes_substitutos: 20, cafe_da_manha: 15, lanches: 15, almoco_jantar: 25, doces_bolos: 20, ceia: 5 };
const simplicidade = (r) => r.ingredientes.filter((i) => !i.opcional).length * 10 + r.tempo.total_min / 6;
const escolhidas = receitas.filter((r) => r.foto).map((r) => r.id);
for (const [cat, cota] of Object.entries(COTAS)) {
  const ja = escolhidas.filter((id) => porId[id].categoria === cat).length;
  const candidatas = receitas.filter((r) => r.categoria === cat && !escolhidas.includes(r.id) && !ehAcompanhamento(r))
    .sort((a, b) => simplicidade(a) - simplicidade(b) || a.id.localeCompare(b.id));
  escolhidas.push(...candidatas.slice(0, Math.max(0, cota - ja)).map((r) => r.id));
}
const caderno = escolhidas.slice(0, 100).sort();
gravar('caderno', {
  produto: 'caderno',
  slug: 'caderno-para-imprimir',
  titulo: 'Caderno de Receitas para Imprimir',
  resumo: '100 receitas escolhidas, uma por página, com letra grande, e o cardápio da semana para colar na geladeira.',
  blocos: [
    { t: 'p', texto: 'Aqui estão 100 receitas do app, escolhidas entre as mais simples de cada categoria, em versão para imprimir: uma receita por folha, com letra grande e espaço para anotar. Imprima tudo de uma vez ou só as que você mais faz.' },
    { t: 'lista', itens: [
      'No computador ou no celular, toque em "Imprimir o caderno" e escolha a impressora ou "Salvar como PDF".',
      'Papel A4, retrato. Se a impressora deixar, imprima frente e verso para gastar menos papel.',
      'Uma pasta com plásticos protege as folhas dos respingos na cozinha.',
    ] },
    { t: 'imprimir_receitas', texto: 'Imprimir o caderno (100 receitas)', ids: caderno },
    { t: 'h', texto: 'Cardápio da geladeira' },
    { t: 'p', texto: 'Uma folha com a semana 1 do Plano, para colar na porta da geladeira. Se você trocou alguma refeição no Plano, a troca aparece aqui.' },
    { t: 'plano_semana_imprimir', semana: 0, texto: 'Imprimir o cardápio da geladeira' },
    { t: 'h', texto: 'As receitas do caderno' },
    { t: 'receitas_ids', ids: caderno },
  ],
});

// ---------- Cardápio de 12 semanas ----------
const REFEICOES = ['cafe_da_manha', 'lanche', 'almoco', 'jantar'];
const MINIMO = { cafe_da_manha: 100, lanche: 80, almoco: 150, jantar: 150 };
const s = criarSorteio('cardapio-12-semanas');
const opcoes = {};
for (const ref of REFEICOES) {
  opcoes[ref] = normal.filter((r) => r.refeicoes_do_plano.includes(ref) && r.nutricao.por_porcao.kcal >= MINIMO[ref]
    && !(['almoco', 'jantar'].includes(ref) && ehAcompanhamento(r))).map((r) => r.id);
  for (let i = opcoes[ref].length - 1; i > 0; i--) {
    const j = Math.floor(s.n() * (i + 1));
    [opcoes[ref][i], opcoes[ref][j]] = [opcoes[ref][j], opcoes[ref][i]];
  }
}
const usos = {};
const semanas = [];
for (let sem = 0; sem < 12; sem++) {
  const naSemana = Object.fromEntries(REFEICOES.map((r) => [r, new Set()]));
  const dias = [];
  for (let d = 0; d < 7; d++) {
    const dia = {};
    const noDia = new Set();
    for (const ref of REFEICOES) {
      const candidatas = opcoes[ref].filter((id) => !naSemana[ref].has(id) && !noDia.has(id));
      candidatas.sort((a, b) => (usos[a] ?? 0) - (usos[b] ?? 0));
      const id = candidatas[0];
      dia[ref] = id;
      usos[id] = (usos[id] ?? 0) + 1;
      naSemana[ref].add(id);
      noDia.add(id);
    }
    dias.push(dia);
  }
  semanas.push(dias);
}
gravar('cardapio12', {
  produto: 'cardapio12',
  slug: 'cardapio-12-semanas',
  titulo: 'Cardápio de 12 Semanas',
  resumo: 'Três meses de café da manhã, lanche, almoço e jantar já decididos, com a lista de compras de cada semana.',
  blocos: [
    { t: 'p', texto: 'São 12 semanas de cardápio com as receitas do app, sem repetir prato na mesma semana. Escolha a semana, veja o que fazer em cada dia e gere a lista de compras com um toque.' },
    { t: 'lista', itens: [
      'Comece pela semana 1 ou pela que tiver mais pratos que você gosta.',
      'Os pratos de almoço que sobram podem virar o jantar do dia seguinte: anote no próprio cardápio.',
      'Quer trocar uma refeição? Use o Plano do app: lá cada refeição tem o botão Trocar.',
    ] },
    { t: 'plano_semanas', semanas },
  ],
});

// ---------- Guia de Marmitas ----------
const congela = (r) => (r.dicas ?? []).some((d) => /congel/i.test(d.texto));
const pratosMarmita = normal.filter((r) => ['almoco_jantar'].includes(r.categoria) && congela(r) && !ehAcompanhamento(r)).map((r) => r.id);
const acompanhamentos = normal.filter((r) => ehAcompanhamento(r) && congela(r)).map((r) => r.id);
const lanchesCongelam = normal.filter((r) => ['lanches', 'paes_substitutos', 'cafe_da_manha'].includes(r.categoria) && congela(r)).map((r) => r.id);
// 4 domingos de exemplo: 2 pratos principais + 1 acompanhamento + 1 lanche, sem repetir.
const domingos = [0, 1, 2, 3].map((i) => ({
  principais: pratosMarmita.slice(i * 2, i * 2 + 2),
  acompanhamento: acompanhamentos[i % Math.max(1, acompanhamentos.length)] ?? null,
  lanche: lanchesCongelam[i] ?? null,
}));
gravar('marmitas', {
  produto: 'marmitas',
  slug: 'guia-de-marmitas',
  titulo: 'Guia de Marmitas da Semana',
  resumo: 'Como cozinhar no domingo, em cerca de 2 horas, e ter almoço e jantar prontos para a semana.',
  blocos: [
    { t: 'p', texto: 'A semana fica muito mais fácil quando a comida já está pronta na geladeira e no congelador. Este guia mostra como organizar um domingo de cozinha, quais receitas do app congelam bem e como guardar e esquentar sem perder o sabor.' },
    { t: 'h', texto: 'O domingo de cozinha, passo a passo' },
    { t: 'lista', itens: [
      'Escolha 2 pratos principais, 1 acompanhamento e 1 lanche (veja os 4 domingos prontos abaixo).',
      'Gere a lista de compras dessas 4 receitas no app e faça as compras no sábado.',
      'Comece pelo que vai ao forno, porque é o que mais demora. Enquanto assa, cozinhe o que vai na panela.',
      'Por último, prepare o lanche e corte os legumes da semana.',
      'Espere a comida amornar (no máximo 2 horas fora da geladeira), divida em potes e guarde.',
    ] },
    { t: 'h', texto: 'Quanto tempo dura' },
    { t: 'tabela', cabecalho: ['Onde', 'Quanto tempo', 'Como fazer'], linhas: [
      ['Geladeira', 'até 3 dias', 'Potes bem fechados. O que você vai comer até quarta fica na geladeira.'],
      ['Congelador', 'até 2 meses', 'O que vai comer de quinta em diante vai para o congelador. Escreva o nome e a data na tampa.'],
      ['Descongelar', 'de um dia para o outro', 'Passe o pote do congelador para a geladeira na noite anterior. Não descongele em cima da pia.'],
      ['Esquentar', 'até ficar bem quente', 'No micro-ondas, mexa na metade do tempo. Esquente só a porção que vai comer.'],
    ] },
    { t: 'h', texto: 'Potes e porções' },
    { t: 'lista', itens: [
      'Potes de vidro com tampa servem para geladeira, congelador e micro-ondas (tire a tampa para esquentar).',
      'Monte a marmita como um prato: metade de legumes ou salada, um quarto de carne, frango, peixe ou ovo e um quarto de acompanhamento.',
      'Folhas e saladas cruas não congelam: guarde à parte e monte na hora.',
      'Arroz, feijão, carnes ensopadas, sopas, escondidinhos e molhos congelam bem.',
    ] },
    { t: 'h', texto: '4 domingos prontos' },
    { t: 'domingos', domingos },
    { t: 'h', texto: 'Pratos principais que congelam bem' },
    { t: 'receitas_ids', ids: pratosMarmita },
    { t: 'h', texto: 'Acompanhamentos que congelam bem' },
    { t: 'receitas_ids', ids: acompanhamentos },
    { t: 'h', texto: 'Lanches e pães que congelam bem' },
    { t: 'receitas_ids', ids: lanchesCongelam },
  ],
});

console.log(`caderno: ${caderno.length} receitas | cardápio: 12 semanas, ${Object.keys(usos).length} receitas diferentes | marmitas: ${pratosMarmita.length} principais, ${acompanhamentos.length} acompanhamentos, ${lanchesCongelam.length} lanches`);
