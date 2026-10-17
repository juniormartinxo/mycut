# Lado Windows da ponte de notificações (MYC-13). Recebe o pedido em JSON base64 e devolve JSON.
param(
  [Parameter(Mandatory)][ValidateSet('estado', 'enviar')][string]$Acao,
  [Parameter(Mandatory)][string]$Pedido
)
$ErrorActionPreference = 'Stop'
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime]

$dados = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Pedido)) | ConvertFrom-Json
$gerenciador = [Windows.UI.Notifications.ToastNotificationManager]

function Ler-Estado($aumid) {
  $notificador = $gerenciador::CreateToastNotifier($aumid)
  # Antes do primeiro toast o Windows não conhece o AUMID e Setting falha com 0x80070490.
  try { $setting = [string]$notificador.get_Setting() } catch { $setting = $null }
  $push = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications' -ErrorAction SilentlyContinue
  $historico = @($gerenciador::History.GetHistory($aumid) | ForEach-Object { $_.Tag })
  [pscustomobject]@{ setting = $setting; toastsGlobais = $push.ToastEnabled; historico = $historico }
}

if ($Acao -eq 'enviar') {
  # Registro do AUMID sem atalho no Menu Iniciar: o nome aparece no toast e em Configurações > Notificações.
  $chave = "HKCU:\Software\Classes\AppUserModelId\$($dados.aumid)"
  if (-not (Test-Path $chave)) { New-Item -Path $chave -Force | Out-Null }
  New-ItemProperty -Path $chave -Name DisplayName -Value $dados.nome -PropertyType String -Force | Out-Null

  $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
  $xml.LoadXml($dados.xml)
  $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
  $toast.Tag = $dados.tag
  $toast.Group = $dados.grupo
  $gerenciador::CreateToastNotifier($dados.aumid).Show($toast)
  # Show() não informa bloqueio; a entrega é conferida no histórico da Central de Notificações.
  Start-Sleep -Milliseconds 800
}

Ler-Estado $dados.aumid | ConvertTo-Json -Compress
