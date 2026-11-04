// Envia o conteúdo dos produtos extras (conteudo/extras/*.json) para a tabela conteudo_extras do Supabase.
// Cada linha só é lida por quem comprou aquele produto (regra do banco, migração 0002).
// Uso: SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... node scripts/publicar-extras.mjs
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createClient } from '@supabase/supabase-js';
import { PASTA_CONTEUDO } from './lib/fontes.mjs';

const url = process.env.SUPABASE_URL;
const chave = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!url || !chave) { console.error('Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.'); process.exit(1); }
const s = createClient(url, chave, { auth: { persistSession: false } });
const pasta = join(PASTA_CONTEUDO, 'extras');
for (const f of readdirSync(pasta).filter((n) => n.endsWith('.json')).sort()) {
  const conteudo = JSON.parse(readFileSync(join(pasta, f), 'utf8'));
  const versao = createHash('sha256').update(JSON.stringify(conteudo)).digest('hex').slice(0, 12);
  const { error } = await s.from('conteudo_extras').upsert({ produto: conteudo.produto, versao, conteudo, publicado_em: new Date().toISOString() });
  if (error) { console.error(`${conteudo.produto}: ${error.message}`); process.exit(1); }
  console.log(`${conteudo.produto}: publicado (versão ${versao})`);
}
