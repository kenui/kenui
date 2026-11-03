'use client';
// Moldura das telas: cabeçalho, conteúdo, rodapé e barra de navegação inferior.
// Também controla o acesso: sem login vai para /entrar; acesso bloqueado mostra o aviso.
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useApp } from './Provedor';

const ICONES = {
  inicio: <path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />,
  receitas: <><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z" /><path d="M5 17a3 3 0 0 1 3-3h11" /></>,
  favoritos: <path d="M12 20s-7-4.4-9-9a4.8 4.8 0 0 1 9-3 4.8 4.8 0 0 1 9 3c-2 4.6-9 9-9 9z" />,
  plano: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  perfil: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
};
const ITENS = [
  ['inicio', 'Início', '/'],
  ['receitas', 'Receitas', '/receitas/'],
  ['favoritos', 'Favoritos', '/favoritos/'],
  ['plano', 'Plano', '/plano/'],
  ['perfil', 'Perfil', '/perfil/'],
];

export const SUPORTE = 'suporte@dividaclara.com.br';

export function Rodape() {
  return (
    <footer className="rodape">
      <p>Receitas Bem Leves · Kenui Cabral · CNPJ 52.594.756/0001-00</p>
      <p>As receitas e valores nutricionais são informativos e não substituem a orientação do seu médico ou nutricionista.</p>
    </footer>
  );
}

export function NavInferior({ ativa }) {
  return (
    <nav className="nav nao-imprimir" aria-label="Navegação principal">
      {ITENS.map(([id, nome, href]) => (
        <Link key={id} href={href} aria-current={ativa === id ? 'page' : undefined}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONES[id]}</svg>
          {nome}
        </Link>
      ))}
    </nav>
  );
}

function Carregando() {
  return <div className="carregando" role="status"><div className="girando" aria-hidden="true" />Abrindo suas receitas…</div>;
}

function Aviso({ titulo, children }) {
  return (
    <main className="conteudo">
      <section className="cartao-aviso">
        <h2>{titulo}</h2>
        {children}
      </section>
      <Rodape />
    </main>
  );
}

export function Moldura({ titulo, ativa, voltar, acoes, children, semRodape }) {
  const { status, recarregar } = useApp();
  const router = useRouter();
  const caminho = usePathname();

  useEffect(() => {
    if (status === 'sem_login') router.replace(`/entrar/?depois=${encodeURIComponent(caminho)}`);
  }, [status, router, caminho]);

  let corpo;
  if (status === 'carregando' || status === 'sem_login') corpo = <main className="conteudo"><Carregando /></main>;
  else if (status === 'bloqueado') {
    corpo = (
      <Aviso titulo="Seu acesso não está ativo">
        <p>Não encontramos uma compra ativa para este e-mail. Isso acontece quando a compra foi reembolsada ou cancelada.</p>
        <p>Se você acha que é um engano, escreva para <b className="selecionavel">{SUPORTE}</b> com o e-mail da compra.</p>
        <Link className="btn btn-principal btn-largo" href="/entrar/">Entrar com outro e-mail</Link>
      </Aviso>
    );
  } else if (status === 'sem_internet') {
    corpo = (
      <Aviso titulo="Sem internet">
        <p>Na primeira vez, o app precisa de internet para baixar as receitas. Depois disso, elas ficam no seu celular e funcionam sem internet.</p>
        <button className="btn btn-principal btn-largo" onClick={recarregar}>Tentar de novo</button>
      </Aviso>
    );
  } else if (status === 'conferir') {
    corpo = (
      <Aviso titulo="Conecte-se à internet">
        <p>Faz mais de 30 dias que o app não confere o seu acesso. Ligue a internet por um instante e toque no botão.</p>
        <button className="btn btn-principal btn-largo" onClick={recarregar}>Conferir agora</button>
      </Aviso>
    );
  } else {
    corpo = <main className="conteudo">{children}{!semRodape && <Rodape />}</main>;
  }

  return (
    <>
      <header className="topo nao-imprimir">
        {voltar && <button className="voltar" onClick={() => (window.history.length > 1 ? router.back() : router.push(voltar))}>‹ Voltar</button>}
        <h1>{titulo}</h1>
        {acoes}
      </header>
      {corpo}
      <NavInferior ativa={ativa} />
    </>
  );
}
