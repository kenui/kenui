'use client';
import Link from 'next/link';
import { useState } from 'react';
import { Moldura, SUPORTE } from '../../componentes/Moldura';
import { useApp } from '../../componentes/Provedor';
import { useAviso } from '../../componentes/Toast';

function Perfil() {
  const { email, dados, sair } = useApp();
  const [confirmando, setConfirmando] = useState(false);
  const [toast, avisar] = useAviso();
  const copiar = async () => {
    try { await navigator.clipboard.writeText(SUPORTE); avisar('E-mail copiado'); } catch { avisar('Toque e segure o e-mail para copiar'); }
  };
  return (
    <>
      <section className="cartao-perfil">
        <p className="nota">Você entrou com o e-mail</p>
        <p><b className="selecionavel">{email}</b></p>
        {!confirmando
          ? <button className="btn btn-secundario" onClick={() => setConfirmando(true)}>Sair</button>
          : (
            <>
              <p>Quer mesmo sair? Para voltar, você vai precisar do link ou do código que chega por e-mail.</p>
              <button className="btn btn-principal" onClick={sair}>Sim, sair</button>
              <button className="btn btn-secundario" onClick={() => setConfirmando(false)}>Cancelar</button>
            </>
          )}
      </section>
      <Link className="btn btn-principal btn-largo btn-grande" href="/lista/">Minha lista de compras{dados.lista.receitas.length ? ` (${dados.lista.receitas.length})` : ''}</Link>
      <Link className="btn btn-secundario btn-largo" href="/bonus/">Meus bônus</Link>
      <section className="cartao-perfil">
        <h2 style={{ fontSize: 24, color: 'var(--vinho)' }}>Precisa de ajuda?</h2>
        <p>Escreva para o suporte:</p>
        <p><b className="selecionavel">{SUPORTE}</b></p>
        <button className="btn btn-secundario" onClick={copiar}>Copiar e-mail do suporte</button>
        <a className="btn btn-secundario" href={`mailto:${SUPORTE}?subject=Ajuda%20com%20o%20app%20Receitas%20Bem%20Leves`}>Abrir meu e-mail</a>
      </section>
      {toast}
    </>
  );
}

export default function Pagina() {
  return <Moldura titulo="Perfil" ativa="perfil"><Perfil /></Moldura>;
}
