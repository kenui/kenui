# Receitas Bem Leves

App web instalável (PWA) com 500 receitas sem açúcar adicionado. A pessoa compra na Hotmart, recebe o acesso por e-mail e entra no app só com o e-mail, sem senha. Depois do primeiro acesso, o app funciona sem internet.

- **App:** Next.js em modo estático (`out/`), publicado no Hostinger em `app.dividaclara.com.br`.
- **Login, banco e webhook:** Supabase (plano grátis).
- **E-mails:** Resend, com remetente do domínio `dividaclara.com.br`.
- **Conteúdo:** arquivos JSON neste repositório, conferidos por um validador.

## Sumário

1. [Rodar no computador](#1-rodar-no-computador)
2. [Adicionar ou editar receitas](#2-adicionar-ou-editar-receitas)
3. [Publicar pela primeira vez](#3-publicar-pela-primeira-vez)
4. [Publicar mudanças depois](#4-publicar-mudanças-depois)
5. [Como as peças funcionam](#5-como-as-peças-funcionam)
6. [Fontes da nutrição](#6-fontes-da-nutrição)
7. [Estrutura das pastas](#7-estrutura-das-pastas)

---

## 1. Rodar no computador

Precisa do Node.js 20 ou mais novo.

```bash
cd receitas-bem-leves
npm install
node scripts/gerar-plano.mjs
node scripts/gerar-pacote.mjs --demo      # cria public/pacote-demo.json (só para teste local)
NEXT_PUBLIC_MODO_DEMO=1 npx next dev      # abre em http://localhost:3000
```

No **modo demonstração** não há login: o app lê as receitas de `public/pacote-demo.json`. Esse arquivo nunca vai para o ar: ele está no `.gitignore`, e a publicação confere que ele não existe.

### Comandos do dia a dia

| Comando | O que faz |
|---|---|
| `npm run nutricao` | Recalcula calorias e carboidratos de todas as receitas e atualiza a etiqueta low carb |
| `npm run validar` | Confere as receitas e o cadastro de ingredientes; sai com erro se algo quebrar as regras |
| `npm test` | Testa o validador e as regras do webhook da Hotmart |
| `npm run revisao` | Gera `docs/receitas-para-revisao.md` com todas as receitas em texto corrido |
| `npm run checar` | Roda `nutricao`, `validar` e `test` em sequência |
| `node scripts/gerar-plano.mjs` | Monta o cardápio de 4 semanas (`conteudo/plano.json`) |
| `node scripts/folha-de-contato.mjs` | Gera as 500 ilustrações, a folha de contato e o relatório das ilustrações |
| `node scripts/gerar-icones.mjs` | Gera os ícones da tela inicial |

## 2. Adicionar ou editar receitas

1. Copie um arquivo de `conteudo/receitas/` parecido com a receita nova. Renomeie para `rbl-NNNN-nome-da-receita.json`, com o próximo número livre.
2. Preencha nome, `slug` (o nome sem acento, com hífens), categoria, tempos, rendimento, porções, ingredientes, preparo, dicas e ilustração. Os campos estão explicados abaixo.
3. Cada ingrediente aponta para um `id` do cadastro em `conteudo/ingredientes/`. Se ele não existir, cadastre antes (veja "Cadastrar um ingrediente").
4. Não preencha `nutricao` nem `etiquetas.low_carb` à mão: rode `npm run nutricao`.
5. Rode `npm run validar` e corrija o que ele apontar.
6. Rode `node scripts/gerar-plano.mjs` se a receita deve poder entrar no cardápio.
7. Faça commit. A publicação acontece sozinha (seção 4).

### Campos de um ingrediente na receita

```json
{
  "grupo": "Massa",
  "ingrediente": "aveia-em-flocos",
  "quantidade": 2,
  "medida": "xicara",
  "texto": "2 xícaras (chá) de aveia em flocos",
  "alternativa": { "ingrediente": "farinha-de-trigo", "texto": "ou 1 e 1/2 xícara de farinha de trigo" },
  "opcional": false
}
```

- `medida`: `unidade`, `xicara`, `colher_sopa`, `colher_cha`, `pitada`, `dente`, `g` ou `ml`. Para o que se compra por peso (queijo, carne, ricota), prefira `g` e escreva a medida caseira no `texto`.
- `texto` é o que aparece na tela. `quantidade` e `medida` entram no cálculo e na lista de compras.
- `grupo` é opcional e separa massa, recheio, calda etc.
- Itens `opcional: true` e as alternativas não entram no cálculo nutricional.

### Outros campos importantes

- `tempo`: `preparo_min`, `cozimento_min`, `descanso_min` (opcional) e `total_min`.
- `forno`: `{ "temperatura_c": 180, "tempo_min": 40, "preaquecer": true }`. É obrigatório quando algum passo fala em forno.
- `destaques`: `cafe_sem_pao`, `substitutos_do_pao`, `doces_e_bolos` e `rapidas_15min`. Use `rapidas_15min` somente quando `total_min` for até 15.
- `refeicoes_do_plano`: `cafe_da_manha`, `lanche`, `almoco` e `jantar`. Acompanhamentos (arroz, purê, farofa) e bebidas muito leves não entram sozinhos no plano.
- `ilustracao`:
  - `prato_base`: um valor da lista em `conteudo/regras.json`.
  - `massa`: `clara`, `chocolate`, `cenoura`, `banana`, `integral` ou `queijo`.
  - `cobertura`: opcional.
  - `enfeites`: só valores que sejam o `enfeite` de algum ingrediente da receita.
- `foto`: só nas receitas da página de vendas. Veja "Fotos" abaixo.

### Cadastrar um ingrediente

Cadastre em um arquivo de `conteudo/ingredientes/` (`base.json` ou um novo, como `extras.json`):

```json
{
  "id": "ricota",
  "nome": "ricota",
  "sinonimos": [],
  "fonte_nutricao": "taco:469",
  "secao_mercado": "laticinios_frios",
  "facil_de_achar": true,
  "gramas_por_medida": {
    "xicara": { "g": 246, "fonte": "USDA 170851: 1 cup = 246 g" },
    "g": { "g": 1, "fonte": "grama" }
  },
  "proibido": false,
  "adocante": null,
  "enfeite": null
}
```

- `fonte_nutricao` pode ser de três tipos:
  - `taco:<número>`: veja `conteudo/fontes/taco-alimentos.csv`.
  - `usda:<fdc_id>`: veja `conteudo/fontes/usda-*.json`.
  - `especial:<id>`: veja `conteudo/fontes/especiais.json`.
- Para trazer um alimento novo da USDA:
  1. Baixe a base SR Legacy (o link está no topo de `scripts/fontes/extrair-usda.mjs`).
  2. Rode `node scripts/fontes/extrair-usda.mjs <pasta> <fdc_id>`.
- Toda medida caseira precisa dizer de onde veio o peso (`fonte`).
- Valor vazio na tabela (ex.: carboidrato de óleo na TACO): use `ajuste_nutricao` com o valor e o motivo.
- Se `facil_de_achar` for `false`, toda receita que usar o ingrediente precisa trazer uma `alternativa`.

### Regras que o validador confere

As regras estão em `conteudo/regras.json` e `scripts/lib/validacao.mjs`.

**Ingredientes e textos**

- Nenhum ingrediente proibido: açúcar, mel, melado, rapadura, xaropes, leite condensado, achocolatado e outros. Os termos também são procurados no texto, com e sem acento; expressões como "sem açúcar" são aceitas.
- Adoçantes aceitos: eritritol, xilitol, stevia, sucralose e fruta.
- Ingrediente difícil de achar precisa de alternativa.
- Pelo menos uma dica de substituição.
- Nenhuma promessa de saúde (glicemia, cura, emagrecer e outros termos da lista).

**Nutrição e etiquetas**

- A nutrição precisa existir, ser calculada pelo script e bater com o arquivo de cálculo.
- A etiqueta low carb só vale com no máximo 15 g de carboidrato por porção.

**Preparo**

- Nenhum passo vazio.
- Forno com temperatura e tempo realistas.

**Repetição e ilustração**

- Sem receitas repetidas: mesmo id, mesmo nome, ou 85% ou mais dos ingredientes iguais na mesma categoria.
- A ilustração só desenha enfeites de ingredientes que a receita tem.

### Fotos

As 6 receitas da página de vendas apontam para fotos em `public/fotos/`:

- `pao-de-frigideira.jpg`
- `misto-quente-sem-pao.jpg`
- `bolo-de-banana.jpg`
- `panqueca-salgada.jpg`
- `bolo-de-chocolate.jpg`
- `panquecas-de-banana.jpg`

Coloque os arquivos com esses nomes, de preferência com cerca de 1200 px de largura, em JPG e com até 200 KB cada. Enquanto uma foto não existir, a página da receita mostra a ilustração.

## 3. Publicar pela primeira vez

Faça uma vez só, nesta ordem. Nenhum passo tem custo.

### 3.1 Supabase (login, banco e webhook)

1. Crie uma conta em supabase.com e um projeto novo no plano Free, na região São Paulo (`sa-east-1`). Guarde a senha do banco.
2. Em **SQL Editor > New query**, cole todo o arquivo `supabase/migrations/0001_inicial.sql` e clique em **Run**.
3. Em **Authentication > URL Configuration**:
   - Em **Site URL**, coloque `https://app.dividaclara.com.br`.
   - Em **Redirect URLs**, adicione `https://app.dividaclara.com.br/entrar/confirmar/`.
4. Em **Authentication > Sign In / Providers > Email**:
   - Deixe o e-mail ligado e desligue **Allow new users to sign up**. Só o webhook cria usuários.
   - Em **Email OTP Expiration**, coloque `3600` e confira se **Email OTP Length** está em `6`.
5. Em **Authentication > Emails > Magic Link**:
   - Em **Subject**, coloque `Seu código de acesso: {{ .Token }}`.
   - No corpo, cole o conteúdo de `supabase/modelos-email/link-magico.html`.
6. Em **Project Settings > API**, anote três valores: a **Project URL**, a chave **anon public** e a chave **service_role**. A service_role é secreta: não mande para ninguém nem coloque no app.
7. Em **Account > Access Tokens**, crie um token para o GitHub publicar a função. Anote também o **Reference ID** do projeto, que fica em **Project Settings > General**.

### 3.2 Resend (e-mails)

1. Crie uma conta em resend.com, no plano grátis: 3.000 e-mails por mês e 100 por dia.
2. Em **Domains**, adicione `dividaclara.com.br` e copie os registros de DNS mostrados.
3. No **Hostinger > Domínios > dividaclara.com.br > DNS**, adicione esses registros (SPF, DKIM e MX de retorno) e espere o Resend marcar o domínio como **Verified**.
4. Em **API Keys**, crie uma chave.
5. No Supabase, em **Authentication > Emails > SMTP Settings**, ligue o SMTP próprio:
   - Host `smtp.resend.com`, porta `465`.
   - Usuário `resend`; a senha é a chave do Resend.
   - Remetente `acesso@dividaclara.com.br`, com o nome `Receitas Bem Leves`.
6. Em **Authentication > Rate Limits**, aumente **Emails per hour** para 100.

### 3.3 Segredos da função do webhook

No Supabase, em **Edge Functions > Secrets**, crie:

| Nome | Valor |
|---|---|
| `HOTMART_HOTTOK` | o token "hottok" que aparece na tela de webhooks da Hotmart (passo 3.6) |
| `RESEND_API_KEY` | a chave do Resend |
| `REMETENTE` | `Receitas Bem Leves <acesso@dividaclara.com.br>` |
| `URL_APP` | `https://app.dividaclara.com.br` |
| `HOTMART_PRODUTO_ID` | (opcional) o código do produto na Hotmart, para ignorar avisos de outros produtos |

### 3.4 Hostinger (subdomínio do app)

1. Em **Domínios > Subdomínios** do `dividaclara.com.br`, crie `app`. Anote a pasta criada, por exemplo `public_html/app`.
2. Em **SSL**, instale o certificado grátis para `app.dividaclara.com.br`.
3. Em **Arquivos > Contas FTP**, crie uma conta FTP com acesso só à pasta do subdomínio. Anote o servidor, o usuário e a senha.

### 3.5 GitHub (publicação automática)

No repositório, em **Settings > Secrets and variables > Actions > New repository secret**, crie:

| Nome | Valor |
|---|---|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_ANON_KEY` | chave anon public |
| `SUPABASE_SERVICE_ROLE_KEY` | chave service_role |
| `SUPABASE_ACCESS_TOKEN` | token criado no passo 3.1.7 |
| `SUPABASE_PROJECT_REF` | Reference ID do projeto |
| `FTP_SERVIDOR`, `FTP_USUARIO`, `FTP_SENHA` | dados da conta FTP |
| `FTP_PASTA` | pasta do subdomínio, terminando em `/` (ex.: `public_html/app/`) |

Depois, em **Actions > Receitas Bem Leves: publicar > Run workflow**, rode a primeira publicação. Ela faz tudo:

1. Confere as receitas.
2. Envia o pacote de receitas ao Supabase.
3. Publica a função do webhook.
4. Monta o app.
5. Envia o app ao Hostinger.

A tarefa **Receitas Bem Leves: manter Supabase acordado** roda sozinha todo dia, para o projeto grátis não pausar.

### 3.6 Hotmart (webhook)

1. Na Hotmart, entre em **Ferramentas > Webhook (API e Notificações)** e clique em **Cadastrar webhook**.
2. Preencha:
   - **Nome:** `Receitas Bem Leves`
   - **URL de envio:** `https://<Reference ID>.supabase.co/functions/v1/hotmart-webhook`
   - **Produto:** Receitas Bem Leves
   - **Versão:** `2.0.0`
   - **Eventos:** Compra aprovada, Compra completa, Compra reembolsada, Chargeback e Compra cancelada.
3. Copie o **hottok** que aparece na tela de webhooks e salve no segredo `HOTMART_HOTTOK` (passo 3.3).
4. Use o botão de **teste** da Hotmart para mandar uma compra aprovada de teste. Depois confira no Supabase:
   - **Table Editor > compradores:** o e-mail aparece como `ativo`.
   - **Edge Functions > hotmart-webhook > Logs:** a função respondeu "acesso liberado".

O que cada aviso faz:

- **Compra aprovada ou completa:** cria o usuário, libera o acesso e manda o e-mail de boas-vindas (uma vez só).
- **Reembolso, chargeback ou cancelamento:** bloqueia o acesso. Na próxima vez que o celular da pessoa ficar online, o app apaga as receitas guardadas e mostra o aviso.
- **Pedido de reembolso em análise:** fica registrado, mas não bloqueia.

## 4. Publicar mudanças depois

Qualquer commit na branch `main` que mexa em `receitas-bem-leves/` publica sozinho. Receitas novas chegam aos celulares na próxima vez que a pessoa abrir o app com internet. Se uma receita quebrar as regras, a publicação para e mostra o erro.

## 5. Como as peças funcionam

- **Proteção do conteúdo:**
  - O app é público e estático, mas não traz receitas dentro dele.
  - Depois do login, ele baixa o pacote de receitas da tabela `pacote_receitas`.
  - O banco só entrega o pacote para quem tem compra ativa (RLS).
- **Login:**
  - O e-mail traz um botão e um código numérico. O código existe porque, no iPhone, o app instalado na tela inicial não recebe o login feito pelo link.
  - O botão abre uma página com "Entrar no app". Assim, programas que abrem links sozinhos não gastam o link.
  - Só e-mails que compraram recebem acesso.
- **Sem internet:**
  - O service worker (`out/sw.js`) guarda todas as telas.
  - As receitas ficam no IndexedDB do aparelho.
  - O app confere o acesso sempre que há internet e pede uma conferência a cada 30 dias.
- **Seus dados:** favoritos e trocas do plano ficam no aparelho, com cópia na conta (tabela `dados_do_usuario`). Lista de compras e receitas vistas ficam só no aparelho.
- **Ilustrações:**
  - São desenhadas por código (`ilustracoes/`), a partir dos dados de cada receita, e não há arquivos de imagem.
  - Os pratos base estão em `pratos.mjs` e os enfeites em `enfeites.mjs`.
  - A tabela ingrediente → enfeite é o campo `enfeite` do cadastro.
  - Cada receita tem variação própria, por um sorteio com semente fixa no id.

## 6. Fontes da nutrição

- **TACO**, Tabela Brasileira de Composição de Alimentos, 4ª edição revisada e ampliada (NEPA/Unicamp, 2011).
  - Arquivos em `conteudo/fontes/taco-*.csv`, tirados da planilha original pelo projeto aberto [taco-api](https://github.com/raulfdm/taco-api).
  - Nessa conversão, "Tr" virou 0, e "NA" e "*" ficaram vazios.
- **USDA FoodData Central**, SR Legacy (abril/2018).
  - Usada para o que a TACO não tem ou tem em reavaliação: cacau 100%, especiarias, leite integral e outros.
  - Também é a fonte do peso das medidas caseiras.
- **Regra do app** (`conteudo/fontes/especiais.json`):
  - Eritritol, stevia e sucralose contam 0 kcal e 0 g de carboidrato.
  - O xilitol conta 2,4 kcal/g e o carboidrato cheio.
- Na tela, os números aparecem como "valores aproximados".

## 7. Estrutura das pastas

```
app/                 telas (Next.js, export estático)
componentes/         moldura, cartões, modo cozinha, bônus, estado do app
lib/                 busca, plano, lista de compras, Supabase, armazenamento
ilustracoes/         pratos base, enfeites e montagem das ilustrações SVG
conteudo/
  receitas/          uma receita por arquivo (fonte da verdade)
  ingredientes/      cadastro de ingredientes (vários arquivos)
  nutricao/          cálculo linha por linha de cada receita (gerado)
  bonus/             conteúdo dos 5 bônus
  fontes/            TACO, USDA e valores especiais
  regras.json        categorias, medidas, termos proibidos, listas de ilustração
  plano.json         cardápio de 4 semanas (gerado)
scripts/             validador, nutrição, plano, pacote, service worker, ícones, folha de contato
supabase/            tabelas (SQL), função do webhook e modelo de e-mail
testes/              testes do validador e do webhook
docs/                proposta, relatórios, folha de contato e receitas para revisão
public/              ícones, manifesto, .htaccess e fotos
```
