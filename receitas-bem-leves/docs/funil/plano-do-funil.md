# Funil do Receitas Bem Leves

Situação: produtos, páginas e app prontos. Falta configurar na Hotmart (seção 5) e rodar 2 passos no Supabase (seção 6).

## 1. O mapa

```
Anúncio (Meta) → Página de vendas (receitas.dividaclara.com.br)
  → Checkout Hotmart personalizado + Order bump "Caderno para Imprimir" (R$ 14,90)
  → Upsell: Cardápio de 12 Semanas + Guia de Marmitas (R$ 47)   app.dividaclara.com.br/oferta/cardapio-12-semanas/
      └ recusou → Downsell: só o Cardápio de 12 Semanas (R$ 27)  app.dividaclara.com.br/oferta/so-o-cardapio/
  → Página de obrigado                                             app.dividaclara.com.br/obrigado/
  → E-mail de boas-vindas (automático) → App
```

| Etapa | O que a pessoa vê | O que queremos | Por quê |
|---|---|---|---|
| Página de vendas | pão, bolo e doce sem açúcar adicionado, 500 receitas, R$ 27,90 | clique em "Quero as receitas agora" | 32% das visitas já iniciam o checkout (dado real, seção 2): a página funciona |
| Checkout | imagem com o app no celular, "o que você recebe", garantia | pagar | hoje só 1 em 6 que inicia o checkout termina a compra: é o maior vazamento |
| Order bump | caixinha do Caderno para Imprimir | marcar a caixinha | público 45+ gosta de papel na cozinha; custa pouco perto do principal |
| Upsell | "Daqui a 4 semanas, a pergunta o que eu faço hoje? volta" | aceitar com 1 clique | o app tem 4 semanas de cardápio; a dúvida do dia a dia volta depois |
| Downsell | "E só o cardápio, sem as marmitas?" | aceitar | quem recusou pelo preço ou não quer cozinhar no domingo |
| Obrigado | como entrar no app em 4 passos | entrar hoje | quem entra no primeiro dia pede menos reembolso |

## 2. O que os seus anúncios mostram (3 e 4 de novembro)

| | 03/11 | 04/11 | Total |
|---|---|---|---|
| Investimento | R$ 55,02 | R$ 9,90 | **R$ 64,92** |
| Impressões | 1.165 | 189 | 1.354 |
| CPM | R$ 47,23 | R$ 52,38 | ≈ R$ 47,95 |
| Cliques no link (CTR) | 14 (1,2%) | 7 (3,7%) | 21 (1,55%) |
| Visitas à página | 13 | 6 | 19 (90% dos cliques) |
| Checkouts iniciados | 4 | 2 | **6 (32% das visitas)** |
| Compras | 1 | 0 | **1 (17% dos checkouts)** |
| Custo por compra | R$ 55,02 | — | **R$ 64,92** |

`[DADO REAL: relatórios do Gerenciador de Anúncios de 03/11 e 04/11]`

Leitura, com a ressalva de que **1 compra é pouco para concluir qualquer coisa**:

- **A página está fazendo o papel dela.** 32% das visitas iniciam o checkout, acima do que costuma ser normal para produto barato (10% a 20%) `[HIPÓTESE: referência de mercado, conservadora]`.
- **O vazamento está no checkout.** De 6 pessoas que começaram a pagar, 1 terminou. O normal fica entre 30% e 50% `[HIPÓTESE]`. Isso combina com o checkout sem identidade visual e com Pix ou boleto gerados e não pagos. Confira na Hotmart quantas compras ficaram "aguardando pagamento".
- **O CPM está alto** (cerca de R$ 48). Em público amplo no Brasil é comum ficar entre R$ 15 e R$ 30 `[HIPÓTESE]`. Antes de culpar o anúncio:
  - A conta de anúncios se chama **"ingles.da.gringa"**. Se o pixel e a conta são os de outra oferta (curso de inglês), o Meta está aprendendo um público misturado. Crie uma **conta de anúncios e um pixel só para o Receitas Bem Leves**; não custa nada e não depende de domínio novo.
  - Confira se algum anúncio está com **alcance limitado** ou se foi reprovado e depois aprovado.
  - Nicho de saúde: o anúncio não pode dizer nem insinuar que a pessoa tem diabetes ("você tem diabetes?" é barrado). Fale de "quem corta o açúcar" e da comida.

## 3. A conta por cliente

Taxa da Hotmart considerada: 9,9% + R$ 1,00 por venda `[HIPÓTESE: confira no seu plano]`. Reembolso: 5% `[HIPÓTESE]`.

