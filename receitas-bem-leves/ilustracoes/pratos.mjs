// Pratos base. Cada um recebe o contexto (c) e as opções (massa, cobertura, cor do conteúdo)
// e devolve { desenho, areas }: areas são as elipses onde os enfeites podem ser colocados.
import { h, r1, massaDe, COBERTURAS, Prato, Tigela, Sombra, Brilho } from './base.mjs';

const k = (x) => ({ key: x });
const el = (cx, cy, rx, ry, fill, extra = {}) => h('ellipse', { cx: r1(cx), cy: r1(cy), rx: r1(rx), ry: r1(ry), fill, ...extra });
const pa = (d, fill, extra = {}) => h('path', { d, fill, ...extra });

// Cilindro em 3/4: lateral + tampo. Serve para bolo, torta, caneca, copo.
function cilindro(c, nome, cx, topo, rx, ry, alt, [cTopo, cLado, cEsc], extra = {}) {
  const lado = `M${r1(cx - rx)} ${r1(topo)} L${r1(cx - rx)} ${r1(topo + alt)} A${r1(rx)} ${r1(ry)} 0 0 0 ${r1(cx + rx)} ${r1(topo + alt)} L${r1(cx + rx)} ${r1(topo)}Z`;
  return h('g', { key: nome },
    pa(lado, c.grad(`${nome}-l`, cLado, cEsc)),
    el(cx, topo, rx, ry, extra.topo || c.grad(`${nome}-t`, cTopo, cLado)),
  );
}

// Tronco de cone (pudim, forminha de muffin, copo).
function tronco(c, nome, cx, topo, rxTopo, rxBase, ry, alt, cores, tampo = true) {
  const [cTopo, cLado, cEsc] = cores;
  const ryb = ry * (rxBase / rxTopo);
  const lado = `M${r1(cx - rxTopo)} ${r1(topo)} L${r1(cx - rxBase)} ${r1(topo + alt)} A${r1(rxBase)} ${r1(ryb)} 0 0 0 ${r1(cx + rxBase)} ${r1(topo + alt)} L${r1(cx + rxTopo)} ${r1(topo)}Z`;
  return h('g', { key: nome }, pa(lado, c.grad(`${nome}-l`, cLado, cEsc)), tampo ? el(cx, topo, rxTopo, ry, c.grad(`${nome}-t`, cTopo, cLado)) : null);
}

// Escorridos de calda pela lateral de um cilindro.
function escorrido(c, cx, topo, rx, ry, cor, s) {
  const pts = [];
  const n = 7;
  for (let i = 0; i <= n; i++) {
    const t = Math.PI - (i / n) * Math.PI;
    const x = cx + Math.cos(t) * rx;
    const y = topo + Math.sin(t) * ry;
    const gota = i % 2 ? s.entre(18, 40) : s.entre(6, 14);
    pts.push(`${r1(x)} ${r1(y + gota)}`);
  }
  const d = `M${r1(cx - rx)} ${r1(topo)} A${r1(rx)} ${r1(ry)} 0 0 1 ${r1(cx + rx)} ${r1(topo)} L${pts.reverse().join(' L')}Z`;
  return pa(d, cor);
}

// Bloco em 3/4 (brownie, fatia de pão, travessa).
function bloco(c, nome, x, y, larg, prof, alt, [cTopo, cFrente, cLado]) {
  const dx = prof * 0.55;
  const dy = prof * 0.45;
  return h('g', { key: nome },
    pa(`M${r1(x)} ${r1(y)} L${r1(x + larg)} ${r1(y)} L${r1(x + larg)} ${r1(y + alt)} L${r1(x)} ${r1(y + alt)}Z`, cFrente),
    pa(`M${r1(x + larg)} ${r1(y)} L${r1(x + larg + dx)} ${r1(y - dy)} L${r1(x + larg + dx)} ${r1(y - dy + alt)} L${r1(x + larg)} ${r1(y + alt)}Z`, cLado),
    pa(`M${r1(x)} ${r1(y)} L${r1(x + dx)} ${r1(y - dy)} L${r1(x + larg + dx)} ${r1(y - dy)} L${r1(x + larg)} ${r1(y)}Z`, cTopo),
  );
}

// Pontinhos de textura (miolo, furinhos, migalhas).
function pontos(c, cx, cy, rx, ry, n, cor, raio, s, opacidade = 0.5) {
  let d = '';
  for (let i = 0; i < n; i++) {
    const a = s.entre(0, Math.PI * 2);
    const r = Math.sqrt(s.n());
    const x = cx + Math.cos(a) * rx * r;
    const y = cy + Math.sin(a) * ry * r;
    const rr = raio * s.entre(0.6, 1.3);
    d += `M${r1(x - rr)} ${r1(y)}a${r1(rr)} ${r1(rr * 0.7)} 0 1 0 ${r1(rr * 2)} 0a${r1(rr)} ${r1(rr * 0.7)} 0 1 0 ${r1(-rr * 2)} 0`;
  }
  return pa(d, cor, { opacity: opacidade });
}

function corCobertura(nome) { return COBERTURAS[nome] || null; }

const CONTEUDO = {
  morango: ['#EC9AA8', '#D9707F'], frutas_vermelhas: ['#B5466A', '#8E2C50'], banana: ['#F1DFA0', '#E3C877'],
  chocolate: ['#7A4630', '#5B3221'], cenoura: ['#F3A458', '#E08A3C'], verde: ['#9CC26F', '#7EA552'],
  creme: ['#F7EEDB', '#E9DBBE'], cafe: ['#8A5A3A', '#5E3A24'], dourado: ['#F2C76A', '#D9A23E'],
  vermelho: ['#D9502F', '#B23A20'], laranja: ['#F5A43A', '#E08A22'], roxo: ['#7A3A6E', '#5A2450'],
};
export function corConteudo(op) {
  if (op.cobertura && COBERTURAS[op.cobertura]) return COBERTURAS[op.cobertura];
  const e = op.enfeites || [];
  if (op.massa === 'chocolate' || e.includes('cacau_po')) return CONTEUDO.chocolate;
  if (e.includes('frutas_vermelhas') || e.includes('mirtilo') || e.includes('uva')) return CONTEUDO.frutas_vermelhas;
  if (e.includes('morango')) return CONTEUDO.morango;
  if (e.includes('manga') || e.includes('laranja') || e.includes('maracuja')) return CONTEUDO.laranja;
  if (op.massa === 'cenoura' || e.includes('abobora') || e.includes('cenoura')) return CONTEUDO.cenoura;
  if (e.includes('folhas_verdes') || e.includes('abobrinha') || e.includes('brocolis')) return CONTEUDO.verde;
  if (op.massa === 'banana' || e.includes('banana_rodelas')) return CONTEUDO.banana;
  if (e.includes('tomate')) return CONTEUDO.vermelho;
  if (op.massa === 'integral') return CONTEUDO.cafe;
  if (op.massa === 'queijo') return CONTEUDO.dourado;
  return CONTEUDO.creme;
}

