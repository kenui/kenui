// Cliente do Supabase (login por e-mail, pacote de receitas e dados da pessoa).
// Em modo demonstração (NEXT_PUBLIC_MODO_DEMO=1) não há Supabase: o app lê /pacote-demo.json.
import { createClient } from '@supabase/supabase-js';

export const MODO_DEMO = process.env.NEXT_PUBLIC_MODO_DEMO === '1';
const URL_SUPABASE = process.env.NEXT_PUBLIC_SUPABASE_URL;
const CHAVE_PUBLICA = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let cliente = null;
export function supabase() {
  if (MODO_DEMO) return null;
  if (!cliente) {
    if (!URL_SUPABASE || !CHAVE_PUBLICA) throw new Error('Configure NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_ANON_KEY.');
    cliente = createClient(URL_SUPABASE, CHAVE_PUBLICA, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, storageKey: 'rbl-sessao' },
    });
  }
  return cliente;
}

// Envia o e-mail com o link e o código. Só funciona para e-mails que já compraram
// (o usuário é criado pelo webhook da Hotmart; aqui shouldCreateUser = false).
export async function pedirAcesso(email) {
  const { error } = await supabase().auth.signInWithOtp({
    email,
    options: { shouldCreateUser: false, emailRedirectTo: `${window.location.origin}/entrar/confirmar/` },
  });
  if (!error) return { ok: true };
  const msg = String(error.message || '').toLowerCase();
  if (msg.includes('banned')) return { ok: false, motivo: 'bloqueado' };
  if (msg.includes('signups not allowed') || msg.includes('not found') || error.status === 422) {
    return { ok: false, motivo: 'sem_compra' };
  }
  if (error.status === 429 || msg.includes('rate')) return { ok: false, motivo: 'muitas_tentativas' };
  return { ok: false, motivo: 'erro' };
}

// Devolve '' quando entrou, ou a mensagem do Supabase (mostrada pequena na tela para diagnóstico).
export async function entrarComCodigo(email, codigo) {
  const token = codigo.replace(/\D/g, '');
  let { error } = await supabase().auth.verifyOtp({ email, token, type: 'email' });
  if (error) ({ error } = await supabase().auth.verifyOtp({ email, token, type: 'magiclink' }));
  return error ? String(error.message || error.code || 'erro') : '';
}

export async function entrarComLink(tokenHash) {
  const { error } = await supabase().auth.verifyOtp({ token_hash: tokenHash, type: 'email' });
  return !error;
}
