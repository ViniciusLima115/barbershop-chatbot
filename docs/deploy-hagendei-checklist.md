# Checklist de deploy — domínio hagendei.com

Passos manuais (fora do acesso do assistente) para colocar `hagendei.com` no ar
apontando para o servidor de produção atual. Siga na ordem — pular a Etapa 3
(rebuild) é o erro mais comum: o site parece "no ar" (DNS e TLS ok) mas o
frontend continua chamando a API antiga e o backend rejeita as requisições do
novo domínio.

## 1. DNS (Hostinger, ou onde o domínio estiver gerenciado)

Criar dois registros `A` na zona DNS de `hagendei.com`, apontando para o IP
público do servidor onde o Caddy roda hoje:

| Tipo | Host | Valor | TTL |
|------|------|-------|-----|
| A | `hagendei.com` (ou `@`) | `<IP do servidor>` | 3600 (ou automático) |
| A | `api.hagendei.com` | `<IP do servidor>` | 3600 (ou automático) |

Se o frontend também deve responder em `www.hagendei.com`, adicionar um terceiro
registro `A` (ou `CNAME` para `hagendei.com`) para `www` — e lembrar que o DNS
sozinho não basta: o `Caddyfile` só tem blocos de site para `{$APP_DOMAIN}` e
`{$API_DOMAIN}`, então é preciso adicionar `www.hagendei.com` também como host
no bloco do `{$APP_DOMAIN}` (ou um bloco próprio) para o Caddy de fato servir
e emitir certificado para esse hostname.

## 2. Variáveis de ambiente no servidor de produção

Existem **dois arquivos `.env` diferentes** no servidor — os dois precisam ser
atualizados, não só um:

**a) `.env` na raiz do projeto** (usado pelo `docker-compose.yml` para o Caddy
e para o *build* do frontend):

```
APP_DOMAIN=hagendei.com
API_DOMAIN=api.hagendei.com
NEXT_PUBLIC_API_URL=https://api.hagendei.com
```

**b) `backend/.env.production`** (usado em runtime pelo backend — controla CORS
e os links públicos gerados em mensagens/e-mails):

```
CORS_ALLOWED_ORIGINS=https://hagendei.com
FRONTEND_URL=https://hagendei.com
BACKEND_PUBLIC_BASE_URL=https://api.hagendei.com
BOOKING_PUBLIC_BASE_URL=https://hagendei.com
ALLOWED_HOSTS=api.hagendei.com,127.0.0.1
```

Se o frontend também responde em `https://www.hagendei.com`, inclua as duas
variantes em `CORS_ALLOWED_ORIGINS` (formato geralmente aceita lista separada
por vírgula — confirme o formato esperado em `backend/app/config.py` antes de
aplicar).

`ALLOWED_HOSTS` é obrigatório em produção e é validado contra o header `Host`
real de cada requisição (`TrustedHostMiddleware`) — diferente do CORS, que só
afeta chamadas feitas por um navegador, isso bloqueia **qualquer** requisição
(inclusive `curl`) se o domínio não estiver na lista. Sem essa variável
atualizada, o backend inteiro responde `400 Invalid host header` para tudo,
incluindo os próprios comandos de verificação abaixo.

**Importante:** inclua `127.0.0.1` na lista mesmo em produção — o healthcheck
interno do container do backend (`docker-compose.yml`) chama
`http://127.0.0.1:8000/health` de dentro do próprio container, com header
`Host: 127.0.0.1`. O fallback padrão do backend (quando `ALLOWED_HOSTS` não
está definido) já inclui `127.0.0.1`, mas ao definir a variável explicitamente
esse fallback deixa de valer — sem incluir `127.0.0.1` na lista, o healthcheck
passa a falhar, o container do backend nunca fica "healthy", e o Caddy (que
depende de `backend: condition: service_healthy` no `docker-compose.yml`)
nunca sobe — o site fica fora do ar por completo, não só a API.

## 3. Rebuild — não é só reiniciar

