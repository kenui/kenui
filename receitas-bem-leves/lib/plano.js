// Plano de 4 semanas: o cardápio base vem do pacote (conteudo/plano.json) e as trocas da pessoa
// ficam guardadas por chave "semana-dia-refeicao".

export const REFEICOES = [
  ['cafe_da_manha', 'Café da manhã'],
  ['lanche', 'Lanche'],
  ['almoco', 'Almoço'],
  ['jantar', 'Jantar'],
];
export const DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];

export const chaveRefeicao = (semana, dia, refeicao) => `${semana}-${dia}-${refeicao}`;

export function receitaDoPlano(pacote, trocas, semana, dia, refeicao) {
  return trocas[chaveRefeicao(semana, dia, refeicao)] ?? pacote.plano.semanas[semana][dia][refeicao];
}

// Opções para trocar: receitas que servem para a mesma refeição e são da mesma categoria
// da receita atual; se houver poucas, completa com as da mesma refeição.
export function opcoesDeTroca(pacote, atualId, refeicao) {
  const atual = pacote.porId[atualId];
  const principal = refeicao === 'almoco' || refeicao === 'jantar';
  const daRefeicao = pacote.receitas.filter((r) => r.id !== atualId && r.categoria !== 'ceia' && r.refeicoes_do_plano.includes(refeicao) && !(principal && r.acompanhamento));
  const mesmaCategoria = daRefeicao.filter((r) => r.categoria === atual?.categoria);
  return mesmaCategoria.length >= 6 ? mesmaCategoria : [...mesmaCategoria, ...daRefeicao.filter((r) => r.categoria !== atual?.categoria)];
}

export function receitasDaSemana(pacote, trocas, semana) {
  const ids = new Set();
  for (let dia = 0; dia < 7; dia++) for (const [k] of REFEICOES) ids.add(receitaDoPlano(pacote, trocas, semana, dia, k));
  return [...ids];
}
