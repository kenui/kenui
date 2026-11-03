// Junta receitas, ingredientes, plano e bônus num único pacote JSON que o app baixa depois do login.
// Uso:
//   node scripts/gerar-pacote.mjs            -> grava .pacote/pacote.json (para enviar ao Supabase)
//   node scripts/gerar-pacote.mjs --demo     -> grava public/pacote-demo.json (só para testes locais; nunca publicar)
import { createHash } from 'node:crypto';
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { carregarIngredientes, carregarProibidos, carregarReceitas, PASTA_CONTEUDO, RAIZ } from './lib/fontes.mjs';
import { ehAcompanhamento } from './lib/acompanhamento.mjs';

const demo = process.argv.includes('--demo');
const regras = carregarProibidos();
const cadastro = carregarIngredientes();
const receitas = carregarReceitas().map((x) => x.receita);

const usados = new Set(receitas.flatMap((r) => r.ingredientes.map((i) => i.ingrediente)));
const ingredientes = {};
for (const id of usados) {
  const c = cadastro[id];
  ingredientes[id] = { nome: c.nome, ...(c.nome_plural ? { nome_plural: c.nome_plural } : {}), secao: c.secao_mercado, ...(c.enfeite ? { enfeite: c.enfeite } : {}) };
}

const enxuta = (r) => ({
  id: r.id,
  slug: r.slug,
  nome: r.nome,
  descricao: r.descricao,
  categoria: r.categoria,
  destaques: r.destaques,
  refeicoes_do_plano: r.refeicoes_do_plano,
  tempo: r.tempo,
  rendimento: r.rendimento,
  porcoes: r.porcoes,
  porcao: r.porcao.descricao,
  ingredientes: r.ingredientes.map((i) => ({
    ...(i.grupo ? { grupo: i.grupo } : {}),
    ingrediente: i.ingrediente, quantidade: i.quantidade, medida: i.medida, texto: i.texto,
    ...(i.alternativa ? { alternativa: { texto: i.alternativa.texto, ...(i.alternativa.observacao ? { observacao: i.alternativa.observacao } : {}) } } : {}),
    ...(i.opcional ? { opcional: true } : {}),
  })),
  preparo: r.preparo,
  forno: r.forno,
  dicas: r.dicas,
  nutricao: r.nutricao.por_porcao,
  low_carb: r.etiquetas.low_carb,
  ...(ehAcompanhamento(r) ? { acompanhamento: true } : {}),
  ilustracao: { prato_base: r.ilustracao.prato_base, massa: r.ilustracao.massa, cobertura: r.ilustracao.cobertura, recheio: r.ilustracao.recheio, enfeites: r.ilustracao.enfeites },
  ...(r.foto ? { foto: r.foto } : {}),
  termos: r.busca?.termos_extras ?? [],
});

const pastaBonus = join(PASTA_CONTEUDO, 'bonus');
const bonus = readdirSync(pastaBonus).filter((f) => f.endsWith('.json')).sort().map((f) => JSON.parse(readFileSync(join(pastaBonus, f), 'utf8')));
const plano = JSON.parse(readFileSync(join(PASTA_CONTEUDO, 'plano.json'), 'utf8'));

const conteudo = {
  categorias: regras.categorias,
  secoes: regras.secoes_mercado,
  receitas: receitas.map(enxuta),
  ingredientes,
  plano: { semanas: plano.semanas },
  bonus,
};
const texto = JSON.stringify(conteudo);
const versao = createHash('sha256').update(texto).digest('hex').slice(0, 12);

if (demo) {
  writeFileSync(join(RAIZ, 'public', 'pacote-demo.json'), JSON.stringify({ ...conteudo, versao }));
  console.log(`public/pacote-demo.json (versão ${versao}, ${receitas.length} receitas, ${(texto.length / 1024).toFixed(0)} KB). NÃO publique este arquivo.`);
} else {
  mkdirSync(join(RAIZ, '.pacote'), { recursive: true });
  writeFileSync(join(RAIZ, '.pacote', 'pacote.json'), JSON.stringify({ versao, conteudo }));
  console.log(`.pacote/pacote.json (versão ${versao}, ${receitas.length} receitas, ${(texto.length / 1024).toFixed(0)} KB)`);
}
