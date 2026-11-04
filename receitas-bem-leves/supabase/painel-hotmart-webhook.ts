// ARQUIVO ÚNICO para colar no painel do Supabase (Edge Functions > função > Code).
// Gerado por scripts/gerar-painel-webhook.mjs a partir de index.ts + regras.ts. Não edite aqui.
// Webhook da Hotmart (versão 2.0.0) para o Receitas Bem Leves.
// - Confere o token "hottok" enviado no cabeçalho X-HOTMART-HOTTOK.
// - Compra aprovada ou completa: libera o acesso (cria o usuário) e manda o e-mail de boas-vindas.
// - Reembolso, chargeback ou cancelamento: bloqueia o acesso.
// Variáveis (Supabase > Edge Functions > Secrets): HOTMART_HOTTOK, RESEND_API_KEY, REMETENTE,
// URL_APP e, opcional, HOTMART_PRODUTOS (qual produto da Hotmart libera o quê; ver regras.ts).
// SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY já existem nas funções do Supabase.
// ---- regras ----
// Regras do webhook separadas do servidor, para poder testar sem Supabase.

const LIBERAR = ['PURCHASE_APPROVED', 'PURCHASE_COMPLETE'];
const BLOQUEAR = ['PURCHASE_REFUNDED', 'PURCHASE_CHARGEBACK', 'PURCHASE_CANCELED'];

type Evento = { id: string; tipo: string; email: string; nome?: string; transacao?: string; produto?: string };

function decidir(tipo: string): 'liberar' | 'bloquear' | 'ignorar' {
  if (LIBERAR.includes(tipo)) return 'liberar';
  if (BLOQUEAR.includes(tipo)) return 'bloquear';
  return 'ignorar'; // ex.: PURCHASE_PROTEST (pedido de reembolso em análise) não bloqueia.
}

const PRODUTOS_INTERNOS = ['app', 'caderno', 'cardapio12', 'marmitas'];

// Converte o id do produto na Hotmart nos produtos internos que ele libera.
// mapaJson: '{"1234":["app"],"5678":["cardapio12","marmitas"]}'. Sem mapa (ou mapa inválido), tudo é "app",
// como era antes do funil. Com mapa, um id que não está nele não é deste app e é ignorado.
function produtosDoEvento(produtoId: string | undefined, mapaJson: string | undefined | null): string[] {
  let mapa: Record<string, unknown> | null = null;
  try { mapa = mapaJson ? JSON.parse(mapaJson) : null; } catch { mapa = null; }
  if (!mapa || typeof mapa !== 'object' || !Object.keys(mapa).length) return ['app'];
  const lista = mapa[String(produtoId ?? '')];
  if (!Array.isArray(lista)) return [];
  return lista.filter((p) => PRODUTOS_INTERNOS.includes(p));
}

// Formato 2.0.0: { id, event, version, data: { buyer: { email, name }, purchase: { transaction }, product: { id } } }
// deno-lint-ignore no-explicit-any
function lerEvento(corpo: any): Evento | null {
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

function emailBoasVindas({ nome, email, urlApp }: { nome?: string; email: string; urlApp: string }) {
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

// ---- servidor ----
import { createClient } from 'npm:@supabase/supabase-js@2.118.0';

const supabase = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
  auth: { persistSession: false },
});
const BANIDO = '876000h'; // 100 anos

const resposta = (status: number, texto: string) => new Response(JSON.stringify({ resultado: texto }), {
  status,
  headers: { 'content-type': 'application/json' },
});

async function acharOuCriarUsuario(email: string, nome?: string): Promise<string> {
  const { data: existente } = await supabase.rpc('usuario_por_email', { p_email: email });
  if (existente) return existente as string;
  const { data, error } = await supabase.auth.admin.createUser({ email, email_confirm: true, user_metadata: { nome } });
  if (error) {
    const { data: depois } = await supabase.rpc('usuario_por_email', { p_email: email });
    if (depois) return depois as string;
    throw error;
  }
  return data.user.id;
}

async function enviarBoasVindas(email: string, nome?: string) {
  const chave = Deno.env.get('RESEND_API_KEY');
  if (!chave) { console.warn('RESEND_API_KEY ausente: e-mail de boas-vindas não enviado'); return; }
  const { assunto, html, texto } = emailBoasVindas({ nome, email, urlApp: Deno.env.get('URL_APP') ?? 'https://app.dividaclara.com.br' });
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${chave}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from: Deno.env.get('REMETENTE') ?? 'Receitas Bem Leves <acesso@dividaclara.com.br>', to: [email], subject: assunto, html, text: texto, reply_to: 'suporte@dividaclara.com.br' }),
  });
  if (!r.ok) console.error('Falha no envio do e-mail de boas-vindas', r.status, await r.text());
}

