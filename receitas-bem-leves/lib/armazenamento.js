// Guarda dados no aparelho. O pacote de receitas (grande) vai para o IndexedDB;
// preferências pequenas vão para o localStorage. Tudo protegido por try/catch:
// em janela anônima ou com armazenamento bloqueado o app continua funcionando.

const BANCO = 'receitas-bem-leves';
const LOJA = 'dados';

function abrir() {
  return new Promise((resolve, reject) => {
    const pedido = indexedDB.open(BANCO, 1);
    pedido.onupgradeneeded = () => pedido.result.createObjectStore(LOJA);
    pedido.onsuccess = () => resolve(pedido.result);
    pedido.onerror = () => reject(pedido.error);
  });
}

export async function lerGrande(chave) {
  try {
    const db = await abrir();
    return await new Promise((resolve) => {
      const t = db.transaction(LOJA, 'readonly').objectStore(LOJA).get(chave);
      t.onsuccess = () => resolve(t.result ?? null);
      t.onerror = () => resolve(null);
    });
  } catch { return null; }
}

export async function gravarGrande(chave, valor) {
  try {
    const db = await abrir();
    await new Promise((resolve) => {
      const t = db.transaction(LOJA, 'readwrite');
      t.objectStore(LOJA).put(valor, chave);
      t.oncomplete = resolve;
      t.onerror = resolve;
    });
  } catch { /* sem armazenamento: o app funciona só online */ }
}

export async function apagarTudo() {
  try { indexedDB.deleteDatabase(BANCO); } catch {}
  try {
    for (const k of Object.keys(localStorage)) if (k.startsWith('rbl:')) localStorage.removeItem(k);
  } catch {}
}

export function lerPequeno(chave, padrao) {
  try { const v = localStorage.getItem(`rbl:${chave}`); return v ? JSON.parse(v) : padrao; } catch { return padrao; }
}

export function gravarPequeno(chave, valor) {
  try { localStorage.setItem(`rbl:${chave}`, JSON.stringify(valor)); } catch {}
}