| | Só o produto (hoje) | Com o funil | Funil, cenário pessimista |
|---|---|---|---|
| Aceitam o bump | — | 25% | 17,5% |
| Aceitam o upsell | — | 12% | 8,4% |
| Aceitam o downsell (dos que recusaram) | — | 15% | 10,5% |
| Venda média por comprador | R$ 27,90 | R$ 40,83 | R$ 36,95 |
| Líquido por comprador (depois de taxa e reembolso) | **R$ 22,90** | **R$ 33,80** | **R$ 30,50** |
| **Máximo que dá para pagar por venda sem prejuízo** | R$ 22,90 | **R$ 33,80** | R$ 30,50 |

`[HIPÓTESE: taxas de bump, upsell e downsell conservadoras]`

- **Hoje cada venda custa R$ 64,92 e deixa R$ 22,90.** Mesmo com o funil, R$ 33,80 não paga esse custo.
- **O que fecha a conta é o checkout.** Se 1 em cada 3 que iniciam o checkout comprar (em vez de 1 em 6), o mesmo dinheiro traz o dobro de vendas, e o custo por venda cai para perto de R$ 32. Com o funil, isso fica perto do empate.
- **Ordem de ataque:**
  1. Checkout (imagens, Pix em destaque e lembrete de pagamento).
  2. Order bump.
  3. Conta e pixel próprios (para o CPM).
  4. Só depois, testar anúncios novos.
- **Não aumente a verba ainda.** Chegue a pelo menos R$ 200 investidos, com as mudanças acima, antes de decidir se o anúncio funciona.

## 4. Textos prontos

### Order bump (caixinha no checkout)

- **Título:** Sim! Quero o Caderno de Receitas para Imprimir por R$ 14,90
- **Descrição:** 100 receitas do app em folhas A4 com letra grande, uma por página, mais o cardápio da semana para colar na geladeira. Para cozinhar com o papel na bancada, sem sujar o celular.

### Páginas de upsell, downsell e obrigado

Já estão no ar e são editáveis no código:

- `app/oferta/cardapio-12-semanas/page.jsx`
- `app/oferta/so-o-cardapio/page.jsx`
- `app/obrigado/page.jsx`

**Textos dos botões** (configure na Hotmart, no funil de vendas):

| Página | Botão de sim | Botão de não |
|---|---|---|
| Upsell | Sim, quero as 12 semanas e as marmitas por R$ 47 | Não, obrigado. Vou ficar só com as 4 semanas do app |
| Downsell | Sim, quero só o cardápio de 12 semanas por R$ 27 | Não, obrigado. Quero ir para o app |

### Recuperação de vendas (e-mail, só para quem deixou o e-mail no checkout)

Na Hotmart, veja se o seu plano tem recuperação automática de carrinho abandonado. Se tiver, use estes textos. **WhatsApp só para quem marcou que aceita receber mensagens.**

**1 hora depois, assunto: "Ficou faltando um passo"**
> Oi! Você começou a garantir o Receitas Bem Leves e a compra não foi até o fim. Se foi a internet que caiu ou o cartão que não passou, o link continua valendo: [link do checkout]. No Pix o acesso chega na hora. Se tiver alguma dúvida antes de comprar, é só responder este e-mail.

**24 horas depois, assunto: "Pão no café sem açúcar adicionado"**
> Uma dúvida que aparece muito: "bolo sem açúcar não fica com gosto de adoçante?". No app, os bolos usam eritritol na medida certa ou só a fruta, e o Guia do Adoçante (que vem de bônus) mostra qual usar no forno e qual na bebida gelada. São 500 receitas por R$ 27,90, pagamento único, com 7 dias de garantia pela Hotmart: [link do checkout].

**72 horas depois, assunto: "Último lembrete"**
> Este é o último e-mail sobre o Receitas Bem Leves. Se não for o momento, tudo bem. Se quiser as 500 receitas, com as calorias e os carboidratos de cada porção, o link é este: [link do checkout]. Para não receber mais, responda "sair".

**Pix gerado e não pago (15 minutos depois):**
> Seu Pix do Receitas Bem Leves foi gerado e ainda não apareceu como pago. Ele vale por pouco tempo. Se precisar, gere um novo aqui: [link do checkout].

**Boleto (no dia seguinte e no dia do vencimento):**
> Seu boleto do Receitas Bem Leves vence [data]. Se preferir, pague no Pix pelo mesmo link e o acesso chega na hora: [link do checkout].

### Passada de conformidade

