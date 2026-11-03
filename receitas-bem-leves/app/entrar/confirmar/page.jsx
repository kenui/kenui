'use client';
// Página aberta pelo botão do e-mail. O login só acontece quando a pessoa toca em "Entrar":
// alguns provedores de e-mail abrem os links sozinhos e gastariam o link antes dela.
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';
import { Rodape } from '../../../componentes/Moldura';
import { useApp } from '../../../componentes/Provedor';
import { entrarComLink } from '../../../lib/supabase';

function Confirmar() {
  const token = useSearchParams().get('token_hash');
  const { recarregar } = useApp();
  const router = useRouter();
  const [estado, setEstado] = useState('pronto');

  async function entrar() {
    setEstado('entrando');
    const ok = token && await entrarComLink(token);
    if (!ok) { setEstado('erro'); return; }
    await recarregar();
    router.replace('/');
  }

  return (
    <div className="entrar">
      <main className="conteudo">
        <div className="marca">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/icones/icone-192.png" alt="" width="88" height="88" />
          <h1>Receitas Bem Leves</h1>
        </div>
        <section className="cartao-aviso">
          {estado !== 'erro' ? (
            <>
              <h2>Quase lá</h2>
              <p>Toque no botão para entrar no app.</p>
              <button className="btn btn-principal btn-largo btn-grande" onClick={entrar} disabled={estado === 'entrando'}>{estado === 'entrando' ? 'Entrando…' : 'Entrar no app'}</button>
            </>
          ) : (
            <>
              <h2>Este link venceu</h2>
              <p>O link do e-mail vale por 1 hora e só pode ser usado uma vez. Peça um novo: leva menos de um minuto.</p>
              <Link className="btn btn-principal btn-largo btn-grande" href="/entrar/">Pedir um novo e-mail</Link>
            </>
          )}
        </section>
        <Rodape />
      </main>
    </div>
  );
}

export default function Pagina() {
  return <Suspense><Confirmar /></Suspense>;
}
