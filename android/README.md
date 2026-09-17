# Sapphire Box Android

Android APK v1.0.0 standalone para usar o Sapphire Box direto no celular.

## Como Funciona

O APK embute a interface web e o pacote Python do Sapphire Box via Chaquopy. Ao abrir, ele carrega a interface a partir dos assets internos do APK e chama a API por uma ponte nativa Android/Python, sem subir servidor local e sem depender de `127.0.0.1`.

Isso significa:

- não precisa de web publicado;
- não precisa de PC ligado na mesma rede;
- não fica preso em tela de "iniciando servidor local";
- busca, leitura, banco local e downloads rodam no aparelho;
- a biblioteca e os arquivos já baixados abrem offline;
- a mesma UI empacotada no desktop/web também é usada no Android.

## Usar o APK

1. Baixe `SapphireBox-Android-1.0.0.apk` na release.
2. Instale no Android.
3. Abra o app.
4. Use busca, leitura e downloads normalmente.

Os arquivos ficam no armazenamento interno do app Android. A permissão de internet serve para acessar as fontes/scrapers.

Compatibilidade esperada: Android 7.0+ (`minSdk 24`), com APK universal para `armeabi-v7a`, `arm64-v8a`, `x86` e `x86_64`.

## Build Local

Abra a pasta `android/` no Android Studio e rode o módulo `:app`.

Por linha de comando, com Gradle instalado:

```bash
gradle -p android :app:assembleDebug
```

Para build local fora do Android Studio, deixe JDK 17, Android SDK e Python 3.11 disponíveis no `PATH`.

O workflow `.github/workflows/release.yml` gera o APK de release automaticamente.

## Assinatura da Release (keystore persistente)

`release.yml` assina o APK com uma keystore guardada nos secrets do repositório, não gerada na hora — se ela mudasse a cada build, o Android trataria cada APK novo como um app diferente e recusaria instalar por cima do anterior sem antes desinstalar (perdendo a biblioteca baixada de quem já tinha o app).

Secrets necessários em Settings → Secrets and variables → Actions:

- `ANDROID_KEYSTORE_BASE64` — a keystore (`.keystore`/`.jks`) inteira, codificada em base64 (`base64 -i minha.keystore | pbcopy` no mac, cole o resultado como o valor do secret).
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

Sem esses 4 secrets configurados, o job `android-apk` falha de propósito (em vez de gerar uma keystore descartável silenciosamente).

**Gerando uma keystore nova** (só se ainda não existir uma, ou se a atual foi perdida — trocar a keystore depois de já ter builds publicadas exige que todo mundo desinstale o app antigo uma vez):

```bash
keytool -genkeypair \
  -keystore sapphirebox-release.keystore \
  -storepass "UMA_SENHA_FORTE" \
  -keypass "UMA_SENHA_FORTE" \
  -alias sapphirebox \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -dname "CN=Sapphire Box, OU=Release, O=Sapphire Box, L=Local, S=Local, C=BR"
```

Keystores modernas (PKCS12, o padrão do `keytool` atual) só suportam uma senha só pra tudo — `storepass` e `keypass` têm que ser iguais, ou o `keytool` ignora a diferença silenciosamente.

Guarde o arquivo `.keystore` gerado em um lugar seguro fora do repositório (gerenciador de senhas, backup privado) — **nunca commitar no git**. Perder essa keystore tem o mesmo efeito de trocá-la: ninguém consegue mais atualizar por cima do app já instalado.

## Detalhes Técnicos

- `com.chaquo.python` empacota o runtime Python e as dependências.
- `android/app/src/main/assets/web/` contém a interface que o WebView abre offline.
- `android/app/src/main/python/sapphirebox_android.py` executa as chamadas da API em processo, sem `uvicorn`.
- `SAPPHIREBOX_DATA_DIR` e `SAPPHIREBOX_CACHE_DIR` apontam para pastas internas do Android.
- `android/app/src/main/python/sapphirebox/` contém a cópia empacotada do app Python para o APK.