| Frase | Regra | Risco | Situação |
|---|---|---|---|
| "Em todas as receitas do app, não entra… farinha branca" (página de vendas) | Promessa precisa ser verdade (CDC) | VERMELHO antes; VERDE agora | As 106 receitas foram corrigidas e o validador recusa farinha branca daqui para frente |
| "Escolha pelo seu objetivo: … para diabetes" (página de vendas) | Promessa que o app não cumpre; nicho de saúde | AMARELO | O app não tem filtro "para diabetes". Troque por: "Café da manhã sem pão, substitutos do pão, doces e bolos, receitas rápidas e low carb" |
| Exemplo "Misto quente sem pão: 2 porções, 12 min, farinha de amêndoas" (página de vendas) | Página igual ao produto | AMARELO | No app: 1 porção, 10 min, ovos, parmesão, presunto e mussarela. Atualize o exemplo |
| "Daqui a 4 semanas, a pergunta o que eu faço hoje? volta" (upsell) | Sem atributo pessoal nem promessa de saúde | VERDE | Fala da rotina, não da doença |
| "Garantia de 7 dias" (upsell, downsell, checkout) | CDC, direito de arrependimento | VERDE | Configure 7 dias nos 3 produtos novos |
| Anúncios | Meta: não afirmar que o espectador tem diabetes | AMARELO | Use "quem corta o açúcar…", nunca "você tem diabetes?" |

## 5. Configuração na Hotmart (passo a passo)

Os nomes dos menus podem mudar. Se algum não bater, procure pelo nome da função.

1. **Cadastre 3 produtos novos** (Produtos → Cadastrar produto → produto digital / e-book), todos com garantia de 7 dias:
   | Produto | Preço | Arquivo para entregar |
   |---|---|---|
   | Caderno de Receitas para Imprimir | R$ 14,90 | `docs/produtos/caderno-de-receitas-para-imprimir.pdf` |
   | Cardápio de 12 Semanas + Guia de Marmitas | R$ 47,00 | `docs/produtos/cardapio-de-12-semanas.pdf` e `docs/produtos/guia-de-marmitas-da-semana.pdf` |
   | Cardápio de 12 Semanas | R$ 27,00 | `docs/produtos/cardapio-de-12-semanas.pdf` |

   A Hotmart pede uma página de vendas para cada produto. Use as páginas do funil: o caderno pode usar a página de vendas principal.
2. **Order bump:** no produto principal, abra a configuração de checkout ou de Order Bump, escolha o produto "Caderno de Receitas para Imprimir" e cole o título e a descrição da seção 4.
3. **Funil de vendas (upsell de 1 clique):** em Ferramentas → Funil de Vendas, crie o funil:
   - Produto principal → **Upsell:** Cardápio de 12 Semanas + Guia de Marmitas, página `https://app.dividaclara.com.br/oferta/cardapio-12-semanas/`
   - Se recusar → **Downsell:** Cardápio de 12 Semanas, página `https://app.dividaclara.com.br/oferta/so-o-cardapio/`
   - **Final:** `https://app.dividaclara.com.br/obrigado/`
   - Use os textos dos botões da seção 4.

   As páginas já têm o código que mostra os botões da Hotmart. Se o funil pedir um código diferente, me mande que eu troco.
4. **Checkout personalizado:** no produto principal, entre na personalização do checkout:
   - **Imagem do topo:** `docs/funil/checkout-topo-1200x300.png` no computador e `docs/funil/checkout-topo-celular-800x400.png` no celular.
   - **Imagem lateral:** `docs/funil/checkout-lateral-400x900.png`.
   - **Cores:** vinho `#7B1E2C` e verde `#137A3D` no botão.
   - **Pix ligado e em destaque**, cartão parcelado ligado.
   - Se a Hotmart pedir outro tamanho de imagem, me diga o tamanho que eu gero de novo.
5. **Webhook:** no webhook que você já cadastrou, inclua os 3 produtos novos (ou marque "todos os produtos").
6. **Anote o ID (código) de cada um dos 4 produtos:** o principal e os 3 novos. Eles aparecem na lista de produtos.

## 6. No Supabase (depois de cadastrar os produtos)

1. **SQL Editor** → cole o arquivo `supabase/migrations/0002_produtos_extras.sql` → **Run**.
2. **Edge Functions** → hotmart-webhook (a do endereço `smart-function`) → **Code**: cole o arquivo novo `supabase/painel-hotmart-webhook.ts` → **Deploy**.
3. **Edge Functions → Secrets** → crie `HOTMART_PRODUTOS` com os IDs da Hotmart no lugar dos números:
   ```
   {"ID_DO_APP":["app"],"ID_DO_CADERNO":["caderno"],"ID_DO_12_SEMANAS_MARMITAS":["cardapio12","marmitas"],"ID_DO_12_SEMANAS":["cardapio12"]}
   ```
   **Atenção:** com esse segredo criado, avisos de produtos que não estão na lista são ignorados. Por isso o ID do app principal precisa estar nela.
4. Me avise: eu envio o conteúdo dos 3 produtos para o banco e faço uma compra de teste de cada um.
