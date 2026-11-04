'use client';
// Página de obrigado: última página do funil, depois do upsell/downsell.
import Link from 'next/link';
import { PaginaOferta } from '../../componentes/PaginaOferta';
import { SUPORTE } from '../../componentes/Moldura';

export default function Obrigado() {
  return (
    <PaginaOferta>
      <section className="bloco">
        <h1 className="titulo-oferta">Compra confirmada. Seja bem-vinda, seja bem-vindo!</h1>
        <p>Em poucos minutos chega no seu e-mail a mensagem <b>“Seu acesso ao Receitas Bem Leves chegou”</b>. Compra no Pix libera na hora; no boleto, quando o banco confirmar o pagamento.</p>
      </section>
      <section className="bloco">
        <h2 className="subtitulo-oferta">Como entrar</h2>
        <ol className="passos">
          <li><div>Abra <b>app.dividaclara.com.br</b> no celular.</div></li>
          <li><div>Digite o <b>mesmo e-mail da compra</b> e toque em “Receber acesso por e-mail”.</div></li>
          <li><div>No e-mail, toque em <b>“Entrar no app”</b> ou digite o código de números. Não precisa de senha.</div></li>
          <li><div>Coloque o app na tela inicial: no Android, menu de 3 pontinhos e “Adicionar à tela inicial”; no iPhone, botão de compartilhar e “Adicionar à Tela de Início”.</div></li>
        </ol>
        <Link className="btn btn-principal btn-largo btn-grande" href="/entrar/">Entrar no app agora</Link>
      </section>
      <section className="bloco">
        <p>O e-mail não chegou em 10 minutos? Olhe no spam e na aba Promoções ou Atualizações. Se não achar, escreva para <b className="selecionavel">{SUPORTE}</b> com o e-mail da compra.</p>
      </section>
    </PaginaOferta>
  );
}
