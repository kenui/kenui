// Acompanhamentos (arroz, purê, farofa, vinagrete, refogados) não entram sozinhos como almoço
// ou jantar no plano. Regra: nome começa com um tipo de acompanhamento ou a porção tem menos de 150 kcal.
import { normalizar } from './texto.mjs';

const INICIOS = ['arroz', 'pure', 'farofa', 'vinagrete', 'couve refogada', 'repolho refogado', 'feijao caseiro', 'mandioca na manteiga', 'brocolis gratinado', 'legumes assados', 'salada de folhas', 'maionese', 'couve flor gratinada'];

export function ehAcompanhamento(r) {
  if (r.categoria !== 'almoco_jantar' && r.categoria !== 'ceia') return false;
  const n = normalizar(r.nome);
  return INICIOS.some((i) => n.startsWith(i)) || (r.nutricao?.por_porcao?.kcal ?? 999) < 150;
}