export const PRATOS = {
  bolo_redondo(c, op) {
    const m = massaDe(op.massa); const { cx, s } = c; const topo = 292;
    const cob = corCobertura(op.cobertura);
    return {
      desenho: h('g', null,
        Prato({ c, rx: 240, ry: 80, y: 400 }),
        cilindro(c, 'bolo', cx, topo, 168, 54, 96, m),
        pontos(c, cx, topo + 70, 150, 20, 26, m[2], 3, s, 0.35),
        cob ? escorrido(c, cx, topo, 168, 54, cob[1], s) : null,
        cob ? el(cx, topo, 162, 50, c.grad('cob', cob[0], cob[1])) : null,
        Brilho({ d: `M${cx - 120} ${topo - 20} Q${cx - 40} ${topo - 44} ${cx + 40} ${topo - 40}`, opacidade: cob ? 0.4 : 0.25 }),
      ),
      areas: [{ cx, cy: topo, rx: 140, ry: 40 }],
    };
  },
  bolo_forma(c, op) {
    const m = massaDe(op.massa); const { cx, s } = c; const cob = corCobertura(op.cobertura);
    return {
      desenho: h('g', null,
        Prato({ c, rx: 255, ry: 76, y: 404 }),
        pa(`M${cx - 180} 404 L${cx - 182} 318 Q${cx - 180} 276 ${cx - 130} 270 L${cx + 130} 270 Q${cx + 180} 276 ${cx + 182} 318 L${cx + 180} 404 Q${cx} 420 ${cx - 180} 404Z`, c.grad('lf', m[1], m[2])),
        pa(`M${cx - 170} 300 Q${cx - 150} 252 ${cx} 248 Q${cx + 150} 252 ${cx + 170} 300 Q${cx} 318 ${cx - 170} 300Z`, cob ? cob[0] : c.grad('lt', m[0], m[1])),
        cob ? pa(`M${cx - 170} 300 Q${cx} 318 ${cx + 170} 300 L${cx + 172} 318 Q${cx + 120} 340 ${cx + 100} 322 Q${cx + 40} 346 ${cx} 326 Q${cx - 60} 344 ${cx - 90} 324 Q${cx - 140} 342 ${cx - 172} 318Z`, cob[1]) : null,
        !cob ? pa(`M${cx - 110} 288 Q${cx - 30} 268 ${cx + 30} 284 Q${cx + 80} 270 ${cx + 120} 288`, 'none', { stroke: m[2], strokeWidth: 4, opacity: 0.6 }) : null,
        pontos(c, cx, 362, 160, 26, 24, m[2], 3, s, 0.3),
      ),
      areas: [{ cx, cy: 286, rx: 140, ry: 18 }],
    };
  },
  bolo_caneca(c, op) {
    const m = massaDe(op.massa); const { cx } = c; const [cl, es] = c.louca;
    return {
      desenho: h('g', null,
        Sombra({ c, y: 470, rx: 150, ry: 34 }),
        h('path', { d: `M${cx + 92} 340 C${cx + 160} 340 ${cx + 160} 430 ${cx + 92} 430`, fill: 'none', stroke: es, strokeWidth: 22 }),
        cilindro(c, 'cnc', cx, 300, 98, 30, 160, [cl, cl, es]),
        el(cx, 300, 86, 24, m[2]),
        pa(`M${cx - 88} 300 Q${cx - 80} 236 ${cx} 232 Q${cx + 80} 236 ${cx + 88} 300 Q${cx} 318 ${cx - 88} 300Z`, c.grad('dm', m[0], m[1])),
        Brilho({ d: `M${cx - 70} 380 L${cx - 70} 430`, opacidade: 0.5 }),
      ),
      areas: [{ cx, cy: 262, rx: 60, ry: 16, k: 0.8 }],
    };
  },
  muffin(c, op) {
    const m = massaDe(op.massa); const { cx } = c;
    const pos = [[cx - 115, 330], [cx + 115, 330], [cx, 392]];
    return {
      desenho: h('g', null, Prato({ c, rx: 250, ry: 84, y: 410 }), ...pos.map(([x, y], i) => h('g', k(i),
        tronco(c, `fm${i}`, x, y, 70, 52, 20, 70, ['#E9DCC8', '#D8C5A8', '#B9A07C'], false),
        pa(`M${x - 50} ${y + 16} L${x - 46} ${y + 64} M${x - 25} ${y + 18} L${x - 23} ${y + 68} M${x} ${y + 20} L${x} ${y + 70} M${x + 25} ${y + 18} L${x + 23} ${y + 68} M${x + 50} ${y + 16} L${x + 46} ${y + 64}`, 'none', { stroke: '#B9A07C', strokeWidth: 2 }),
        pa(`M${x - 80} ${y + 4} Q${x - 82} ${y - 64} ${x} ${y - 70} Q${x + 82} ${y - 64} ${x + 80} ${y + 4} Q${x} ${y + 24} ${x - 80} ${y + 4}Z`, c.grad('dmf', m[0], m[1])),
        Brilho({ d: `M${x - 50} ${y - 30} Q${x - 20} ${y - 56} ${x + 14} ${y - 54}`, opacidade: 0.3 }),
      ))),
      areas: pos.map(([x, y]) => ({ cx: x, cy: y - 34, rx: 52, ry: 22, k: 0.7 })),
    };
  },
  cookie(c, op) {
    const m = massaDe(op.massa); const { cx, s } = c;
    const pos = [[cx - 120, 360], [cx + 110, 352], [cx - 20, 330], [cx + 10, 420], [cx - 150, 432], [cx + 150, 430]];
    return {
      desenho: h('g', null, Prato({ c, rx: 260, ry: 88, y: 392 }), ...pos.map(([x, y], i) => h('g', k(i),
        el(x, y + 10, 66, 26, m[2]),
        el(x, y, 66, 26, c.grad('ck', m[0], m[1])),
        pa(`M${x - 30} ${y - 6} l16 6 l12 -8 M${x + 8} ${y + 8} l18 -4`, 'none', { stroke: m[2], strokeWidth: 2.5, opacity: 0.6 }),
        pontos(c, x, y, 50, 18, 6, m[2], 3, s, 0.45),
      ))),
      areas: pos.slice(0, 4).map(([x, y]) => ({ cx: x, cy: y, rx: 46, ry: 16, k: 0.65 })),
    };
  },
  brownie(c, op) {
    const m = massaDe(op.massa || 'chocolate'); const { cx } = c;
    const pos = [[cx - 170, 360], [cx + 10, 360], [cx - 90, 430]];
    return {
      desenho: h('g', null, Prato({ c, rx: 260, ry: 88, y: 410 }), ...pos.map(([x, y], i) => h('g', k(i),
        bloco(c, `bw${i}`, x, y, 140, 90, 52, [m[1], m[2], '#2E170D']),
        pa(`M${x + 20} ${y - 18} l30 -8 l26 10 l30 -6`, 'none', { stroke: m[0], strokeWidth: 3, opacity: 0.6 }),
      ))),
      areas: pos.map(([x, y]) => ({ cx: x + 95, cy: y - 20, rx: 55, ry: 14, k: 0.7 })),
    };
  },
  pudim(c, op) {
    const { cx, s } = c; const cob = corCobertura(op.cobertura) || ['#C98A3E', '#9C6224'];
    const m = op.massa === 'chocolate' ? massaDe('chocolate') : ['#F8E7B8', '#EDD08D', '#CFA764'];
    return {
      desenho: h('g', null,
        Prato({ c, rx: 245, ry: 80, y: 404 }),
        tronco(c, 'pd', cx, 290, 120, 168, 40, 104, m),
        el(cx, 290, 120, 40, c.grad('pdc', cob[0], cob[1])),
        escorrido(c, cx, 290, 120, 40, cob[1], s),
        el(cx, 290, 34, 11, cob[1], { opacity: 0.9 }),
        el(cx, 290, 26, 8, '#5A2E1C', { opacity: 0.55 }),
        Brilho({ d: `M${cx - 90} 272 Q${cx - 40} 254 ${cx + 10} 256`, opacidade: 0.5 }),
      ),
      areas: [{ cx, cy: 290, rx: 92, ry: 26, k: 0.85 }],
    };
  },
  mousse_taca(c, op) {
    const { cx } = c; const cor = corConteudo(op);
    return {
      desenho: h('g', null,
        Sombra({ c, y: 494, rx: 150, ry: 30 }),
        el(cx, 488, 90, 22, '#E7E2DA', { stroke: '#CFC6B8', strokeWidth: 2 }),
        pa(`M${cx - 10} 488 L${cx - 8} 400 L${cx + 8} 400 L${cx + 10} 488Z`, '#EEE9E1'),
        pa(`M${cx - 130} 250 Q${cx - 128} 400 ${cx} 404 Q${cx + 128} 400 ${cx + 130} 250Z`, '#F3EFE8', { opacity: 0.55, stroke: '#D9D1C4', strokeWidth: 3 }),
        pa(`M${cx - 120} 276 Q${cx - 118} 390 ${cx} 394 Q${cx + 118} 390 ${cx + 120} 276Z`, c.grad('ms', cor[0], cor[1])),
        el(cx, 276, 120, 30, cor[0]),
        el(cx, 250, 130, 32, 'none', { stroke: '#D9D1C4', strokeWidth: 3 }),
        Brilho({ d: `M${cx - 100} 300 Q${cx - 96} 360 ${cx - 60} 384`, opacidade: 0.6 }),
      ),
      areas: [{ cx, cy: 274, rx: 92, ry: 20, k: 0.85 }],
    };
  },
  torta(c, op) {
    const m = massaDe(op.massa); const crosta = massaDe('integral'); const { cx, s } = c;
    const recheio = corConteudo(op);
    return {
      desenho: h('g', null,
        Prato({ c, rx: 250, ry: 84, y: 402 }),
        cilindro(c, 'tt', cx, 330, 182, 62, 46, crosta),
        el(cx, 330, 160, 52, c.grad('rch', recheio[0], recheio[1])),
        pa(Array.from({ length: 16 }, (_, i) => { const a = (i / 16) * Math.PI * 2; return `M${r1(cx + Math.cos(a) * 171)} ${r1(330 + Math.sin(a) * 57)} a8 6 0 1 0 0.1 0`; }).join(' '), crosta[0]),
        pontos(c, cx, 330, 130, 40, 10, recheio[1], 4, s, 0.3),
        op.massa === 'chocolate' ? null : el(cx - 60, 316, 40, 10, '#fff', { opacity: 0.25 }),
        m ? null : null,
      ),
      areas: [{ cx, cy: 330, rx: 128, ry: 38 }],
    };
  },
  pave(c, op) {
    const { cx } = c; const cor = corConteudo(op); const m = massaDe(op.massa);
    const x = cx - 190; const y = 300;
    return {
      desenho: h('g', null,
        Sombra({ c, y: 470, rx: 270, ry: 40 }),
        pa(`M${x} ${y} L${x + 380} ${y} L${x + 370} ${y + 150} Q${x + 190} ${y + 160} ${x + 10} ${y + 150}Z`, '#F4F1EC', { opacity: 0.6, stroke: '#D9D1C4', strokeWidth: 3 }),
        pa(`M${x + 12} ${y + 20} L${x + 368} ${y + 20} L${x + 366} ${y + 50} L${x + 14} ${y + 50}Z`, '#F7EEDB'),
        pa(`M${x + 14} ${y + 50} L${x + 366} ${y + 50} L${x + 364} ${y + 80} L${x + 16} ${y + 80}Z`, m[1]),
        pa(`M${x + 16} ${y + 80} L${x + 364} ${y + 80} L${x + 362} ${y + 112} L${x + 18} ${y + 112}Z`, cor[0]),
        pa(`M${x + 18} ${y + 112} L${x + 362} ${y + 112} L${x + 360} ${y + 142} Q${x + 190} ${y + 150} ${x + 20} ${y + 142}Z`, m[2]),
        pa(`M${x + 12} ${y + 20} L${x + 60} ${y - 16} L${x + 420} ${y - 16} L${x + 368} ${y + 20}Z`, '#FBF4E4'),
        Brilho({ d: `M${x + 30} ${y + 30} L${x + 30} ${y + 130}`, opacidade: 0.5 }),
      ),
      areas: [{ cx: cx + 20, cy: y + 2, rx: 160, ry: 14, k: 0.8 }],
    };
  },
  docinhos(c, op) {
    const m = op.massa === 'chocolate' ? massaDe('chocolate') : op.massa ? massaDe(op.massa) : ['#FBF6EC', '#EFE5D3', '#D8CAB0'];
    const { cx } = c;
    const pos = [[cx - 150, 350], [cx - 50, 330], [cx + 50, 330], [cx + 150, 350], [cx - 100, 420], [cx, 430], [cx + 100, 420]];
    return {
      desenho: h('g', null, Prato({ c, rx: 260, ry: 88, y: 400 }), ...pos.map(([x, y], i) => h('g', k(i),
        tronco(c, `fd${i}`, x, y, 42, 32, 13, 22, ['#8A4A2A', '#7A3E22', '#5A2C16'], false),
        h('circle', { cx: x, cy: y - 10, r: 34, fill: c.grad('bola', m[0], m[2], true) }),
        h('circle', { cx: x - 12, cy: y - 22, r: 8, fill: '#fff', opacity: 0.35 }),
      ))),
      areas: pos.map(([x, y]) => ({ cx: x, cy: y - 18, rx: 22, ry: 14, k: 0.45 })),
    };
  },
  pao_forma(c, op) {
    const m = massaDe(op.massa || 'integral'); const { cx, s } = c;
    return {
      desenho: h('g', null,
        Sombra({ c, y: 440, rx: 280, ry: 60 }),
        pa(`M${cx - 200} 410 L${cx - 200} 320 Q${cx - 196} 262 ${cx - 120} 256 L${cx + 60} 256 Q${cx + 120} 262 ${cx + 120} 320 L${cx + 120} 410Z`, c.grad('pfl', m[1], m[2])),
        pa(`M${cx - 196} 300 Q${cx - 180} 226 ${cx - 40} 222 Q${cx + 100} 226 ${cx + 116} 300 Q${cx - 40} 314 ${cx - 196} 300Z`, c.grad('pft', m[1], m[2])),
        pa(`M${cx - 150} 270 l40 -20 M${cx - 80} 262 l40 -22 M${cx - 10} 262 l40 -20`, 'none', { stroke: m[0], strokeWidth: 6, strokeLinecap: 'round', opacity: 0.7 }),
        h('g', { transform: `rotate(-8 ${cx + 190} 380)` },
          pa(`M${cx + 130} 440 L${cx + 130} 330 Q${cx + 130} 300 ${cx + 170} 296 L${cx + 230} 296 Q${cx + 262} 300 ${cx + 262} 330 L${cx + 262} 440Z`, m[2]),
          pa(`M${cx + 138} 436 L${cx + 138} 334 Q${cx + 138} 306 ${cx + 172} 304 L${cx + 228} 304 Q${cx + 254} 306 ${cx + 254} 334 L${cx + 254} 436Z`, '#F3E2C2'),
          pontos(c, cx + 196, 370, 50, 56, 22, '#C9A77A', 3, s, 0.6),
        ),
      ),
      areas: [{ cx: cx - 40, cy: 274, rx: 120, ry: 16, k: 0.8 }],
    };
  },
  pao_frigideira(c, op) {
    const m = massaDe(op.massa); const { cx, s } = c;
    const metade = (x, i) => h('g', k(i),
      pa(`M${x - 110} 360 A110 40 0 0 0 ${x + 110} 360 L${x + 110} 384 A110 40 0 0 1 ${x - 110} 384Z`, m[2]),
      el(x, 360, 110, 40, i ? '#F3E2BE' : c.grad('pfr', m[0], m[1])),
      i ? pontos(c, x, 360, 90, 30, 30, '#D2B07E', 3, s, 0.7) : pa(`M${x - 60} 352 q30 -14 60 -6`, 'none', { stroke: m[2], strokeWidth: 3, opacity: 0.5 }),
    );
    return {
      desenho: h('g', null, Prato({ c, rx: 260, ry: 88, y: 400 }), metade(cx - 100, 0), metade(cx + 110, 1)),
      areas: [{ cx: cx - 100, cy: 356, rx: 80, ry: 26, k: 0.7 }],
    };
  },
  pao_de_queijo(c, op) {
    const m = massaDe(op.massa || 'queijo'); const { cx, s } = c;
    const pos = [[cx - 130, 360], [cx - 40, 334], [cx + 60, 338], [cx + 145, 366], [cx - 90, 420], [cx + 20, 428], [cx + 120, 420]];
    return {
      desenho: h('g', null, Prato({ c, rx: 260, ry: 88, y: 396 }), ...pos.map(([x, y], i) => h('g', k(i),
        el(x, y + 14, 46, 20, m[2], { opacity: 0.6 }),
        h('circle', { cx: x, cy: y - 6, r: 44, fill: c.grad('pq', m[0], m[2], true) }),
        pa(`M${x - 18} ${y - 26} q10 6 18 -2 q8 8 16 2`, 'none', { stroke: m[2], strokeWidth: 3, opacity: 0.6 }),
        h('circle', { cx: x - 14, cy: y - 22, r: 9, fill: '#fff', opacity: 0.3 }),
      ))),
      areas: pos.slice(0, 4).map(([x, y]) => ({ cx: x, cy: y - 20, rx: 22, ry: 12, k: 0.5 })),
    };
  },
  tapioca(c, op) { return meiaLua(c, op, ['#FBF8F1', '#EEE6D6', '#D9CCB4'], 'tp'); },
  crepioca(c, op) { return meiaLua(c, op, ['#F6DE9A', '#EAC874', '#C99C48'], 'cr'); },
  omelete(c, op) { return meiaLua(c, op, ['#F7D766', '#EBC048', '#C99A28'], 'om', true); },
  panqueca_pilha(c, op) {
    const m = massaDe(op.massa); const { cx, s } = c; const cob = corCobertura(op.cobertura);
    const camadas = [];
    for (let i = 0; i < 4; i++) {
      const y = 380 - i * 22;
      camadas.push(h('g', k(i), el(cx + s.entre(-6, 6), y + 8, 140, 46, m[2]), el(cx + s.entre(-6, 6), y, 140, 46, c.grad('pk', m[0], m[1]))));
    }
    return {
      desenho: h('g', null, Prato({ c, rx: 250, ry: 84, y: 404 }), ...camadas,
        pontos(c, cx, 314, 100, 30, 26, m[2], 3, s, 0.45),
        cob ? pa(`M${cx - 90} 300 Q${cx} 330 ${cx + 90} 302 Q${cx + 120} 320 ${cx + 118} 352 L${cx + 110} 340 Q${cx + 40} 340 ${cx - 40} 336 L${cx - 60} 360 L${cx - 70} 330Z`, cob[1], { opacity: 0.9 }) : null),
      areas: [{ cx, cy: 314, rx: 100, ry: 30 }],
    };
  },
  panqueca_enrolada(c, op) {
    const m = massaDe(op.massa); const { cx } = c; const cob = corCobertura(op.cobertura) || COBERTURAS.molho_tomate;
    const rolos = [0, 1, 2].map((i) => {
      const y = 330 + i * 46;
      return h('g', k(i), pa(`M${cx - 170} ${y} L${cx + 170} ${y} A22 30 0 0 1 ${cx + 170} ${y + 56} L${cx - 170} ${y + 56}Z`, c.grad('rl', m[0], m[2])), el(cx - 170, y + 28, 20, 28, m[1]), el(cx - 170, y + 28, 12, 18, '#E9D4B0'));
    });
    return {
      desenho: h('g', null,
        Sombra({ c, y: 470, rx: 290, ry: 60 }),
        el(cx, 410, 260, 92, c.louca[1]), el(cx, 400, 250, 86, c.louca[0]),
        ...rolos,
        pa(`M${cx - 160} 360 Q${cx - 60} 330 ${cx + 40} 360 Q${cx + 120} 390 ${cx + 170} 360 L${cx + 170} 400 Q${cx + 80} 430 ${cx} 410 Q${cx - 80} 390 ${cx - 160} 410Z`, cob[0], { opacity: 0.92 }),
      ),
      areas: [{ cx, cy: 380, rx: 150, ry: 30 }],
    };
  },
  waffle(c, op) {
    const m = massaDe(op.massa); const { cx } = c;
    const um = (x, y, i) => {
      const linhas = [];
      for (let j = -3; j <= 3; j++) linhas.push(`M${x + j * 26 - 50} ${y - 40} L${x + j * 26 + 50} ${y + 40}`, `M${x + j * 26 + 50} ${y - 40} L${x + j * 26 - 50} ${y + 40}`);
      return h('g', k(i), el(x, y + 10, 110, 40, m[2]), el(x, y, 110, 40, c.grad('wf', m[0], m[1])),
        h('clipPath', { id: `${c.prefixo}-w${i}` }, el(x, y, 100, 34, '#000')),
        pa(linhas.join(' '), 'none', { stroke: m[2], strokeWidth: 5, opacity: 0.55, clipPath: `url(#${c.prefixo}-w${i})` }));
    };
    return { desenho: h('g', null, Prato({ c, rx: 255, ry: 86, y: 400 }), um(cx - 90, 380, 0), um(cx + 70, 344, 1)), areas: [{ cx: cx + 70, cy: 344, rx: 80, ry: 26, k: 0.75 }] };
  },
  ovos_mexidos(c, op) {
    const { cx, s } = c; const bolhas = [];
    for (let i = 0; i < 14; i++) {
      const a = s.entre(0, Math.PI * 2); const r = Math.sqrt(s.n());
      bolhas.push(el(cx + Math.cos(a) * 120 * r, 380 + Math.sin(a) * 40 * r, s.entre(30, 48), s.entre(18, 28), i % 3 ? '#F6D865' : '#F2C94C'));
    }
    return { desenho: h('g', null, Prato({ c }), ...bolhas.map((b, i) => h('g', k(i), b)), Brilho({ d: `M${cx - 80} 364 q40 -16 80 -6`, opacidade: 0.35 })), areas: [{ cx, cy: 376, rx: 120, ry: 34, k: 0.85 }] };
  },
  misto_quente(c, op) {
    const m = massaDe(op.massa || 'clara'); const { cx } = c;
    const tri = (x, y, i, rot) => h('g', { key: i, transform: `rotate(${rot} ${x} ${y})` },
      pa(`M${x - 120} ${y + 40} L${x + 120} ${y + 40} L${x - 100} ${y - 60}Z`, m[2]),
      pa(`M${x - 118} ${y + 26} L${x + 112} ${y + 26} L${x - 96} ${y - 50}Z`, '#E9A3A0'),
      pa(`M${x - 118} ${y + 20} L${x + 116} ${y + 20} L${x - 100} ${y - 58} Q${x - 70} ${y - 20} ${x + 40} ${y + 6}Z`, '#F6CB5A'),
      pa(`M${x - 120} ${y + 10} L${x + 120} ${y + 10} L${x - 100} ${y - 80}Z`, c.grad('ms1', m[0], m[1])),
      pa(`M${x - 70} ${y - 30} l40 10 m-20 -30 l50 14`, 'none', { stroke: m[2], strokeWidth: 5, opacity: 0.6 }),
    );
    return { desenho: h('g', null, Prato({ c }), tri(cx - 40, 400, 'a', 0), tri(cx + 60, 360, 'b', 14)), areas: [{ cx: cx + 150, cy: 410, rx: 60, ry: 22, k: 0.7 }] };
  },
  wrap(c, op) {
    const m = massaDe(op.massa || 'clara'); const { cx } = c; const cor = corConteudo(op);
    const rolo = (x, y, i) => h('g', k(i),
      pa(`M${x - 60} ${y} L${x - 60} ${y + 110} A60 22 0 0 0 ${x + 60} ${y + 110} L${x + 60} ${y}Z`, c.grad('wr', m[0], m[1])),
      el(x, y, 60, 22, m[0]), el(x, y, 50, 17, cor[0]), el(x - 10, y - 2, 26, 9, '#7DB060'), el(x + 16, y + 3, 16, 7, '#E9A3A0'),
      pa(`M${x - 40} ${y + 30} Q${x} ${y + 50} ${x + 40} ${y + 30}`, 'none', { stroke: m[2], strokeWidth: 3, opacity: 0.4 }),
    );
    return { desenho: h('g', null, Prato({ c }), rolo(cx - 75, 290, 0), rolo(cx + 75, 300, 1)), areas: [{ cx, cy: 440, rx: 160, ry: 18, k: 0.7 }] };
  },
  sanduiche(c, op) {
    const m = massaDe(op.massa || 'integral'); const { cx } = c;
    return {
      desenho: h('g', null, Prato({ c }),
        el(cx, 400, 170, 48, m[2]), el(cx, 392, 170, 46, m[1]),
        pa(`M${cx - 180} 380 q20 -24 40 0 q20 -24 40 0 q20 -24 40 0 q20 -24 40 0 q20 -24 40 0 q20 -24 40 0 q20 -24 40 0 q20 -24 40 0 q20 -24 40 0 L${cx + 180} 388 L${cx - 180} 388Z`, '#6FA24F'),
        el(cx, 372, 160, 40, '#E9A3A0'), el(cx - 10, 362, 158, 38, '#D6402F'), el(cx, 352, 166, 40, '#F6CB5A'),
        pa(`M${cx - 172} 346 Q${cx - 168} 272 ${cx} 266 Q${cx + 168} 272 ${cx + 172} 346 Q${cx} 372 ${cx - 172} 346Z`, c.grad('sd', m[0], m[1])),
        Brilho({ d: `M${cx - 110} 312 Q${cx - 40} 284 ${cx + 30} 288`, opacidade: 0.3 }),
      ),
      areas: [{ cx, cy: 300, rx: 120, ry: 22, k: 0.8 }],
    };
  },
  pizza(c, op) {
    const m = massaDe(op.massa || 'clara'); const { cx, s } = c; const molho = corCobertura(op.cobertura) || COBERTURAS.molho_tomate;
    return {
      desenho: h('g', null, Prato({ c, rx: 262, ry: 90 }),
        el(cx, 396, 220, 74, m[2]), el(cx, 388, 220, 74, c.grad('pz', m[0], m[1])),
        el(cx, 388, 190, 62, molho[0]),
        pontos(c, cx, 388, 170, 54, 14, '#F6D06A', 22, s, 0.95),
        pa(`M${cx} 388 L${cx - 120} 336 M${cx} 388 L${cx + 160} 350 M${cx} 388 L${cx + 20} 450`, 'none', { stroke: m[2], strokeWidth: 3, opacity: 0.5 }),
      ),
      areas: [{ cx, cy: 388, rx: 160, ry: 50 }],
    };
  },
  bolinhos_salgados(c, op) {
    const m = massaDe(op.massa || 'clara'); const { cx, s } = c;
    const pos = [[cx - 140, 370], [cx - 50, 340], [cx + 50, 344], [cx + 140, 372], [cx - 90, 430], [cx + 10, 436], [cx + 110, 426]];
    return {
      desenho: h('g', null, Prato({ c, rx: 260, ry: 88, y: 400 }), ...pos.map(([x, y], i) => h('g', k(i),
        pa(`M${x} ${y - 58} C${x + 18} ${y - 38} ${x + 44} ${y - 10} ${x + 40} ${y + 10} C${x + 36} ${y + 30} ${x - 36} ${y + 30} ${x - 40} ${y + 10} C${x - 44} ${y - 10} ${x - 18} ${y - 38} ${x} ${y - 58}Z`, c.grad('cx', m[1], m[2])),
        pontos(c, x, y, 26, 20, 8, '#8A5A2A', 2, s, 0.4),
        Brilho({ d: `M${x - 18} ${y - 18} q4 -16 14 -26`, opacidade: 0.3 }),
      ))),
      areas: [{ cx, cy: 452, rx: 190, ry: 20, k: 0.6 }],
    };
  },
  pate_com_palitos(c, op) {
    const { cx } = c; const cor = !op.massa || op.massa === 'clara' ? CONTEUDO.creme : corConteudo(op);
    return {
      desenho: h('g', null, Prato({ c, rx: 260, ry: 90 }),
        Tigela({ c, rx: 92, y: 340, altura: 70, conteudo: cor[0], conteudo2: cor[1] }),
        pa(`M${cx - 30} 340 q20 -12 50 -2 q-20 8 -50 2`, 'none', { stroke: '#fff', strokeWidth: 4, opacity: 0.5 }),
      ),
      areas: [{ cx: cx - 170, cy: 410, rx: 60, ry: 30, k: 0.9 }, { cx: cx + 170, cy: 410, rx: 60, ry: 30, k: 0.9 }, { cx, cy: 452, rx: 80, ry: 16, k: 0.8 }],
    };
  },
  salada(c, op) {
    const { cx, s } = c; const folhas = [];
    for (let i = 0; i < 12; i++) {
      const x = cx + s.entre(-130, 130); const y = 300 + s.entre(-16, 26);
      folhas.push(pa(`M${r1(x - 40)} ${r1(y + 10)} C${r1(x - 30)} ${r1(y - 30)} ${r1(x + 20)} ${r1(y - 34)} ${r1(x + 44)} ${r1(y - 6)} C${r1(x + 20)} ${r1(y + 14)} ${r1(x - 10)} ${r1(y + 20)} ${r1(x - 40)} ${r1(y + 10)}Z`, i % 3 ? '#6FA24F' : '#8CC271', { key: i }));
    }
    return { desenho: h('g', null, Tigela({ c, rx: 200, y: 320, altura: 120, conteudo: '#5E9A47' }), ...folhas), areas: [{ cx, cy: 300, rx: 150, ry: 34 }] };
  },
  sopa(c, op) {
    const { cx } = c; const cor = corConteudo(op);
    return {
      desenho: h('g', null, Prato({ c, rx: 250, ry: 84, y: 420 }), Tigela({ c, rx: 190, y: 340, altura: 100, conteudo: cor[0], conteudo2: cor[1] }),
        pa(`M${cx - 60} 336 q30 -12 70 -2`, 'none', { stroke: '#fff', strokeWidth: 5, opacity: 0.4 }),
        pa(`M${cx - 40} 280 q-14 -20 0 -40 q14 -20 0 -40 M${cx + 30} 284 q-14 -20 0 -40 q14 -20 0 -40`, 'none', { stroke: '#E9DCC8', strokeWidth: 5, strokeLinecap: 'round', opacity: 0.8 })),
      areas: [{ cx, cy: 344, rx: 140, ry: 38 }],
    };
  },
  frango(c, op) {
    const { cx, s } = c; const pecas = [];
    const pos = [[cx - 110, 370, -14], [cx + 20, 344, 6], [cx + 120, 392, 18], [cx - 20, 420, -4]];
    pos.forEach(([x, y, r], i) => pecas.push(h('g', { key: i, transform: `rotate(${r} ${x} ${y})` },
      pa(`M${x - 66} ${y} C${x - 70} ${y - 46} ${x + 40} ${y - 56} ${x + 66} ${y - 14} C${x + 80} ${y + 20} ${x + 30} ${y + 40} ${x - 20} ${y + 36} C${x - 50} ${y + 32} ${x - 64} ${y + 20} ${x - 66} ${y}Z`, c.grad('fr', '#E3A659', '#B2662A', true)),
      pontos(c, x, y - 4, 44, 22, 8, '#8A4A1A', 3, s, 0.35),
      Brilho({ d: `M${x - 40} ${y - 22} q30 -20 70 -10`, opacidade: 0.35 }))));
    return { desenho: h('g', null, Prato({ c, rx: 262, ry: 90 }), ...pecas), areas: [{ cx, cy: 380, rx: 200, ry: 56, k: 0.85 }] };
  },
  carne(c, op) {
    const { cx } = c; const fatias = [];
    for (let i = 0; i < 5; i++) {
      const x = cx - 150 + i * 62; const y = 378 - (i % 2) * 10;
      fatias.push(h('g', k(i), el(x, y, 58, 44, '#7A3E22'), el(x, y - 2, 50, 37, c.grad('cn', '#C98A6A', '#A86448')), el(x - 8, y - 6, 22, 14, '#D9A58A', { opacity: 0.6 })));
    }
    return { desenho: h('g', null, Prato({ c, rx: 262, ry: 90 }), ...fatias), areas: [{ cx, cy: 376, rx: 200, ry: 52, k: 0.9 }] };
  },
  peixe(c, op) {
    const { cx } = c;
    const fil = (x, y, i) => h('g', k(i),
      pa(`M${x - 130} ${y} C${x - 110} ${y - 50} ${x + 90} ${y - 54} ${x + 130} ${y - 10} C${x + 120} ${y + 30} ${x - 100} ${y + 40} ${x - 130} ${y}Z`, c.grad('px', '#F6E1BE', '#E1B97E', true)),
      pa(`M${x - 90} ${y - 20} l30 30 M${x - 40} ${y - 30} l30 34 M${x + 10} ${y - 32} l30 34 M${x + 60} ${y - 28} l26 30`, 'none', { stroke: '#B07A3A', strokeWidth: 5, opacity: 0.55 }));
    return { desenho: h('g', null, Prato({ c, rx: 262, ry: 90 }), fil(cx - 20, 370, 0), fil(cx + 30, 420, 1)), areas: [{ cx, cy: 390, rx: 190, ry: 50, k: 0.9 }] };
  },
  legumes_assados(c, op) {
    const { cx, s } = c; const cores = ['#EE9A3C', '#7DA84E', '#D6402F', '#F2C94C', '#8E3D78'];
    const pedacos = [];
    for (let i = 0; i < 22; i++) {
      const a = s.entre(0, Math.PI * 2); const r = Math.sqrt(s.n());
      const x = cx + Math.cos(a) * 180 * r; const y = 386 + Math.sin(a) * 56 * r;
      pedacos.push(pa(`M${r1(x - 18)} ${r1(y - 8)} L${r1(x + 14)} ${r1(y - 14)} L${r1(x + 20)} ${r1(y + 8)} L${r1(x - 12)} ${r1(y + 14)}Z`, cores[i % cores.length], { key: i, stroke: '#7A4A22', strokeWidth: 2, strokeOpacity: 0.3 }));
    }
    return { desenho: h('g', null, Prato({ c, rx: 262, ry: 90 }), ...pedacos), areas: [{ cx, cy: 386, rx: 170, ry: 50, k: 0.9 }] };
  },
  arroz_graos(c, op) {
    const { cx, s } = c; const cor = op.massa === 'integral' ? ['#D9C29A', '#BFA374'] : op.massa === 'cenoura' ? ['#F1C890', '#DDA866'] : ['#FBF8F0', '#E8DFCB'];
    return {
      desenho: h('g', null, Prato({ c }),
        pa(`M${cx - 170} 400 Q${cx - 150} 300 ${cx} 290 Q${cx + 150} 300 ${cx + 170} 400 Q${cx} 430 ${cx - 170} 400Z`, c.grad('ar', cor[0], cor[1])),
        pontos(c, cx, 360, 140, 50, 60, cor[1], 3.5, s, 0.9)),
      areas: [{ cx, cy: 330, rx: 120, ry: 30, k: 0.85 }],
    };
  },
  pure(c, op) {
    const { cx } = c; const cor = op.massa === 'cenoura' ? ['#F3B062', '#E0903E'] : op.massa === 'banana' ? ['#F4DF9E', '#E2C676'] : ['#FAEFD2', '#EADBB2'];
    return {
      desenho: h('g', null, Prato({ c }),
        pa(`M${cx - 160} 400 Q${cx - 150} 320 ${cx} 314 Q${cx + 150} 320 ${cx + 160} 400 Q${cx} 428 ${cx - 160} 400Z`, c.grad('pu', cor[0], cor[1])),
        pa(`M${cx - 110} 380 Q${cx - 40} 340 ${cx + 30} 360 Q${cx + 90} 380 ${cx + 110} 360 M${cx - 70} 350 Q${cx} 320 ${cx + 60} 344`, 'none', { stroke: cor[1], strokeWidth: 6, strokeLinecap: 'round' })),
      areas: [{ cx, cy: 350, rx: 110, ry: 28, k: 0.85 }],
    };
  },
  travessa_gratinada(c, op) {
    const { cx, s } = c; const cob = corCobertura(op.cobertura) || COBERTURAS.queijo_gratinado;
    const x = cx - 230; const y = 300;
    return {
      desenho: h('g', null,
        Sombra({ c, y: 470, rx: 300, ry: 60 }),
        pa(`M${x} ${y + 20} Q${x} ${y} ${x + 30} ${y} L${x + 430} ${y} Q${x + 460} ${y} ${x + 460} ${y + 20} L${x + 450} ${y + 150} Q${x + 450} ${y + 170} ${x + 420} ${y + 170} L${x + 40} ${y + 170} Q${x + 10} ${y + 170} ${x + 10} ${y + 150}Z`, c.grad('tv', '#E8D7C2', '#C9A98A')),
        pa(`M${x + 24} ${y + 24} L${x + 436} ${y + 24} L${x + 430} ${y + 118} L${x + 30} ${y + 118}Z`, c.grad('gr', cob[0], cob[1])),
        pontos(c, cx, y + 70, 190, 40, 30, '#A8661E', 10, s, 0.45),
        Brilho({ d: `M${x + 40} ${y + 140} L${x + 420} ${y + 140}`, opacidade: 0.3 }),
      ),
      areas: [{ cx, cy: y + 70, rx: 180, ry: 36 }],
    };
  },
  tigela(c, op) {
    const { cx } = c; const cor = corConteudo(op);
    return {
      desenho: h('g', null, Prato({ c, rx: 230, ry: 78, y: 430 }), Tigela({ c, rx: 180, y: 330, altura: 110, conteudo: cor[0], conteudo2: cor[1] }),
        pa(`M${cx - 70} 330 q40 -14 90 0`, 'none', { stroke: '#fff', strokeWidth: 5, opacity: 0.35 })),
      areas: [{ cx, cy: 334, rx: 130, ry: 36 }],
    };
  },
  vitamina_copo(c, op) {
    const { cx } = c; const cor = corConteudo(op);
    return {
      desenho: h('g', null,
        Sombra({ c, y: 480, rx: 150, ry: 30 }),
        pa(`M${cx + 30} 210 L${cx + 70} 120`, 'none', { stroke: '#7B1E2C', strokeWidth: 12, strokeLinecap: 'round' }),
        tronco(c, 'cp', cx, 220, 100, 80, 26, 250, ['#F3EFE8', '#ECE6DC', '#D9D1C4'], false),
        tronco(c, 'lq', cx, 246, 94, 78, 24, 218, [cor[0], cor[0], cor[1]]),
        el(cx, 246, 94, 24, '#FFFDF6', { opacity: 0.8 }),
        el(cx, 220, 100, 26, 'none', { stroke: '#D9D1C4', strokeWidth: 3 }),
        Brilho({ d: `M${cx - 70} 270 L${cx - 60} 440`, opacidade: 0.5 }),
      ),
      areas: [{ cx: cx + 150, cy: 450, rx: 50, ry: 18, k: 0.9 }, { cx, cy: 246, rx: 60, ry: 14, k: 0.6 }],
    };
  },
  xicara_bebida(c, op) {
    const { cx } = c; const cor = op.massa === 'chocolate' ? ['#6B3B26', '#4A2617'] : op.massa === 'clara' ? ['#E9C98F', '#C99A58'] : op.massa === 'queijo' ? ['#F2C24A', '#D99A22'] : ['#8A5A3A', '#5E3A24'];
    const [cl, es] = c.louca;
    return {
      desenho: h('g', null,
        Sombra({ c, y: 450, rx: 200, ry: 44 }),
        el(cx, 430, 190, 56, es), el(cx, 424, 190, 56, cl),
        h('path', { d: `M${cx + 110} 320 C${cx + 180} 320 ${cx + 180} 400 ${cx + 104} 400`, fill: 'none', stroke: es, strokeWidth: 20 }),
        pa(`M${cx - 120} 290 Q${cx - 116} 420 ${cx} 424 Q${cx + 116} 420 ${cx + 120} 290Z`, c.grad('xc', cl, es)),
        el(cx, 290, 120, 36, es), el(cx, 294, 108, 30, c.grad('bb', cor[0], cor[1])),
        pa(`M${cx - 30} 250 q-16 -24 0 -48 q16 -24 0 -48 M${cx + 30} 246 q-16 -24 0 -48 q16 -24 0 -48`, 'none', { stroke: '#E9DCC8', strokeWidth: 6, strokeLinecap: 'round' }),
      ),
      areas: [{ cx, cy: 294, rx: 70, ry: 16, k: 0.7 }],
    };
  },
  picole(c, op) {
    const { cx } = c; const cor = corConteudo(op);
    const um = (x, y, r, i) => h('g', { key: i, transform: `rotate(${r} ${x} ${y})` },
      h('rect', { x: x - 10, y: y + 70, width: 20, height: 90, rx: 8, fill: '#E3C38E' }),
      h('rect', { x: x - 48, y: y - 80, width: 96, height: 160, rx: 44, fill: c.grad('pc', cor[0], cor[1], true) }),
      pa(`M${x - 28} ${y - 50} L${x - 28} ${y + 30}`, 'none', { stroke: '#fff', strokeWidth: 8, strokeLinecap: 'round', opacity: 0.35 }));
    return { desenho: h('g', null, Prato({ c, rx: 260, ry: 90 }), um(cx - 110, 340, -60, 0), um(cx + 10, 330, -70, 1), um(cx + 120, 360, -80, 2)), areas: [{ cx: cx - 20, cy: 300, rx: 130, ry: 20, k: 0.7 }] };
  },
  geleia_pote(c, op) {
    const { cx } = c; const cor = corConteudo(op);
    return {
      desenho: h('g', null,
        Sombra({ c, y: 470, rx: 230, ry: 44 }),
        cilindro(c, 'pt', cx - 40, 250, 96, 28, 200, ['#F3EFE8', '#ECE6DC', '#D9D1C4']),
        cilindro(c, 'gl', cx - 40, 280, 88, 24, 162, [cor[0], cor[0], cor[1]]),
        pa(`M${cx - 150} 250 Q${cx - 40} 200 ${cx + 70} 250 L${cx + 60} 270 Q${cx - 40} 240 ${cx - 140} 270Z`, '#C9534F'),
        h('rect', { x: cx - 136, y: 222, width: 192, height: 30, rx: 8, fill: '#B8A48A' }),
        Brilho({ d: `M${cx - 110} 300 L${cx - 110} 420`, opacidade: 0.5 }),
        el(cx + 150, 440, 80, 26, c.louca[0], { stroke: c.louca[1], strokeWidth: 3 }),
      ),
      areas: [{ cx: cx + 150, cy: 436, rx: 50, ry: 14, k: 0.8 }],
    };
  },
  ceia_peru(c, op) {
    const { cx, s } = c;
    return {
      desenho: h('g', null, Prato({ c, rx: 280, ry: 96, y: 410 }),
        pa(`M${cx - 150} 380 C${cx - 160} 270 ${cx + 150} 250 ${cx + 170} 360 C${cx + 176} 420 ${cx - 140} 440 ${cx - 150} 380Z`, c.grad('pr', '#E0A055', '#9E5A24', true)),
        pa(`M${cx + 150} 330 C${cx + 210} 320 ${cx + 240} 350 ${cx + 220} 380 C${cx + 200} 400 ${cx + 160} 380 ${cx + 150} 360Z`, '#B66E30'),
        pa(`M${cx - 140} 340 C${cx - 210} 330 ${cx - 230} 360 ${cx - 210} 386 C${cx - 190} 404 ${cx - 150} 386 ${cx - 140} 366Z`, '#B66E30'),
        pontos(c, cx, 340, 110, 40, 18, '#7A3E16', 4, s, 0.35),
        Brilho({ d: `M${cx - 90} 300 Q${cx} 270 ${cx + 80} 286`, opacidade: 0.4 }),
      ),
      areas: [{ cx: cx - 200, cy: 450, rx: 50, ry: 20, k: 0.85 }, { cx: cx + 200, cy: 450, rx: 50, ry: 20, k: 0.85 }],
    };
  },
  salpicao(c, op) {
    const { cx, s } = c;
    return {
      desenho: h('g', null, Tigela({ c, rx: 200, y: 320, altura: 120, conteudo: '#F4E9CF', conteudo2: '#E5D3AE' }),
        pa(`M${cx - 150} 320 Q${cx - 120} 266 ${cx} 260 Q${cx + 120} 266 ${cx + 150} 320Z`, '#F1E4C6'),
        pontos(c, cx, 300, 120, 24, 30, '#D9B98A', 5, s, 0.7)),
      areas: [{ cx, cy: 296, rx: 120, ry: 24 }],
    };
  },
};

