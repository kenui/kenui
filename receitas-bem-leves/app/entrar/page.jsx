'use client';
// Login só com e-mail: o app manda um e-mail com um botão de entrar e um código numérico (6 a 8 dígitos, conforme a configuração do Supabase).
// O código existe porque, no iPhone, o app instalado na tela inicial não recebe o login feito pelo link.
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import { Rodape, SUPORTE } from '../../componentes/Moldura';
import { useApp } from '../../componentes/Provedor';
import { MODO_DEMO, entrarComCodigo, pedirAcesso } from '../../lib/supabase';

function Entrar() {
  const { status, recarregar } = useApp();
  const router = useRouter();
  const params = useSearchParams();
  const depois = params.get('depois') || '/';
  const [email, setEmail] = useState(params.get('email') ?? '');
  const [etapa, setEtapa] = useState('email');
  const [codigo, setCodigo] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => { if (status === 'pronto' || MODO_DEMO) router.replace(depois); }, [status, router, depois]);

  async function enviar(e) {
    e.preventDefault();
    setErro('');
    const limpo = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(limpo)) { setErro('Confira o e-mail: parece que falta alguma parte (por exemplo, @gmail.com).'); return; }
    setEnviando(true);
    const r = await pedirAcesso(limpo);
    setEnviando(false);
    if (r.ok) { setEmail(limpo); setEtapa('codigo'); return; }
    if (r.motivo === 'sem_compra') setErro('Não encontramos uma compra com este e-mail. Use o mesmo e-mail da sua compra na Hotmart.');
    else if (r.motivo === 'bloqueado') setErro('O acesso deste e-mail não está ativo (compra reembolsada ou cancelada). Fale com o suporte se for engano.');
    else if (r.motivo === 'muitas_tentativas') setErro('Você pediu muitos e-mails seguidos. Espere 1 minuto e tente de novo.');
    else setErro('Não foi possível enviar agora. Confira sua internet e tente de novo.');
  }

  async function confirmar(e) {
    e.preventDefault();
    setErro('');
    setEnviando(true);
    const ok = await entrarComCodigo(email, codigo);
    setEnviando(false);
    if (!ok) { setErro('Código errado ou vencido. Confira os números ou peça um novo e-mail.'); return; }
    await recarregar();
    router.replace(depois);
  }

  return (
    <div className="entrar">
      <main className="conteudo">
        <div className="marca">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/icones/icone-192.png" alt="" width="88" height="88" />
          <h1>Receitas Bem Leves</h1>
        </div>
        {etapa === 'email' ? (
          <form className="cartao-aviso" onSubmit={enviar}>
            <h2>Entrar</h2>
            <p><b>Use o mesmo e-mail da sua compra na Hotmart.</b></p>
            <div className="campo">
              <label htmlFor="email">Seu e-mail</label>
              <input id="email" type="email" inputMode="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seuemail@exemplo.com" required />
            </div>
            {erro && <p className="erro" role="alert">{erro}</p>}
            <button className="btn btn-principal btn-largo btn-grande" disabled={enviando}>{enviando ? 'Enviando…' : 'Receber acesso por e-mail'}</button>
            <p className="dica-campo">Não precisa de senha. Vamos mandar um e-mail com um botão para entrar e um código.</p>
          </form>
        ) : (
          <form className="cartao-aviso" onSubmit={confirmar}>
            <h2>Confira seu e-mail</h2>
            <p>Mandamos um e-mail para <b className="selecionavel">{email}</b>. Abra e toque em <b>“Entrar no app”</b>.</p>
            <p>Ou digite aqui o código que veio no e-mail:</p>
            <div className="campo">
              <label htmlFor="codigo">Código</label>
              <input id="codigo" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]*" maxLength={8} value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ''))} style={{ fontSize: 28, letterSpacing: '.2em' }} />
            </div>
            {erro && <p className="erro" role="alert">{erro}</p>}
            <button className="btn btn-principal btn-largo btn-grande" disabled={enviando || codigo.length < 6}>{enviando ? 'Entrando…' : 'Entrar'}</button>
            <p className="dica-campo">Não chegou? Olhe a caixa de spam e a aba Promoções. O e-mail pode levar alguns minutos.</p>
            <button type="button" className="btn btn-secundario" onClick={() => { setEtapa('email'); setCodigo(''); setErro(''); }}>Usar outro e-mail ou mandar de novo</button>
          </form>
        )}
        <Link className="btn btn-secundario btn-largo" href="/nao-recebi/">Não recebi meu acesso</Link>
        <p className="nota" style={{ textAlign: 'center' }}>Suporte: <b className="selecionavel">{SUPORTE}</b></p>
        <Rodape />
      </main>
    </div>
  );
}

export default function Pagina() {
  return <Suspense><Entrar /></Suspense>;
}
