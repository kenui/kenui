// Biblioteca de enfeites, desenhados uma vez só. Cada enfeite desenha UMA peça em (x, y),
// com escala k e rotação em graus. espalharEnfeite() distribui as peças sobre a área do prato.
import { h, r1 } from './base.mjs';

const g = (x, y, k, rot, ...filhos) => h('g', { transform: `translate(${r1(x)} ${r1(y)}) rotate(${r1(rot)}) scale(${k.toFixed(2)})` }, ...filhos);
const p = (d, fill, extra = {}) => h('path', { d, fill, ...extra });
const c0 = (cx, cy, r, fill, extra = {}) => h('circle', { cx, cy, r, fill, ...extra });
const e0 = (cx, cy, rx, ry, fill, extra = {}) => h('ellipse', { cx, cy, rx, ry, fill, ...extra });

export const ENFEITES = {
  banana_rodelas: { qtd: [4, 6], k: 1, peca: () => [e0(0, 0, 22, 14, '#F3E0A8', { stroke: '#E3C77E', strokeWidth: 3 }), e0(0, 0, 9, 5, '#E9D08F'), c0(-4, -1, 1.6, '#8A6A3A'), c0(4, 1, 1.6, '#8A6A3A'), c0(0, -3, 1.6, '#8A6A3A')] },
  morango: { qtd: [3, 5], k: 1, peca: () => [p('M0 -16 C14 -16 20 -4 14 8 C9 17 3 22 0 24 C-3 22 -9 17 -14 8 C-20 -4 -14 -16 0 -16Z', '#D3283E'), p('M-10 -14 L0 -22 L10 -14 L4 -12 L0 -18 L-4 -12Z', '#3E8A3A'), c0(-5, -2, 1.5, '#F6D774'), c0(5, 2, 1.5, '#F6D774'), c0(0, 10, 1.5, '#F6D774'), p('M-6 -8 q4 -4 8 -2', 'none', { stroke: '#fff', strokeWidth: 3, opacity: 0.5, strokeLinecap: 'round' })] },
  mirtilo: { qtd: [6, 9], k: 1, peca: () => [c0(0, 0, 9, '#3B3F78'), c0(-3, -3, 3, '#7C80B8', { opacity: 0.7 }), p('M-2 -8 l2 3 l2 -3', 'none', { stroke: '#22264F', strokeWidth: 1.5 })] },
  frutas_vermelhas: { qtd: [6, 9], k: 1, peca: (s) => (s.n() < 0.5
    ? [c0(0, 0, 9, '#3B3F78'), c0(-3, -3, 3, '#7C80B8', { opacity: 0.7 })]
    : [c0(0, 0, 10, '#C2284A'), c0(-4, -3, 3.5, '#E0567A'), c0(4, -2, 3.5, '#E0567A'), c0(0, 4, 3.5, '#E0567A')]) },
  lascas_chocolate: { qtd: [6, 10], k: 1, peca: () => [p('M-8 -4 L7 -6 L10 3 L-5 6Z', '#3A1B10'), p('M-6 -3 L5 -4', 'none', { stroke: '#7A4630', strokeWidth: 2 })] },
  cacau_po: { qtd: [14, 20], k: 1, peca: () => [c0(0, 0, 2.6, '#5B3221', { opacity: 0.75 })] },
  coco_ralado: { qtd: [14, 20], k: 1, peca: () => [p('M-5 0 q5 -4 10 0', 'none', { stroke: '#FFFFFF', strokeWidth: 3.2, strokeLinecap: 'round' })] },
  castanhas: { qtd: [4, 7], k: 1, peca: () => [e0(0, 0, 13, 9, '#B27A45'), p('M-10 0 q10 -5 20 0', 'none', { stroke: '#7A4E26', strokeWidth: 2 }), e0(-3, -3, 4, 2, '#D9A66E', { opacity: 0.8 })] },
  amendoim: { qtd: [5, 8], k: 1, peca: () => [p('M-11 0 C-11 -9 -2 -8 0 -4 C2 -8 11 -9 11 0 C11 9 2 8 0 4 C-2 8 -11 9 -11 0Z', '#D7A86E'), c0(-5, -1, 1.2, '#A87843'), c0(5, 1, 1.2, '#A87843')] },
  sementes: { qtd: [14, 22], k: 1, peca: (s) => [e0(0, 0, 2.6, 1.6, s.n() < 0.5 ? '#3B2B22' : '#8C6A3A')] },
  gergelim: { qtd: [16, 24], k: 1, peca: () => [e0(0, 0, 3, 1.7, '#FFF4DA', { stroke: '#D8C29A', strokeWidth: 0.6 })] },
  aveia: { qtd: [8, 12], k: 1, peca: () => [e0(0, 0, 6, 4, '#E8D3A8', { stroke: '#C9AE7C', strokeWidth: 1 })] },
  canela: { qtd: [12, 18], k: 1, peca: () => [c0(0, 0, 2.2, '#8B4A22', { opacity: 0.7 })] },
  queijo_derretido: { qtd: [2, 3], k: 1, peca: () => [p('M-34 -6 C-20 -16 18 -16 34 -6 C30 4 24 2 22 14 C18 20 14 12 12 4 C4 8 -6 6 -10 12 C-14 22 -20 18 -20 8 C-26 6 -34 4 -34 -6Z', '#F6CB5A'), p('M-20 -6 q16 -6 34 0', 'none', { stroke: '#FFF0B8', strokeWidth: 3, strokeLinecap: 'round', opacity: 0.8 })] },
  queijo_ralado: { qtd: [10, 16], k: 1, peca: () => [p('M-6 -1 l12 2', 'none', { stroke: '#F3D27A', strokeWidth: 3.4, strokeLinecap: 'round' })] },
  queijo_branco: { qtd: [5, 8], k: 1, peca: () => [p('M-7 -5 L5 -7 L8 4 L-5 6Z', '#FBF7EE', { stroke: '#E4DAC5', strokeWidth: 1.2 })] },
  presunto: { qtd: [2, 3], k: 1, peca: () => [p('M-28 -4 C-18 -18 18 -18 28 -4 C20 8 -20 8 -28 -4Z', '#E9A3A0'), p('M-24 -4 C-14 -12 14 -12 24 -4', 'none', { stroke: '#F6C9C3', strokeWidth: 3 })] },
  frango_desfiado: { qtd: [8, 12], k: 1, peca: (s) => [p(`M-10 ${r1(s.entre(-2, 2))} q10 -4 20 0`, 'none', { stroke: '#E2BE8C', strokeWidth: 4.5, strokeLinecap: 'round' })] },
  ovo_cozido: { qtd: [2, 3], k: 1, peca: () => [e0(0, 0, 18, 13, '#FFFFFF', { stroke: '#EDE4D6', strokeWidth: 1.5 }), c0(0, 0, 8, '#F2B73A')] },
  tomate: { qtd: [3, 5], k: 1, peca: () => [c0(0, 0, 15, '#D6402F'), c0(0, 0, 11, '#E8654C'), p('M0 -9 L0 9 M-8 -5 L8 5 M-8 5 L8 -5', 'none', { stroke: '#F4A487', strokeWidth: 2 }), c0(-4, -4, 1.6, '#F9E3A4'), c0(5, 3, 1.6, '#F9E3A4')] },
  folhas_verdes: { qtd: [3, 5], k: 1, peca: () => [p('M-20 6 C-14 -14 10 -18 22 -8 C12 4 -4 12 -20 6Z', '#5E9A47'), p('M-16 4 L18 -8', 'none', { stroke: '#8CC271', strokeWidth: 2 })] },
  ervas: { qtd: [8, 12], k: 1, peca: () => [p('M-5 2 C-3 -5 3 -6 6 -2 C3 2 -1 4 -5 2Z', '#4E8B3E')] },
  cenoura: { qtd: [4, 7], k: 1, peca: () => [c0(0, 0, 10, '#EE8B35'), c0(0, 0, 5, '#F6AE62')] },
  abobrinha: { qtd: [4, 6], k: 1, peca: () => [e0(0, 0, 15, 11, '#E7EBC0', { stroke: '#4F7B34', strokeWidth: 3 }), c0(-3, 0, 1.4, '#C9CF8F'), c0(3, 1, 1.4, '#C9CF8F')] },
  abobora: { qtd: [5, 7], k: 1, peca: () => [p('M-9 -6 L8 -8 L10 6 L-7 8Z', '#EE9A3C'), p('M-9 -6 L8 -8', 'none', { stroke: '#F7C27A', strokeWidth: 2 })] },
  pepino: { qtd: [4, 6], k: 1, peca: () => [c0(0, 0, 12, '#E3EFC6', { stroke: '#3F7A34', strokeWidth: 2.6 }), c0(0, 0, 4, '#CFE1A4')] },
  brocolis: { qtd: [3, 5], k: 1, peca: () => [p('M-3 4 L-3 14 L3 14 L3 4Z', '#8DBF6A'), c0(-7, -2, 8, '#3F7D35'), c0(5, -4, 8, '#46883A'), c0(0, -10, 7, '#3A7330')] },
  pimentao: { qtd: [4, 6], k: 1, peca: (s) => [p('M-12 0 q12 -8 24 0', 'none', { stroke: s.n() < 0.5 ? '#D63B2C' : '#F0B92E', strokeWidth: 5, strokeLinecap: 'round' })] },
  cogumelo: { qtd: [4, 6], k: 1, peca: () => [p('M-12 0 C-12 -12 12 -12 12 0Z', '#C9A47A'), p('M-4 0 L-4 9 L4 9 L4 0Z', '#EBDCC3')] },
  azeitona: { qtd: [4, 7], k: 1, peca: () => [e0(0, 0, 8, 6, '#3A3326'), e0(0, 0, 3, 2, '#7A6B4F')] },
  cebola_roxa: { qtd: [3, 5], k: 1, peca: () => [e0(0, 0, 14, 10, 'none', { stroke: '#8E3D78', strokeWidth: 3 }), e0(0, 0, 8, 5, 'none', { stroke: '#B76AA0', strokeWidth: 2 })] },
  milho: { qtd: [10, 16], k: 1, peca: () => [e0(0, 0, 4, 3.4, '#F2C94C', { stroke: '#D9A72E', strokeWidth: 0.8 })] },
  limao: { qtd: [2, 3], k: 1, peca: () => [c0(0, 0, 16, '#5C9E3A'), c0(0, 0, 13, '#D9EBA4'), p('M0 -12 L0 12 M-11 -6 L11 6 M-11 6 L11 -6', 'none', { stroke: '#F4FAD9', strokeWidth: 1.6 })] },
  laranja: { qtd: [2, 3], k: 1, peca: () => [c0(0, 0, 17, '#EE8A22'), c0(0, 0, 14, '#F8B54C'), p('M0 -13 L0 13 M-12 -6 L12 6 M-12 6 L12 -6', 'none', { stroke: '#FCDFA0', strokeWidth: 1.6 })] },
  maca: { qtd: [3, 5], k: 1, peca: () => [p('M-14 6 C-14 -10 14 -10 14 6Z', '#F8EDC9', { stroke: '#C43A36', strokeWidth: 3 }), c0(-3, 0, 1.5, '#5A3A22'), c0(3, 0, 1.5, '#5A3A22')] },
  abacaxi: { qtd: [3, 5], k: 1, peca: () => [p('M-10 8 L0 -12 L10 8Z', '#F5D05A'), p('M-10 8 L10 8', 'none', { stroke: '#D9A72E', strokeWidth: 3 })] },
  manga: { qtd: [5, 7], k: 1, peca: () => [p('M-8 -6 L8 -7 L9 6 L-7 7Z', '#F6A92C'), p('M-6 -4 L6 -5', 'none', { stroke: '#FBD27A', strokeWidth: 2 })] },
  maracuja: { qtd: [5, 8], k: 1, peca: () => [c0(0, 0, 6, '#F2C230', { opacity: 0.85 }), c0(0, 0, 2, '#2A1A10')] },
  uva: { qtd: [5, 8], k: 1, peca: () => [c0(0, 0, 9, '#6A2C5E'), c0(-3, -3, 3, '#A55A93', { opacity: 0.7 })] },
  calda: { qtd: [1, 1], k: 1, peca: () => [p('M-70 -10 C-40 10 -20 -20 10 0 C30 14 50 -6 70 6', 'none', { stroke: '#7A3A1E', strokeWidth: 7, strokeLinecap: 'round', opacity: 0.9 }), p('M-50 -4 C-36 4 -24 -8 -10 -2', 'none', { stroke: '#fff', strokeWidth: 2, opacity: 0.45, strokeLinecap: 'round' })] },
  chantilly: { qtd: [1, 3], k: 1, peca: () => [p('M-22 8 C-24 -4 -10 -10 -6 -16 C-2 -24 6 -22 6 -14 C14 -14 22 -6 22 8Z', '#FFFDF7', { stroke: '#EADFCC', strokeWidth: 1.5 }), p('M-12 0 q10 -8 20 -2', 'none', { stroke: '#EADFCC', strokeWidth: 2 })] },
};

// Distribui as peças de um enfeite numa elipse (a superfície de cima do prato ou da massa).
export function espalharEnfeite(nome, area, s, chave) {
  const def = ENFEITES[nome];
  if (!def) return null;
  const qtd = s.inteiro(def.qtd[0], def.qtd[1]);
  const pecas = [];
  if (nome === 'calda') {
    return h('g', { key: chave }, g(area.cx, area.cy, area.rx / 90, s.entre(-6, 6), ...def.peca(s)));
  }
  for (let i = 0; i < qtd; i++) {
    // Espalha em anéis para não amontoar no centro.
    const ang = (i / qtd) * Math.PI * 2 + s.entre(-0.4, 0.4);
    const raio = qtd === 1 ? 0 : Math.sqrt(s.entre(0.12, 0.9));
    const x = area.cx + Math.cos(ang) * area.rx * raio * 0.82;
    const y = area.cy + Math.sin(ang) * area.ry * raio * 0.75;
    const k = (area.k || 1) * def.k * s.entre(0.85, 1.12);
    pecas.push(h('g', { key: i }, g(x, y, k, s.entre(-40, 40), ...def.peca(s))));
  }
  return h('g', { key: chave }, ...pecas);
}
