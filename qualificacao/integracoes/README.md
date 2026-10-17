# Qualificação das integrações locais (MYC-13)

Código da prova técnica registrada em [docs/qualificacao-integracoes.md](../../docs/qualificacao-integracoes.md).
Não é código do produto: serve para repetir as verificações. Clipes, sessões dos CLIs e respostas vão para
`.saida/`, ignorada pelo Git.

## Peças

| Arquivo | O que faz |
| --- | --- |
| `ponte_windows.py` | Lado WSL da ponte de notificações: `estado()` e `notificar(título, texto, tag)`, chamando o `powershell.exe` pela interoperabilidade do WSL |
| `ponte_windows.ps1` | Lado Windows: registra o AUMID `MyCut` no HKCU, mostra o toast e devolve o estado do notificador e as tags da Central de Notificações |
| `test_ponte_windows.py` | Leitura dos estados do Windows e montagem do pedido, com o PowerShell trocado por um falso |
| `sondar_grok.sh` | Um pedido de clipe ao Grok Build em modo headless, gravando a saída em fluxo, a sessão e o consumo |
| `resumir_grok.py` | Lê a saída em fluxo gravada e lista cada chamada de ferramenta com argumentos, status, arquivo e erro |
| `test_resumir_grok.py` | Resumo de uma rodada concluída e de uma recusada pelo provedor, com eventos reduzidos das rodadas reais |

## Repetir

```bash
cd qualificacao/integracoes
python3 -m unittest test_ponte_windows test_resumir_grok

# Estado das notificações do MyCut no Windows (só leitura)
python3 ponte_windows.py estado

# Toast disparado de um serviço de usuário, sem terminal nem WSL_INTEROP herdado
systemd-run --user --wait --collect --pipe --quiet -p WorkingDirectory=$PWD \
  /usr/bin/python3 ponte_windows.py notificar "MyCut" "Teste da ponte" teste-1

# Clipe no Grok: consome cota de vídeo. Só com autorização registrada do autor.
bash sondar_grok.sh .saida/grok-N <imagem-base.png>
python3 resumir_grok.py .saida/grok-N/stream.ndjson
```

O vídeo do Grok exige o ZDR da conta desligado (`/privacy`); com ele ligado a ferramenta recusa o pedido sem gerar.

Para remover o registro do AUMID: `Remove-Item 'HKCU:\Software\Classes\AppUserModelId\MyCut'` no PowerShell.
Não grave `Enabled` à mão em `HKCU:\...\Notifications\Settings\<AUMID>`: o Windows passa a guardar o estado
na própria base e a entrada só volta a funcionar pela tela de Configurações (ver o documento da prova).
