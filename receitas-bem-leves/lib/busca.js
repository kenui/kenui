// Busca e filtros de receitas. A busca ignora acentos e maiúsculas ("pao" encontra "Pão").
import { normalizar } from './texto';

export function criarIndice(pacote) {
  const indice = {};
  for (const r of pacote.receitas) {
    indice[r.id] = normalizar([
      r.nome, r.descricao, ...(r.termos ?? []),
      ...r.ingredientes.map((i) => pacote.ingredientes[i.ingrediente]?.nome ?? ''),
    ].join(' '));
  }
  return indice;
}

export const FILTROS_VAZIOS = { busca: '', categoria: '', destaque: '', tempo: 0, lowCarb: false, emCasa: '' };

export function filtrarReceitas(pacote, indice, f) {
  const termos = normalizar(f.busca).split(/\s+/).filter(Boolean);
  return pacote.receitas.filter((r) =>
    termos.every((t) => indice[r.id].includes(t)) &&
    (!f.categoria || r.categoria === f.categoria) &&
    (!f.destaque || r.destaques.includes(f.destaque)) &&
    (!f.tempo || r.tempo.total_min <= f.tempo) &&
    (!f.lowCarb || r.low_carb) &&
    (!f.emCasa || r.ingredientes.some((i) => i.ingrediente === f.emCasa)));
}

// Ingredientes que fazem sentido no filtro "Tenho em casa" (sem sal, água e temperos de pitada).
export function ingredientesParaFiltro(pacote) {
  const contagem = {};
  for (const r of pacote.receitas) {
    for (const i of r.ingredientes) {
      if (i.opcional || ['sal', 'agua', 'pimenta-do-reino'].includes(i.ingrediente)) continue;
      contagem[i.ingrediente] = (contagem[i.ingrediente] ?? 0) + 1;
    }
  }
  return Object.keys(contagem)
    .filter((id) => contagem[id] >= 2)
    .sort((a, b) => pacote.ingredientes[a].nome.localeCompare(pacote.ingredientes[b].nome, 'pt-BR'));
}
