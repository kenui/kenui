// Envia o pacote de receitas para o Supabase (tabela pacote_receitas, protegida por login).
// Precisa das variáveis SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY (chave secreta: nunca no app).
// Uso: node scripts/gerar-pacote.mjs && node scripts/publicar-pacote.mjs
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createClient } from '@supabase/supabase-js';
import { RAIZ } from './lib/fontes.mjs';

const url = process.env.SUPABASE_URL;
const chave = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!url || !chave) {
  console.error('Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.');
  process.exit(1);
}
const { versao, conteudo } = JSON.parse(readFileSync(join(RAIZ, '.pacote', 'pacote.json'), 'utf8'));
const s = createClient(url, chave, { auth: { persistSession: false } });
const { data: existente } = await s.from('pacote_receitas').select('versao').eq('versao', versao).maybeSingle();
if (existente) {
  console.log(`Versão ${versao} já está publicada. Nada a fazer.`);
} else {
  const { error } = await s.from('pacote_receitas').insert({ versao, conteudo });
  if (error) { console.error('Falha ao publicar:', error.message); process.exit(1); }
  // Mantém só as 3 versões mais recentes.
  const { data: todas } = await s.from('pacote_receitas').select('versao').order('publicado_em', { ascending: false });
  const antigas = (todas ?? []).slice(3).map((x) => x.versao);
  if (antigas.length) await s.from('pacote_receitas').delete().in('versao', antigas);
  console.log(`Pacote ${versao} publicado (${conteudo.receitas.length} receitas).`);
}
