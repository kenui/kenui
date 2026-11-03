// Monta o cardápio de 4 semanas (café da manhã, lanche, almoço e jantar) com as receitas do app.
// Regras: usa refeicoes_do_plano de cada receita; não usa receitas de ceia, acompanhamentos nem bebidas muito leves; não repete receita
// na mesma semana dentro da mesma refeição nem no mesmo dia; espalha o uso para variar o máximo.
// O sorteio tem semente fixa: rodar de novo dá o mesmo plano enquanto as receitas não mudarem.
// Uso: node scripts/gerar-plano.mjs
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { carregarReceitas, PASTA_CONTEUDO } from './lib/fontes.mjs';
import { criarSorteio } from '../ilustracoes/base.mjs';
import { ehAcompanhamento } from './lib/acompanhamento.mjs';

const REFEICOES = ['cafe_da_manha', 'lanche', 'almoco', 'jantar'];
const receitas = carregarReceitas().map((x) => x.receita).filter((r) => r.categoria !== 'ceia');
const s = criarSorteio('plano-4-semanas');

const opcoes = {};
for (const ref of REFEICOES) {
  // Bebidas muito leves (água saborizada, chá) não contam como refeição sozinhas.
  const minimo = { cafe_da_manha: 100, lanche: 80, almoco: 150, jantar: 150 }[ref];
  opcoes[ref] = receitas.filter((r) => r.refeicoes_do_plano.includes(ref) && r.nutricao.por_porcao.kcal >= minimo && !(['almoco', 'jantar'].includes(ref) && ehAcompanhamento(r))).map((r) => r.id);
  // Embaralha (Fisher-Yates com semente).
  for (let i = opcoes[ref].length - 1; i > 0; i--) {
    const j = Math.floor(s.n() * (i + 1));
    [opcoes[ref][i], opcoes[ref][j]] = [opcoes[ref][j], opcoes[ref][i]];
  }
  if (opcoes[ref].length < 7) throw new Error(`Poucas receitas para ${ref}: ${opcoes[ref].length}`);
}

const usos = {};
const semanas = [];
for (let sem = 0; sem < 4; sem++) {
  const naSemana = { cafe_da_manha: new Set(), lanche: new Set(), almoco: new Set(), jantar: new Set() };
  const dias = [];
  for (let d = 0; d < 7; d++) {
    const dia = {};
    const noDia = new Set();
    for (const ref of REFEICOES) {
      // Escolhe a receita menos usada até agora que ainda não apareceu nesta semana nem neste dia.
      const candidatas = opcoes[ref].filter((id) => !naSemana[ref].has(id) && !noDia.has(id));
      candidatas.sort((a, b) => (usos[a] ?? 0) - (usos[b] ?? 0));
      const id = candidatas[0];
      dia[ref] = id;
      usos[id] = (usos[id] ?? 0) + 1;
      naSemana[ref].add(id);
      noDia.add(id);
    }
    dias.push(dia);
  }
  semanas.push(dias);
}

const destino = join(PASTA_CONTEUDO, 'plano.json');
writeFileSync(destino, JSON.stringify({ descricao: 'Cardápio de 4 semanas gerado por scripts/gerar-plano.mjs', semanas }, null, 2) + '\n');
const distintas = Object.keys(usos).length;
console.log(`Plano gravado em ${destino}: 112 refeições com ${distintas} receitas diferentes.`);
for (const ref of REFEICOES) console.log(`  ${ref}: ${opcoes[ref].length} opções`);
