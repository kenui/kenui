// Lista de compras: soma ingredientes iguais e agrupa por seção do mercado.
import { fracao } from './texto';

const MEDIDAS = {
  xicara: ['xícara (chá)', 'xícaras (chá)'],
  colher_sopa: ['colher (sopa)', 'colheres (sopa)'],
  colher_cha: ['colher (chá)', 'colheres (chá)'],
  pitada: ['pitada', 'pitadas'],
  dente: ['dente', 'dentes'],
};
const ORDEM = ['unidade', 'g', 'ml', 'xicara', 'colher_sopa', 'colher_cha', 'dente', 'pitada'];

function parte(medida, q, sozinha) {
  if (medida === 'g') return q >= 1000 ? `${fracao(Math.round(q / 100) / 10)} kg` : `${Math.round(q)} g`;
  if (medida === 'ml') return q >= 1000 ? `${fracao(Math.round(q / 100) / 10)} ${q >= 2000 ? 'litros' : 'litro'}` : `${Math.round(q)} ml`;
  if (medida === 'unidade') return sozinha ? fracao(q) : `${fracao(q)} ${q > 1 ? 'unidades' : 'unidade'}`;
  const [um, varios] = MEDIDAS[medida] ?? [medida, medida];
  return `${fracao(q)} ${q > 1 ? varios : um}`;
}

export function descreverItem(ingrediente, medidas) {
  const chaves = Object.keys(medidas).sort((a, b) => ORDEM.indexOf(a) - ORDEM.indexOf(b));
  const sozinha = chaves.length === 1;
  const partes = chaves.map((m) => parte(m, medidas[m], sozinha));
  if (sozinha && chaves[0] === 'unidade') {
    const q = medidas.unidade;
    return `${partes[0]} ${q > 1 && ingrediente.nome_plural ? ingrediente.nome_plural : ingrediente.nome}`;
  }
  return `${partes.join(' + ')} de ${ingrediente.nome}`;
}

// ids: receitas escolhidas (uma vez cada). Devolve [{ secao, itens: [{ id, texto }] }].
export function montarLista(pacote, ids) {
  const soma = {};
  for (const id of ids) {
    const r = pacote.porId[id];
    if (!r) continue;
    for (const i of r.ingredientes) {
      if (i.opcional || i.ingrediente === 'agua') continue;
      soma[i.ingrediente] ??= {};
      soma[i.ingrediente][i.medida] = (soma[i.ingrediente][i.medida] ?? 0) + i.quantidade;
    }
  }
  const grupos = {};
  for (const [id, medidas] of Object.entries(soma)) {
    const ing = pacote.ingredientes[id];
    if (!ing) continue;
    (grupos[ing.secao] ??= []).push({ id, texto: descreverItem(ing, medidas) });
  }
  return Object.keys(pacote.secoes)
    .filter((s) => grupos[s])
    .map((s) => ({ secao: pacote.secoes[s], itens: grupos[s].sort((a, b) => a.texto.localeCompare(b.texto, 'pt-BR')) }));
}
