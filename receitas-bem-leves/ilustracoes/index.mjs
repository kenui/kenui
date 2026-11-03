// Ilustração de uma receita, montada a partir dos dados dela.
// - prato base e cor da massa vêm de receita.ilustracao;
// - enfeites só entram se algum ingrediente da receita tiver aquele enfeite (tabela ingrediente → enfeite
//   do cadastro). Assim nunca se desenha algo que a receita não tem;
// - variações (posição do prato, louça, enfeites) saem de um sorteio com semente fixa pelo id.
import { h, L, A, contexto, Mesa } from './base.mjs';
import { PRATOS } from './pratos.mjs';
import { espalharEnfeite, ENFEITES } from './enfeites.mjs';

export const PRATO_GENERICO = 'legumes_assados';

// Enfeites permitidos: os que algum ingrediente da receita realmente tem.
export function enfeitesDaReceita(receita, ingredientes) {
  const disponiveis = new Set();
  for (const i of receita.ingredientes ?? []) {
    const e = ingredientes?.[i.ingrediente]?.enfeite ?? i.enfeite;
    if (e) disponiveis.add(e);
  }
  const pedidos = receita.ilustracao?.enfeites ?? [];
  return pedidos.filter((e) => disponiveis.has(e) && ENFEITES[e]);
}

export function pratoDaReceita(receita) {
  const pedido = receita.ilustracao?.prato_base;
  return PRATOS[pedido] ? { nome: pedido, generico: false } : { nome: PRATO_GENERICO, generico: true };
}

export function Ilustracao({ receita, ingredientes, className }) {
  const prefixo = `il${receita.id.replace(/\D/g, '')}`;
  const c = contexto(receita, prefixo);
  const prato = pratoDaReceita(receita);
  const enfeites = enfeitesDaReceita(receita, ingredientes);
  const il = receita.ilustracao ?? {};
  const op = { massa: il.massa, cobertura: il.cobertura, recheio: il.recheio, enfeites };
  const mesa = Mesa({ c, categoria: receita.categoria });
  const { desenho, areas } = PRATOS[prato.nome](c, op);
  const camadas = [];
  enfeites.forEach((nome, i) => {
    const area = areas[i % areas.length];
    camadas.push(espalharEnfeite(nome, area, c.s, `e${i}`));
  });
  return h('svg', {
    xmlns: 'http://www.w3.org/2000/svg',
    viewBox: `0 0 ${L} ${A}`,
    role: 'img',
    'aria-label': receita.nome,
    className,
    preserveAspectRatio: 'xMidYMid slice',
  },
  h('defs', null, ...c.defs),
  // Aproxima a cena para o prato ocupar bem o quadro.
  h('g', { transform: 'translate(400 300) scale(1.3) translate(-400 -365)' }, mesa, desenho, ...camadas));
}