`NEXT_PUBLIC_API_URL` é um *build arg* do frontend (`docker-compose.yml`,
serviço `frontend`, seção `build.args`): ele é gravado dentro dos arquivos
estáticos do Next.js no momento do build, não é lido em runtime. Um simples
`restart` do container **não** aplica esse valor novo — é necessário reconstruir
as imagens:

```bash
cd /caminho/do/projeto/no/servidor
docker compose up -d --build
```

**Não** use `-f docker-compose.yml -f docker-compose.prod.yml` juntos — o
`docker-compose.prod.yml` já é só um `include: [docker-compose.yml]`, e passar
os dois arquivos via `-f` faz o Compose carregar o mesmo conteúdo duas vezes,
o que quebra a validação (`items at 0 and 1 are equal` em campos de lista como
`security_opt`) e o comando falha com erro antes de reconstruir qualquer
coisa. O comando acima (`docker compose up -d --build`, sem `-f`) é o mesmo
usado por `scripts/deploy.sh` neste repositório e é o jeito certo de rodar.

Isso reconstrói `frontend` e `backend` com as variáveis novas e reinicia todos
os serviços (incluindo o Caddy, que já lê `{$APP_DOMAIN}`/`{$API_DOMAIN}`
diretamente do `Caddyfile` sem precisar de nenhuma mudança de código) em uma
única passada — não precisa rodar `restart` separadamente depois.

O Caddy emite o certificado TLS automaticamente via Let's Encrypt assim que o
DNS resolver para o IP correto — não é necessário configurar certificado
manualmente.

## 4. Verificação

- [ ] `dig hagendei.com` e `dig api.hagendei.com` resolvem para o IP do servidor.
- [ ] `curl -I https://hagendei.com` retorna `200` (ou redirect esperado) com
      certificado válido.
- [ ] `curl -I https://api.hagendei.com/docs` (ou outro endpoint público)
      retorna `200` com certificado válido.
- [ ] Abrir `https://hagendei.com` num navegador (não só `curl`) e confirmar que
      a página carrega dados reais (ex.: login funciona, uma página pública de
      agendamento carrega horários) — isso testa a chamada real do browser para
      a API, que é onde um CORS mal configurado aparece e que um `curl` direto
      não pega.
- [ ] Abrir o DevTools do navegador (aba Network/Console) na página carregada e
      confirmar que não há erros de CORS nem chamadas ainda apontando para o
      domínio antigo.

## Troubleshooting

- **Página carrega mas nenhum dado aparece / erro de CORS no console do
  navegador**: `CORS_ALLOWED_ORIGINS` em `backend/.env.production` não inclui o
  domínio novo, ou o backend não foi reiniciado depois de editar esse arquivo —
  rode novamente o `up -d --build` da Etapa 3.
- **Frontend ainda chama a URL antiga da API**: o `NEXT_PUBLIC_API_URL` foi
  atualizado no `.env` mas as imagens não foram reconstruídas — `docker compose
  up -d --build` sem o `--build` não é suficiente, o cache da imagem antiga
  seria reaproveitado.
- **Links de confirmação/reagendamento enviados por WhatsApp/e-mail apontam
  para o domínio antigo**: `BOOKING_PUBLIC_BASE_URL` em
  `backend/.env.production` não foi atualizado.
- **`400 Invalid host header` em qualquer requisição, inclusive `curl -I
  https://api.hagendei.com/docs`**: `ALLOWED_HOSTS` em
  `backend/.env.production` ainda não inclui `api.hagendei.com` — atualize e
  rode o `up -d --build` da Etapa 3 novamente.
- **Site inteiro fora do ar depois do `up -d --build` (Caddy nunca inicia,
  não só a API dando erro)**: verifique `docker compose ps` — se o container
  `backend` está com status diferente de `healthy` (ex. `unhealthy` ou preso em
  `starting`), o `ALLOWED_HOSTS` provavelmente foi definido sem incluir
  `127.0.0.1`, e o healthcheck interno do container está falhando. Corrija
  `ALLOWED_HOSTS=api.hagendei.com,127.0.0.1` em `backend/.env.production` e
  rode o `up -d --build` novamente — o Caddy só sobe depois que o backend
  reportar `healthy`.
