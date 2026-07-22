# Atualizacao Telz em VPS

Script:

```bash
sudo bash scripts/update-telz.sh /opt/telz
```

Fluxo:

1. bloqueia atualizacoes simultaneas;
2. registra commit atual;
3. cria backup;
4. atualiza codigo via Git;
5. instala dependencias;
6. executa typecheck, testes e build;
7. revisa Alembic;
8. pergunta antes de `alembic upgrade head`;
9. reinicia `telz-api`, `telz-web` e `telz-whatsapp-gateway` quando instalado;
10. executa health check.

Se o health check falhar, o script volta codigo/build para o commit anterior, mas nao faz downgrade de banco.
