// Depois do "next build", grava out/sw.js com a lista de todos os arquivos do app,
// para que ele funcione sem internet depois do primeiro acesso.
// O pacote de receitas não passa por aqui: fica no IndexedDB do aparelho, depois do login.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { RAIZ } from './lib/fontes.mjs';

const OUT = join(RAIZ, 'out');
const arquivos = [];
const andar = (pasta) => {
  for (const nome of readdirSync(pasta)) {
    const p = join(pasta, nome);
    if (statSync(p).isDirectory()) andar(p);
    else arquivos.push(p);
  }
};
andar(OUT);

const ignorar = (r) => r === 'sw.js' || r.startsWith('fotos/') || r === 'pacote-demo.json' || r === '.htaccess' || r === '404.html';
const urls = [];
const hash = createHash('sha256');
for (const p of arquivos.sort()) {
  const r = relative(OUT, p).split(sep).join('/');
  if (ignorar(r)) continue;
  hash.update(r).update(readFileSync(p));
  urls.push(r.endsWith('index.html') ? `/${r.slice(0, -'index.html'.length)}` : `/${r}`);
}
const versao = hash.digest('hex').slice(0, 10);
const modelo = readFileSync(join(RAIZ, 'scripts', 'sw-modelo.js'), 'utf8');
writeFileSync(join(OUT, 'sw.js'), modelo.replace('__VERSAO__', versao).replace('__ARQUIVOS__', JSON.stringify(urls)));
console.log(`out/sw.js: versão ${versao}, ${urls.length} arquivos guardados para uso offline.`);
