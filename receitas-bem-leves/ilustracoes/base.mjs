// Peças comuns das ilustrações: sorteio com semente, cores, degradês, mesa, louça e sombra.
// Tudo é desenhado num viewBox fixo de 800 x 600, vista 3/4 (levemente de cima).
import { createElement } from 'react';

export const h = createElement;
export const L = 800;
export const A = 600;

// Sorteio previsível: a mesma receita sempre gera o mesmo desenho.
export function criarSorteio(texto) {
  let s = 2166136261;
  for (const c of String(texto)) s = Math.imul(s ^ c.charCodeAt(0), 16777619) >>> 0;
  const proximo = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    n: proximo,
    entre: (a, b) => a + proximo() * (b - a),
    inteiro: (a, b) => Math.floor(a + proximo() * (b - a + 1)),
    um: (lista) => lista[Math.floor(proximo() * lista.length)],
  };
}

export const r1 = (v) => Math.round(v);

export const MASSAS = {
  clara: ['#F4D9A3', '#E5BC77', '#C98D47'],
  chocolate: ['#7A4630', '#5B3221', '#3E2015'],
  cenoura: ['#F3AE63', '#E28E3F', '#B96B29'],
  banana: ['#EED083', '#DBB25B', '#B4863B'],
  integral: ['#D9B07A', '#C3935B', '#9A6A3A'],
  queijo: ['#F6D272', '#EAB54D', '#C98A2E'],
};

export const COBERTURAS = {
  calda_chocolate: ['#5A2E1C', '#3A1B10'],
  calda_morango: ['#D23A4E', '#A31F33'],
  calda_frutas_vermelhas: ['#9E2A4F', '#6E1736'],
  molho_tomate: ['#D9502F', '#B23A20'],
  molho_branco: ['#FBF4E4', '#E9DCC0'],
  chantilly: ['#FFFDF8', '#EFE6D6'],
  queijo_gratinado: ['#F2C15A', '#C98A2E'],
};

const LOUCAS = [
  ['#FFFFFF', '#E9E1D6'],
  ['#F7EFE4', '#E2D3BE'],
  ['#EEF3F2', '#D2DEDB'],
  ['#F6ECE9', '#E3CFC9'],
  ['#F3F0E6', '#DAD3BD'],
];

// Mesa: um elemento diferente por categoria.
const MESAS = {
  cafe_da_manha: { fundo: '#EAD7BC', pano: 'xadrez', cores: ['#F7F0E6', '#C9534F'] },
  paes_substitutos: { fundo: '#E7D3B6', pano: 'tabua', cores: ['#C08A55', '#A87240'] },
  lanches: { fundo: '#E3DCC2', pano: 'listras', cores: ['#F6EFE3', '#6F9A6B'] },
  almoco_jantar: { fundo: '#E8D2BF', pano: 'liso', cores: ['#C8684A', '#B25A3E'] },
  doces_bolos: { fundo: '#EED6CF', pano: 'bolinhas', cores: ['#F3D2CB', '#FBF3E8'] },
  ceia: { fundo: '#E2D3B5', pano: 'ceia', cores: ['#7B1E2C', '#C9A24B'] },
};

export function contexto(receita, prefixo) {
  const s = criarSorteio(receita.id);
  const louca = s.um(LOUCAS);
  const defs = [];
  const ids = new Set();
  // Degradê linear vertical (ou diagonal) com id único por ilustração.
  const grad = (nome, c1, c2, diagonal = false) => {
    const id = `${prefixo}-${nome}`;
    if (!ids.has(id)) {
      ids.add(id);
      defs.push(h('linearGradient', { key: id, id, x1: 0, y1: 0, x2: diagonal ? 1 : 0, y2: 1 },
        h('stop', { offset: 0, stopColor: c1 }), h('stop', { offset: 1, stopColor: c2 })));
    }
    return `url(#${id})`;
  };
  const radial = (nome, cor, opacidade = 0.35) => {
    const id = `${prefixo}-${nome}`;
    if (!ids.has(id)) {
      ids.add(id);
      defs.push(h('radialGradient', { key: id, id },
        h('stop', { offset: 0, stopColor: cor, stopOpacity: opacidade }),
        h('stop', { offset: 1, stopColor: cor, stopOpacity: 0 })));
    }
    return `url(#${id})`;
  };
  return { s, louca, defs, grad, radial, cx: 400 + r1(s.entre(-24, 24)), cy: 392, prefixo };
}

export function massaDe(nome) {
  return MASSAS[nome] || MASSAS.clara;
}

