// Regras do webhook separadas do servidor, para poder testar sem Supabase.

export const LIBERAR = ['PURCHASE_APPROVED', 'PURCHASE_COMPLETE'];
export const BLOQUEAR = ['PURCHASE_REFUNDED', 'PURCHASE_CHARGEBACK', 'PURCHASE_CANCELED'];

export type Evento = { id: string; tipo: string; email: string; nome?: string; transacao?: string; produto?: string };

export function decidir(tipo: string): 'liberar' | 'bloquear' | 'ignorar' {
  if (LIBERAR.includes(tipo)) return 'liberar';
  if (BLOQUEAR.includes(tipo)) return 'bloquear';
  return 'ignorar'; // ex.: PURCHASE_PROTEST (pedido de reembolso em análise) não bloqueia.
}

// Formato 2.0.0: { id, event, version, data: { buyer: { email, name }, purchase: { transaction }, product: { id } } }
// deno-lint-ignore no-explicit-any
export function lerEvento(corpo: any): Evento | null {
  const id = corpo?.id ? String(corpo.id) : '';
  const tipo = corpo?.event ? String(corpo.event) : '';
  const email = String(corpo?.data?.buyer?.email ?? '').trim().toLowerCase();
  if (!id || !tipo || !email.includes('@')) return null;
  return {
    id,
    tipo,
    email,
    nome: corpo?.data?.buyer?.name ?? undefined,
    transacao: corpo?.data?.purchase?.transaction ?? undefined,
    produto: corpo?.data?.product?.id !== undefined ? String(corpo.data.product.id) : undefined,
  };
}

const escapar = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));

export function emailBoasVindas({ nome, email, urlApp }: { nome?: string; email: string; urlApp: string }) {
  const primeiro = nome ? escapar(nome.split(' ')[0]) : '';
  const link = `${urlApp}/entrar/?email=${encodeURIComponent(email)}`;
  const assunto = 'Seu acesso ao Receitas Bem Leves chegou';
  const html = `<!doctype html><html lang="pt-BR"><body style="margin:0;background:#FBF3E8;font-family:Arial,sans-serif;color:#2A1A1A">
<div style="max-width:560px;margin:0 auto;padding:24px 16px">
<h1 style="font-family:Georgia,serif;font-weight:normal;color:#7B1E2C;font-size:30px;margin:0 0 16px">Receitas Bem Leves</h1>
<p style="font-size:19px;line-height:1.5">${primeiro ? `Olá, ${primeiro}!` : 'Olá!'} Sua compra foi aprovada e o seu acesso já está liberado.</p>
<p style="font-size:19px;line-height:1.5">Toque no botão abaixo e entre com este e-mail: <b>${escapar(email)}</b>. Não precisa de senha: o app manda um código para este e-mail.</p>
<p style="margin:28px 0"><a href="${link}" style="background:#137A3D;color:#fff;text-decoration:none;font-size:20px;font-weight:bold;padding:16px 28px;border-radius:12px;display:inline-block">Abrir o app</a></p>
<p style="font-size:17px;line-height:1.5"><b>Dica:</b> depois de entrar, coloque o app na tela inicial do celular. No Android, toque nos 3 pontinhos do navegador e em “Adicionar à tela inicial”. No iPhone, toque no botão de compartilhar e em “Adicionar à Tela de Início”.</p>
<p style="font-size:17px;line-height:1.5">Precisa de ajuda? Responda este e-mail ou escreva para suporte@dividaclara.com.br.</p>
<p style="font-size:14px;color:#5A4644;margin-top:28px">Receitas Bem Leves · Kenui Cabral · CNPJ 52.594.756/0001-00</p>
</div></body></html>`;
  const texto = `${primeiro ? `Olá, ${primeiro}!` : 'Olá!'} Sua compra foi aprovada e o seu acesso ao Receitas Bem Leves já está liberado.\n\nAbra o app: ${link}\nEntre com este e-mail: ${email}. Não precisa de senha: o app manda um código para este e-mail.\n\nAjuda: suporte@dividaclara.com.br\n\nReceitas Bem Leves · Kenui Cabral · CNPJ 52.594.756/0001-00`;
  return { assunto, html, texto };
}
