'use client';
// Upsell 1 (R$ 47): Cardápio de 12 Semanas + Guia de Marmitas da Semana.
import { BotoesHotmart, PaginaOferta } from '../../../componentes/PaginaOferta';

export default function Upsell() {
  return (
    <PaginaOferta aviso="Sua compra foi aprovada. O acesso ao app já está a caminho do seu e-mail. Não feche esta página.">
      <section className="bloco">
        <h1 className="titulo-oferta">Daqui a 4 semanas, a pergunta “o que eu faço hoje?” volta</h1>
        <p>O app que você acabou de comprar traz um cardápio de 4 semanas. Ele resolve o primeiro mês. Na quinta semana, você vai abrir a geladeira de novo sem saber o que cozinhar, e é aí que a vontade de comprar um pão de padaria aparece.</p>
        <p>Por isso existe uma oferta que só aparece agora, uma vez, logo depois da compra.</p>
      </section>

      <section className="bloco">
        <h2 className="subtitulo-oferta">Cardápio de 12 Semanas + Guia de Marmitas da Semana</h2>
        <div className="duas-telas">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/funil/cardapio12.jpg" alt="Tela do Cardápio de 12 Semanas no app" width="375" height="760" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/funil/marmitas.jpg" alt="Tela do Guia de Marmitas no app" width="375" height="760" />
        </div>
        <ul className="lista-oferta">
          <li><b>84 dias de cardápio pronto:</b> café da manhã, lanche, almoço e jantar, sem repetir prato na mesma semana. São mais de 300 receitas diferentes ao longo das 12 semanas.</li>
          <li><b>A lista de compras de cada semana em um toque:</b> o app soma os ingredientes e separa por seção do mercado, do hortifrúti aos temperos.</li>
          <li><b>O domingo de cozinha:</b> como fazer em cerca de 2 horas os almoços e jantares da semana, começando pelo que vai ao forno.</li>
          <li><b>O que dura quanto:</b> o que fica até 3 dias na geladeira, o que vai para o congelador por até 2 meses, como descongelar e esquentar.</li>
          <li><b>4 domingos já montados</b>, com 2 pratos principais, 1 acompanhamento e 1 lanche cada, e a lista dos pratos do app que congelam bem.</li>
        </ul>
        <p>Tudo entra no mesmo app, com o mesmo e-mail. Não tem outra senha nem outro aplicativo.</p>
      </section>

      <section className="bloco caixa-preco">
        <p className="preco-oferta">R$ 47,00 <small>pagamento único</small></p>
        <p>A cobrança usa o mesmo cartão da compra que você acabou de fazer, sem digitar nada de novo. Se pagou com Pix ou boleto, a Hotmart mostra como pagar.</p>
        <p><b>Garantia de 7 dias:</b> se não gostar, peça o reembolso pela Hotmart. O app principal continua seu.</p>
        <BotoesHotmart />
      </section>

      <section className="bloco">
        <h2 className="subtitulo-oferta">Para quem não é</h2>
        <p>Se você gosta de decidir o prato na hora e cozinha um pouco todo dia, as 4 semanas do app já bastam. Pode recusar no botão acima sem problema: seu acesso ao app não muda.</p>
      </section>
    </PaginaOferta>
  );
}