// Fundo: parede creme e o tampo da mesa com o elemento da categoria.
export function Mesa({ c, categoria }) {
  const m = MESAS[categoria] || MESAS.almoco_jantar;
  const partes = [
    h('rect', { key: 'p', x: -200, y: -200, width: L + 400, height: A + 400, fill: '#FBF3E8' }),
    h('rect', { key: 't', x: -200, y: 250, width: L + 400, height: 500, fill: m.fundo }),
    h('rect', { key: 'l', x: -200, y: 250, width: L + 400, height: 6, fill: '#000', opacity: 0.04 }),
  ];
  const [c1, c2] = m.cores;
  const x0 = c.cx - 330;
  if (m.pano === 'tabua') {
    partes.push(
      h('path', { key: 'tb', d: `M${x0 + 30} 300 L${x0 + 630} 300 Q${x0 + 690} 300 ${x0 + 700} 360 L${x0 + 720} 520 Q${x0 + 722} 560 ${x0 + 680} 560 L${x0 - 20} 560 Q${x0 - 60} 560 ${x0 - 56} 520 L${x0 - 30} 360 Q${x0 - 20} 300 ${x0 + 30} 300Z`, fill: c.grad('tabua', c1, c2) }),
      h('path', { key: 'tv', d: `M${x0} 350 Q${x0 + 300} 340 ${x0 + 660} 352 M${x0 - 10} 420 Q${x0 + 320} 410 ${x0 + 680} 424 M${x0 - 20} 495 Q${x0 + 330} 486 ${x0 + 700} 498`, stroke: '#8A5A31', strokeWidth: 2, fill: 'none', opacity: 0.35 }),
    );
  } else {
    const d = `M${x0} 300 L${x0 + 660} 300 L${x0 + 760} 680 L${x0 - 100} 680Z`;
    partes.push(h('path', { key: 'pn', d, fill: c1 }));
    if (m.pano === 'xadrez') {
      const linhas = [];
      for (let i = 0; i < 8; i++) {
        const t = i / 7;
        const xa = x0 + t * 660;
        const xb = x0 - 80 + t * 820;
        linhas.push(`M${r1(xa)} 300 L${r1(xb)} 600`);
      }
      for (let y = 330; y < 600; y += 46) linhas.push(`M0 ${y} L${L} ${y}`);
      partes.push(h('path', { key: 'xd', d: linhas.join(' '), stroke: c2, strokeWidth: 22, opacity: 0.32, clipPath: `url(#${c.prefixo}-pano)` }));
    } else if (m.pano === 'listras') {
      const linhas = [];
      for (let i = 1; i < 7; i++) {
        const t = i / 7;
        linhas.push(`M${r1(x0 + t * 660)} 300 L${r1(x0 - 80 + t * 820)} 600`);
      }
      partes.push(h('path', { key: 'ls', d: linhas.join(' '), stroke: c2, strokeWidth: 14, opacity: 0.55, clipPath: `url(#${c.prefixo}-pano)` }));
    } else if (m.pano === 'bolinhas') {
      const pontos = [];
      for (let y = 320; y < 600; y += 40) {
        const k = (y - 300) / 300;
        for (let x = x0 - 80 * k + 20; x < x0 + 660 + 80 * k; x += 54) pontos.push(`M${r1(x + ((y / 40) % 2) * 27)} ${y} a5 4 0 1 0 0.1 0`);
      }
      partes.push(h('path', { key: 'bl', d: pontos.join(' '), fill: c2, opacity: 0.9, clipPath: `url(#${c.prefixo}-pano)` }));
    } else if (m.pano === 'ceia') {
      partes.push(
        h('path', { key: 'fx', d: `M${x0 + 20} 318 L${x0 + 640} 318 M${x0 - 60} 582 L${x0 + 720} 582`, stroke: c2, strokeWidth: 6, opacity: 0.8 }),
        h('path', { key: 'rm', d: 'M44 270 q40 -30 90 -6 q-30 22 -90 6Z M90 262 q30 -40 76 -30 q-24 30 -76 30Z', fill: '#3F6B3A' }),
        h('circle', { key: 'b1', cx: 140, cy: 270, r: 9, fill: '#B3263A' }),
        h('circle', { key: 'b2', cx: 158, cy: 262, r: 7, fill: c2 }),
      );
    } else {
      partes.push(h('path', { key: 'gd', d: `M${x0 + 520} 520 L${x0 + 700} 520 L${x0 + 720} 600 L${x0 + 520} 600Z`, fill: '#F4E7D4', opacity: 0.9 }));
    }
    c.defs.push(h('clipPath', { key: `${c.prefixo}-pano`, id: `${c.prefixo}-pano` }, h('path', { d })));
  }
  return h('g', null, ...partes);
}

// Sombra de contato suave embaixo da louça.
export function Sombra({ c, x = c.cx, y = c.cy + 34, rx = 290, ry = 80 }) {
  return h('ellipse', { cx: x, cy: y, rx, ry, fill: c.radial('sombra', '#3A2414', 0.42) });
}

// Prato raso visto de cima, em 3/4.
export function Prato({ c, rx = 250, ry = 86, y = c.cy }) {
  const [claro, escuro] = c.louca;
  return h('g', null,
    Sombra({ c, y: y + 26, rx: rx + 30, ry: ry + 14 }),
    h('ellipse', { cx: c.cx, cy: y + 10, rx, ry, fill: escuro }),
    h('ellipse', { cx: c.cx, cy: y, rx, ry, fill: c.grad('louca', claro, escuro) }),
    h('ellipse', { cx: c.cx, cy: y - 4, rx: rx * 0.76, ry: ry * 0.72, fill: claro, stroke: escuro, strokeWidth: 3, opacity: 0.95 }),
  );
}

// Tigela funda.
export function Tigela({ c, rx = 190, y = c.cy - 20, altura = 120, conteudo = '#E8C07A', conteudo2 }) {
  const [claro, escuro] = c.louca;
  const ry = rx * 0.32;
  return h('g', null,
    Sombra({ c, y: y + altura + 6, rx: rx + 20, ry: 46 }),
    h('path', { d: `M${c.cx - rx} ${y} Q${c.cx - rx * 0.92} ${y + altura * 1.05} ${c.cx} ${y + altura} Q${c.cx + rx * 0.92} ${y + altura * 1.05} ${c.cx + rx} ${y}Z`, fill: c.grad('tigela', claro, escuro) }),
    h('ellipse', { cx: c.cx, cy: y, rx, ry, fill: escuro }),
    h('ellipse', { cx: c.cx, cy: y + 4, rx: rx - 12, ry: ry - 8, fill: c.grad('conteudo', conteudo, conteudo2 || conteudo) }),
  );
}

// Brilho: faixa clara curva por cima de uma forma.
export function Brilho({ d, opacidade = 0.35 }) {
  return h('path', { d, fill: 'none', stroke: '#FFFFFF', strokeWidth: 8, strokeLinecap: 'round', opacity: opacidade });
}
