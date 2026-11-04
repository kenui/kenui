// Testes das regras do webhook da Hotmart (sem Supabase).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decidir, lerEvento, emailBoasVindas } from '../supabase/functions/hotmart-webhook/regras.ts';

// Exemplo no formato 2.0.0 enviado pela Hotmart.
const exemplo = (event) => ({
  id: 'b9d8b8f0-1a2b-4c3d-9e8f-000000000001',
  creation_date: 1730000000000,
  event,
  version: '2.0.0',
  data: {
    product: { id: 1234567, name: 'Receitas Bem Leves' },
    buyer: { email: ' Maria.Silva@Exemplo.com ', name: 'Maria da Silva' },
    purchase: { transaction: 'HP1234567890', status: 'APPROVED' },
  },
});

test('compra aprovada e completa liberam', () => {
  assert.equal(decidir('PURCHASE_APPROVED'), 'liberar');
  assert.equal(decidir('PURCHASE_COMPLETE'), 'liberar');
});

test('reembolso, chargeback e cancelamento bloqueiam', () => {
  for (const t of ['PURCHASE_REFUNDED', 'PURCHASE_CHARGEBACK', 'PURCHASE_CANCELED']) assert.equal(decidir(t), 'bloquear');
});

test('pedido de reembolso em análise não bloqueia', () => {
  assert.equal(decidir('PURCHASE_PROTEST'), 'ignorar');
  assert.equal(decidir('PURCHASE_DELAYED'), 'ignorar');
});

test('lê o evento 2.0.0 e normaliza o e-mail', () => {
  const ev = lerEvento(exemplo('PURCHASE_APPROVED'));
  assert.equal(ev.email, 'maria.silva@exemplo.com');
  assert.equal(ev.transacao, 'HP1234567890');
  assert.equal(ev.produto, '1234567');
  assert.equal(ev.nome, 'Maria da Silva');
});

test('recusa evento sem e-mail ou sem id', () => {
  const sem = exemplo('PURCHASE_APPROVED');
  delete sem.data.buyer.email;
  assert.equal(lerEvento(sem), null);
  assert.equal(lerEvento({ event: 'PURCHASE_APPROVED' }), null);
});

test('e-mail de boas-vindas tem o link de acesso e escapa o nome', () => {
  const m = emailBoasVindas({ nome: '<b>Ana</b> Souza', email: 'ana@x.com', urlApp: 'https://app.dividaclara.com.br' });
  assert.ok(m.html.includes('https://app.dividaclara.com.br/entrar/?email=ana%40x.com'));
  assert.ok(!m.html.includes('<b>Ana</b>'));
  assert.ok(m.texto.includes('suporte@dividaclara.com.br'));
});

import { produtosDoEvento } from '../supabase/functions/hotmart-webhook/regras.ts';

test('sem mapa de produtos, todo aviso libera o app (comportamento anterior)', () => {
  assert.deepEqual(produtosDoEvento('0', undefined), ['app']);
  assert.deepEqual(produtosDoEvento('123', 'isto não é json'), ['app']);
});

test('com mapa, cada produto da Hotmart libera só o que foi comprado', () => {
  const mapa = JSON.stringify({ 111: ['app'], 222: ['caderno'], 333: ['cardapio12', 'marmitas'], 444: ['cardapio12'] });
  assert.deepEqual(produtosDoEvento('111', mapa), ['app']);
  assert.deepEqual(produtosDoEvento('333', mapa), ['cardapio12', 'marmitas']);
  assert.deepEqual(produtosDoEvento('999', mapa), []);
  assert.deepEqual(produtosDoEvento('222', JSON.stringify({ 222: ['caderno', 'inventado'] })), ['caderno']);
});
