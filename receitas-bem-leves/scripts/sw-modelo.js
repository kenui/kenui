// Service worker do Receitas Bem Leves (gerado por scripts/gerar-service-worker.mjs).
// - Na instalação, guarda todas as telas, scripts, estilos, fontes e ícones.
// - Telas: tenta a internet primeiro (para pegar a versão nova) e, sem internet, usa a guardada.
// - Arquivos com nome versionado (_next/static) e fotos: usa o guardado e só baixa se não tiver.
// - Pedidos ao Supabase (login, receitas) nunca passam pelo cache daqui.
const VERSAO = '__VERSAO__';
const CACHE = `rbl-${VERSAO}`;
const CACHE_FOTOS = 'rbl-fotos';
const ARQUIVOS = __ARQUIVOS__;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARQUIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((nomes) => Promise.all(nomes.filter((n) => n.startsWith('rbl-') && n !== CACHE && n !== CACHE_FOTOS).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((r) => { const copia = r.clone(); caches.open(CACHE).then((c) => c.put(req, copia)); return r; })
        .catch(async () => (await caches.match(req, { ignoreSearch: true })) || (await caches.match('/'))),
    );
    return;
  }

  if (url.pathname.startsWith('/fotos/')) {
    e.respondWith(caches.open(CACHE_FOTOS).then(async (c) => (await c.match(req)) || fetch(req).then((r) => { if (r.ok) c.put(req, r.clone()); return r; })));
    return;
  }

  // Dados das telas (.txt, pedidos com ?_rsc=) e arquivos versionados: o parâmetro de busca não muda o arquivo.
  const semBusca = url.pathname.startsWith('/_next/static/') || url.pathname.endsWith('.txt');
  e.respondWith(caches.match(req, { ignoreSearch: semBusca }).then((achado) => achado || fetch(req)));
});
