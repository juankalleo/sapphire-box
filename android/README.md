# Sapphire Box Android

Android APK v1.0.0 standalone para usar o Sapphire Box direto no celular.

## Como Funciona

O APK embute o pacote Python do Sapphire Box via Chaquopy. Ao abrir, ele inicia o backend local no próprio Android e carrega a interface pelo WebView em `127.0.0.1`.

Isso significa:

- não precisa de web publicado;
- não precisa de PC ligado na mesma rede;
- busca, leitura, banco local e downloads rodam no aparelho;
- a mesma UI empacotada no desktop/web também é usada no Android.

## Usar o APK

1. Baixe `SapphireBox-Android-1.0.0.apk` na release.
2. Instale no Android.
3. Abra o app e aguarde a inicialização local.
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

## Detalhes Técnicos

- `com.chaquo.python` empacota o runtime Python e as dependências.
- `android/app/src/main/python/sapphirebox_android.py` sobe o servidor local em `127.0.0.1:8765`.
- `SAPPHIREBOX_DATA_DIR` e `SAPPHIREBOX_CACHE_DIR` apontam para pastas internas do Android.
- `android/app/src/main/python/sapphirebox/` contém a cópia empacotada do app Python para o APK.