// Guarda avisos recusados para diagnóstico, sem guardar o hottok recebido (só o tamanho e as 2 primeiras letras).
// deno-lint-ignore no-explicit-any
async function registrarRecusa(motivo: string, corpo: any, hottok: string) {
  const id = `recusado-${crypto.randomUUID()}`;
  const resumo = { motivo, evento: corpo?.event ?? null, versao: corpo?.version ?? null, hottok_recebido: hottok ? `${hottok.slice(0, 2)}… (${hottok.length} caracteres)` : 'nenhum' };
  await supabase.from('eventos_hotmart').insert({ id, tipo: `RECUSADO: ${motivo}`, email: corpo?.data?.buyer?.email ?? null, conteudo: resumo }).then(() => {}, () => {});
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return resposta(405, 'use POST');

  let corpo: unknown;
  try { corpo = await req.json(); } catch { corpo = null; }

  // A versão 2.0.0 manda o hottok no cabeçalho; versões antigas mandam no corpo.
  // deno-lint-ignore no-explicit-any
  const hottok = (req.headers.get('x-hotmart-hottok') ?? (corpo as any)?.hottok ?? '').trim();
  const esperado = (Deno.env.get('HOTMART_HOTTOK') ?? '').trim();
  if (!esperado || hottok !== esperado) {
    await registrarRecusa(!esperado ? 'segredo HOTMART_HOTTOK não configurado' : !hottok ? 'aviso sem hottok' : 'hottok diferente do segredo', corpo, hottok);
    return resposta(401, 'hottok inválido');
  }
  if (!corpo) { await registrarRecusa('corpo inválido', corpo, hottok); return resposta(400, 'corpo inválido'); }
  const ev = lerEvento(corpo);
  if (!ev) { await registrarRecusa('evento sem id, tipo ou e-mail', corpo, hottok); return resposta(400, 'evento sem id, tipo ou e-mail'); }

  // Quais produtos internos este aviso libera ou bloqueia (app, caderno, cardapio12, marmitas).
  // Segredo HOTMART_PRODUTOS: {"<id na Hotmart>": ["app"], "<id>": ["caderno"], ...}. Sem ele, tudo conta como "app".
  const produtos = produtosDoEvento(ev.produto, Deno.env.get('HOTMART_PRODUTOS'));
  if (!produtos.length) return resposta(200, 'produto que não é deste app: ignorado');

  // Idempotência: o mesmo aviso pode chegar mais de uma vez.
  const { error: erroEvento } = await supabase.from('eventos_hotmart').insert({ id: ev.id, tipo: ev.tipo, email: ev.email, transacao: ev.transacao, conteudo: corpo });
  if (erroEvento) {
    if (erroEvento.code === '23505') return resposta(200, 'aviso já processado');
    console.error(erroEvento);
    return resposta(500, 'erro ao registrar aviso');
  }

  const acao = decidir(ev.tipo);
  if (acao === 'ignorar') return resposta(200, `evento ${ev.tipo} registrado sem ação`);

  const { data: anterior } = await supabase.from('compradores').select('status').eq('email', ev.email).maybeSingle();
  const agora = new Date().toISOString();
  const status = acao === 'liberar' ? 'ativo' : 'bloqueado';
  try {
    const userId = await acharOuCriarUsuario(ev.email, ev.nome);
    // Registra cada produto deste aviso. A tabela pode não existir ainda (migração 0002 não rodada): não trava o app.
    const { error: erroProdutos } = await supabase.from('produtos_comprados').upsert(
      produtos.map((produto) => ({ email: ev.email, produto, status, transacao: ev.transacao, hotmart_produto_id: ev.produto, atualizado_em: agora })),
    );
    if (erroProdutos) console.error('produtos_comprados', erroProdutos.message);

    if (!produtos.includes('app')) return resposta(200, `extra ${status}: ${produtos.join(', ')}`);

    // O app principal: libera ou bloqueia o acesso inteiro.
    await supabase.from('compradores').upsert({ email: ev.email, user_id: userId, nome: ev.nome, status, transacao: ev.transacao, produto: ev.produto, ultimo_evento: ev.tipo, atualizado_em: agora });
    if (acao === 'liberar') {
      await supabase.auth.admin.updateUserById(userId, { ban_duration: 'none' });
      if (anterior?.status !== 'ativo') await enviarBoasVindas(ev.email, ev.nome);
      return resposta(200, 'acesso liberado');
    }
    await supabase.auth.admin.updateUserById(userId, { ban_duration: BANIDO });
    return resposta(200, 'acesso bloqueado');
  } catch (e) {
    console.error(e);
    // Apaga o registro do aviso para a Hotmart poder tentar de novo.
    await supabase.from('eventos_hotmart').delete().eq('id', ev.id);
    return resposta(500, 'erro ao processar');
  }
});
