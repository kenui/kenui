'use client';
import Link from 'next/link';
import { Moldura } from '../../componentes/Moldura';
import { ListaReceitas } from '../../componentes/Receita';
import { useApp } from '../../componentes/Provedor';

function Favoritos() {
  const { pacote, dados } = useApp();
  if (!pacote) return null;
  const lista = dados.favoritos.map((id) => pacote.porId[id]).filter(Boolean);
  return lista.length
    ? <ListaReceitas receitas={lista} />
    : <div className="vazio">Você ainda não tem receitas favoritas. Abra uma receita e toque em “Favoritar”.<Link className="btn btn-principal" href="/receitas/">Ver receitas</Link></div>;
}

export default function Pagina() {
  return <Moldura titulo="Favoritos" ativa="favoritos"><Favoritos /></Moldura>;
}
