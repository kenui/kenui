// Gera supabase/painel-hotmart-webhook.ts: a função do webhook num arquivo só, para colar no painel do Supabase.
// Uso: node scripts/gerar-painel-webhook.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { RAIZ } from './lib/fontes.mjs';

const pasta = join(RAIZ, 'supabase', 'functions', 'hotmart-webhook');
const regras = readFileSync(join(pasta, 'regras.ts'), 'utf8').replace(/^export (const|function|type) /gm, '$1 ');
const servidor = readFileSync(join(pasta, 'index.ts'), 'utf8').replace(/^import \{[^}]*\} from '\.\/regras\.ts';\n/m, '');
const cabecalho = '// ARQUIVO ÚNICO para colar no painel do Supabase (Edge Functions > função > Code).\n// Gerado por scripts/gerar-painel-webhook.mjs a partir de index.ts + regras.ts. Não edite aqui.\n';
const final = cabecalho + servidor.replace("import { createClient }", `// ---- regras ----\n${regras}\n// ---- servidor ----\nimport { createClient }`);
writeFileSync(join(RAIZ, 'supabase', 'painel-hotmart-webhook.ts'), final);
console.log('supabase/painel-hotmart-webhook.ts gerado');
