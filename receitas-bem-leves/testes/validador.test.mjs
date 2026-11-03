// Testes do validador: cada teste quebra uma regra numa cópia de receita válida
// e confere que o validador recusa.
// Uso: npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { carregarIngredientes, carregarProibidos, carregarReceitas } from '../scripts/lib/fontes.mjs';
import { validarColecao, validarReceita, procurarTermos } from '../scripts/lib/validacao.mjs';
import { normalizar } from '../scripts/lib/texto.mjs';

const contexto = { ingredientes: carregarIngredientes(), regras: carregarProibidos() };
const todas = carregarReceitas();
const base = () => structuredClone(todas.find((x) => x.receita.id === 'rbl-0001').receita);
const errosDe = (r) => validarReceita(r, contexto).erros;
const temErro = (r, trecho) => {
  const erros = errosDe(r);
  assert.ok(erros.some((e) => e.includes(trecho)), `esperava erro com "${trecho}", veio: ${JSON.stringify(erros)}`);
};

test('as receitas do piloto passam no validador', () => {
  const reprovadas = validarColecao(todas, contexto).filter((r) => r.erros.length);
  assert.deepEqual(reprovadas.map((r) => [r.receita.id, r.erros]), []);
});

test('busca sem acento: "pao" encontra "pão"', () => {
  assert.equal(normalizar('Pão de Queijo'), 'pao de queijo');
  assert.ok(normalizar('Pão de frigideira').includes(normalizar('pao')));
});

test('recusa ingrediente proibido do cadastro', () => {
  const r = base();
  r.ingredientes.push({ ingrediente: 'acucar', quantidade: 1, medida: 'g', texto: '1 g de açúcar' });
  temErro(r, 'ingrediente proibido');
});

test('recusa ingrediente que não está no cadastro', () => {
  const r = base();
  r.ingredientes.push({ ingrediente: 'xarope-de-agave', quantidade: 1, medida: 'g', texto: 'xarope' });
  temErro(r, 'fora do cadastro');
});

for (const frase of ['Polvilhe açúcar por cima.', 'Regue com mel antes de servir.', 'Sirva com leite condensado.', 'Use acucar mascavo se quiser.', 'Junte 1 colher de melado e misture.']) {
  test(`recusa termo proibido no texto: "${frase}"`, () => {
    const r = base();
    r.preparo.push({ texto: frase });
    temErro(r, 'termo proibido');
  });
}

test('aceita "sem açúcar" e "0 açúcar adicionado" no texto', () => {
  assert.deepEqual(procurarTermos('Coco ralado sem açúcar. Receita com 0 açúcar adicionado.', contexto.regras.termos_proibidos, contexto.regras.expressoes_permitidas_com_termo_proibido), []);
});

test('não confunde palavras parecidas ("caramelizar", "melhor", "meia cura")', () => {
  const r = base();
  r.preparo.push({ texto: 'Fica melhor quando a cebola começa a caramelizar.' });
  r.dicas.push({ tipo: 'dica', texto: 'Combina com queijo minas meia cura.' });
  assert.deepEqual(errosDe(r), []);
});

for (const frase of ['Ajuda a controlar a glicemia.', 'Ótima para quem quer emagrecer.', 'Receita que cura a vontade de doce.']) {
  test(`recusa promessa de saúde: "${frase}"`, () => {
    const r = base();
    r.descricao = frase;
    temErro(r, 'promessa de saúde');
  });
}

test('recusa nutrição faltando', () => {
  const r = base();
  r.nutricao = null;
  temErro(r, 'nutrição faltando');
});

test('recusa nutrição digitada à mão que não bate com o cálculo', () => {
  const r = base();
  r.nutricao.por_porcao.carboidratos_g = 2;
  temErro(r, 'nutrição desatualizada');
});

test('recusa etiqueta low carb em receita com mais de 15 g de carboidrato', () => {
  const r = structuredClone(todas.find((x) => x.receita.id === 'rbl-0003').receita);
  r.etiquetas.low_carb = true;
  temErro(r, 'etiqueta low carb errada');
});

test('recusa receita low carb sem a etiqueta', () => {
  const r = base();
  r.etiquetas.low_carb = false;
  temErro(r, 'etiqueta low carb errada');
});

test('recusa modo de preparo vazio', () => {
  const r = base();
  r.preparo = [];
  temErro(r, 'modo de preparo vazio');
});

test('recusa passo vazio', () => {
  const r = base();
  r.preparo.push({ texto: '   ' });
  temErro(r, 'vazio ou curto demais');
});

test('recusa ingrediente difícil sem alternativa', () => {
  const ingredientes = structuredClone(contexto.ingredientes);
  ingredientes['aveia-em-flocos'].facil_de_achar = false;
  const erros = validarReceita(base(), { ...contexto, ingredientes }).erros;
  assert.ok(erros.some((e) => e.includes('difícil de achar')));
});

test('recusa ilustração com ingrediente que a receita não tem', () => {
  const r = base();
  r.ilustracao.enfeites.push('morango');
  temErro(r, 'não tem ingrediente com esse enfeite');
});

test('recusa receita sem dica de substituição', () => {
  const r = base();
  r.dicas = r.dicas.filter((d) => d.tipo !== 'substituicao');
  temErro(r, 'dica de substituição');
});

test('recusa receita com forno no preparo mas sem temperatura', () => {
  const r = structuredClone(todas.find((x) => x.receita.id === 'rbl-0003').receita);
  r.forno = null;
  temErro(r, 'usa forno');
});

test('recusa receita duplicada com o mesmo nome', () => {
  const copia = structuredClone(todas[0]);
  copia.receita.id = 'rbl-9999';
  const res = validarColecao([...todas, copia], contexto).find((r) => r.receita.id === 'rbl-9999');
  assert.ok(res.erros.some((e) => e.includes('nome repetido')));
});

test('recusa receita repetida com nome diferente', () => {
  const copia = structuredClone(todas[0]);
  copia.receita.id = 'rbl-9998';
  copia.receita.nome = 'Pãozinho rápido de aveia';
  copia.receita.slug = 'paozinho-rapido-de-aveia';
  const res = validarColecao([...todas, copia], contexto).find((r) => r.receita.id === 'rbl-9998');
  assert.ok(res.erros.some((e) => e.includes('parece a mesma receita')), JSON.stringify(res.erros));
});
