// Calcula calorias e carboidratos de uma receita, ingrediente por ingrediente.
// Regras:
// - Usa só os ingredientes principais: alternativas e itens marcados "opcional" ficam fora.
// - Gramas = quantidade × gramas da medida (cadastro de ingredientes).
// - Valores por 100 g vêm da fonte do ingrediente (TACO, USDA ou regra do app).
import { buscarNaFonte } from './fontes.mjs';
import { arredondar } from './texto.mjs';

export function gramasDoIngrediente(item, cadastro) {
  if (item.medida === 'g') return item.quantidade;
  const medida = cadastro.gramas_por_medida?.[item.medida];
  if (!medida) return null;
  return item.quantidade * medida.g;
}

export function valoresPor100g(cadastro) {
  const fonte = buscarNaFonte(cadastro.fonte_nutricao);
  if (!fonte) return { erro: `fonte "${cadastro.fonte_nutricao}" não encontrada` };
  const ajuste = cadastro.ajuste_nutricao ?? {};
  const kcal = fonte.kcal ?? ajuste.kcal ?? null;
  const carboidratos_g = fonte.carboidratos_g ?? ajuste.carboidratos_g ?? null;
  if (kcal === null || carboidratos_g === null) {
    return { erro: `a fonte ${fonte.rotulo} não tem valor de ${kcal === null ? 'calorias' : 'carboidrato'}` };
  }
  return { kcal, carboidratos_g, rotulo: fonte.rotulo, ajuste: cadastro.ajuste_nutricao?.motivo ?? null };
}

export function calcularNutricao(receita, ingredientes) {
  const erros = [];
  const linhas = [];
  const fora = [];
  for (const item of receita.ingredientes ?? []) {
    const cadastro = ingredientes[item.ingrediente];
    if (!cadastro) { erros.push(`ingrediente "${item.ingrediente}" não está no cadastro`); continue; }
    if (item.opcional) { fora.push({ ingrediente: item.ingrediente, texto: item.texto, motivo: 'opcional' }); continue; }
    const gramas = gramasDoIngrediente(item, cadastro);
    if (gramas === null || !Number.isFinite(gramas)) {
      erros.push(`"${item.texto}": a medida "${item.medida}" não tem peso no cadastro de ${cadastro.nome}`);
      continue;
    }
    const v = valoresPor100g(cadastro);
    if (v.erro) { erros.push(`"${item.texto}": ${v.erro}`); continue; }
    linhas.push({
      ingrediente: item.ingrediente,
      texto: item.texto,
      gramas: arredondar(gramas, 1),
      kcal: arredondar((gramas * v.kcal) / 100, 1),
      carboidratos_g: arredondar((gramas * v.carboidratos_g) / 100, 2),
      fonte: v.rotulo,
      por_100g: { kcal: v.kcal, carboidratos_g: v.carboidratos_g },
      ...(v.ajuste ? { observacao: v.ajuste } : {}),
    });
  }
  const totalKcal = linhas.reduce((s, l) => s + (l.gramas * l.por_100g.kcal) / 100, 0);
  const totalCarb = linhas.reduce((s, l) => s + (l.gramas * l.por_100g.carboidratos_g) / 100, 0);
  const porcoes = receita.porcoes;
  return {
    erros,
    calculo: {
      receita: receita.id,
      nome: receita.nome,
      porcoes,
      porcao: receita.porcao?.descricao ?? null,
      metodo: 'Soma ingrediente por ingrediente: gramas × valor por 100 g da fonte. Alternativas e itens opcionais não entram.',
      linhas,
      fora_do_calculo: fora,
      total: { kcal: arredondar(totalKcal, 1), carboidratos_g: arredondar(totalCarb, 1) },
      por_porcao: porcoes > 0
        ? { kcal: Math.round(totalKcal / porcoes), carboidratos_g: arredondar(totalCarb / porcoes, 1) }
        : null,
    },
  };
}
