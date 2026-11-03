'use client';
import Link from 'next/link';
import { Rodape, SUPORTE } from '../../componentes/Moldura';

export default function NaoRecebi() {
  return (
    <div className="entrar">
      <header className="topo"><h1>Não recebi meu acesso</h1></header>
      <main className="conteudo">
        <section className="cartao-aviso">
          <h2>Faça nesta ordem</h2>
          <ol className="passos">
            <li><div><b>Espere alguns minutos.</b> Depois da compra aprovada, o e-mail de boas-vindas pode levar até 10 minutos. Compra por boleto só é aprovada quando o banco confirma o pagamento (até 3 dias úteis).</div></li>
            <li><div><b>Procure no spam e na aba Promoções.</b> Procure pelo remetente “Receitas Bem Leves” ou pela palavra “acesso”.</div></li>
            <li><div><b>Confira o e-mail da compra.</b> O acesso é liberado para o mesmo e-mail que você usou na Hotmart. O e-mail de confirmação da Hotmart mostra qual foi.</div></li>
            <li><div><b>Entre direto no app.</b> Toque no botão abaixo, digite o e-mail da compra e peça um novo e-mail de acesso.</div></li>
          </ol>
          <Link className="btn btn-principal btn-largo btn-grande" href="/entrar/">Entrar com o e-mail da compra</Link>
        </section>
        <section className="cartao-aviso">
          <h2>Ainda não deu certo?</h2>
          <p>Escreva para o suporte e conte qual e-mail você usou na compra. Se tiver, mande também o número do pedido da Hotmart (começa com HP).</p>
          <p><b className="selecionavel">{SUPORTE}</b></p>
          <a className="btn btn-secundario" href={`mailto:${SUPORTE}?subject=N%C3%A3o%20recebi%20meu%20acesso`}>Abrir meu e-mail</a>
        </section>
        <Rodape />
      </main>
    </div>
  );
}
