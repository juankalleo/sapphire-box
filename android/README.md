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

## Detalhes Técnicos

- `com.chaquo.python` empacota o runtime Python e as dependências.
- `android/app/src/main/assets/web/` contém a interface que o WebView abre offline.
- `android/app/src/main/python/sapphirebox_android.py` executa as chamadas da API em processo, sem `uvicorn`.
- `SAPPHIREBOX_DATA_DIR` e `SAPPHIREBOX_CACHE_DIR` apontam para pastas internas do Android.
- `android/app/src/main/python/sapphirebox/` contém a cópia empacotada do app Python para o APK.