// Meia-lua dobrada (tapioca, crepioca, omelete) com recheio aparecendo.
function meiaLua(c, op, cores, nome, manchas = false) {
  const { cx, s } = c; const recheio = corConteudo(op);
  const um = (x, y, i, r) => h('g', { key: i, transform: `rotate(${r} ${x} ${y})` },
    el(x, y + 12, 150, 40, cores[2], { opacity: 0.6 }),
    pa(`M${x - 150} ${y} A150 52 0 0 0 ${x + 150} ${y} L${x + 140} ${y - 6} Q${x} ${y - 30} ${x - 140} ${y - 6}Z`, recheio[0]),
    pa(`M${x - 150} ${y} A150 60 0 0 1 ${x + 150} ${y} Q${x} ${y + 26} ${x - 150} ${y}Z`, c.grad(`${nome}`, cores[0], cores[1])),
    manchas ? pontos(c, x, y - 20, 110, 24, 14, '#C9862C', 6, s, 0.35) : pontos(c, x, y - 20, 110, 24, 18, cores[2], 2.5, s, 0.4),
  );
  return {
    desenho: h('g', null, Prato({ c }), um(cx - 10, 400, 0, -4), op.recheio || nome === 'tp' ? um(cx + 30, 350, 1, 6) : null),
    areas: [{ cx: cx + 10, cy: 330, rx: 100, ry: 18, k: 0.75 }],
  };
}
