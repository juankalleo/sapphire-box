package com.sapphirebox.app

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.DocumentsContract
import android.provider.Settings
import android.util.Base64
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.JsPromptResult
import android.webkit.JsResult
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.webkit.WebViewAssetLoader
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.ByteArrayInputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var setupForm: LinearLayout
    private lateinit var serverStatus: TextView
    private lateinit var retryButton: Button
    private lateinit var assetLoader: WebViewAssetLoader

    private val pythonLock = Any()
    private var pythonBridge: PyObject? = null

    // Folder-picker flow (Storage Access Framework, gated behind "all files
    // access" so the resolved path is a real filesystem path Python can
    // write into directly — see resolvePickedFolder below).
    private lateinit var openTreeLauncher: ActivityResultLauncher<Uri?>
    private lateinit var allFilesAccessLauncher: ActivityResultLauncher<Intent>
    private lateinit var legacyStoragePermissionLauncher: ActivityResultLauncher<String>
    private var pendingFolderPickAfterPermission = false

    // In-app update flow: download the new APK, then hand it to the system
    // installer — still needs a final human tap on "Instalar" (Android
    // never lets a non-system app install silently), but skips the
    // "open browser, find the file, remember to come back" detour.
    private lateinit var installSourceLauncher: ActivityResultLauncher<Intent>
    private var pendingUpdateUrl: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        openTreeLauncher = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri == null) {
                notifyFolderPickFailed()
                return@registerForActivityResult
            }
            val resolved = resolvePickedFolder(uri)
            if (resolved != null) notifyFolderPicked(resolved) else notifyFolderPickFailed()
        }
        allFilesAccessLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
            if (!pendingFolderPickAfterPermission) return@registerForActivityResult
            pendingFolderPickAfterPermission = false
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R || Environment.isExternalStorageManager()) {
                openTreeLauncher.launch(null)
            } else {
                notifyFolderPickFailed()
            }
        }
        legacyStoragePermissionLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (!pendingFolderPickAfterPermission) return@registerForActivityResult
            pendingFolderPickAfterPermission = false
            if (granted) openTreeLauncher.launch(null) else notifyFolderPickFailed()
        }
        installSourceLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
            val url = pendingUpdateUrl
            pendingUpdateUrl = null
            if (url == null) return@registerForActivityResult
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || packageManager.canRequestPackageInstalls()) {
                startApkDownload(url)
            } else {
                notifyUpdateError("Permissão pra instalar não foi concedida.")
            }
        }

        webView = findViewById(R.id.webview)
        setupForm = findViewById(R.id.setup_form)
        serverStatus = findViewById(R.id.server_status)
        retryButton = findViewById(R.id.connect_button)

        assetLoader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.addJavascriptInterface(AndroidApiBridge(), "SapphireBoxAndroid")
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest
            ): WebResourceResponse? {
                if (isLocalApiRequest(request.url)) {
                    return handleApiResource(request)
                }
                return assetLoader.shouldInterceptRequest(request.url)
            }

            // A plain in-app link (e.g. the "baixar atualização" link to the
            // GitHub releases page) would otherwise either get silently
            // dropped or navigate the WebView itself away from the app's
            // own UI — there's no multi-window/onCreateWindow handling set
            // up for target="_blank" to open a real new tab. Anything that
            // isn't our own bundled page goes to the system browser instead.
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                if (uri.host == "appassets.androidplatform.net") return false
                if (uri.scheme != "http" && uri.scheme != "https") return false
                return try {
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                    true
                } catch (_: ActivityNotFoundException) {
                    false
                }
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                if (request.isForMainFrame) {
                    showStartup(
                        getString(
                            R.string.server_error,
                            error.description?.toString() ?: "falha ao carregar a interface"
                        ),
                        isError = true
                    )
                }
            }
        }
        // The web UI leans on plain window.confirm()/alert()/prompt() for
        // delete confirmations and error messages (same code runs in a
        // desktop browser too). A WebView shows none of that without a
        // WebChromeClient — it just auto-cancels the dialog and moves on,
        // which is why e.g. the "esse quadrinho vem como arquivo único...
        // continuar?" confirm() before a comic download silently returned
        // false and the download never started.
        webView.webChromeClient = object : WebChromeClient() {
            override fun onJsAlert(view: WebView, url: String, message: String, result: JsResult): Boolean {
                AlertDialog.Builder(this@MainActivity)
                    .setMessage(message)
                    .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm() }
                    .setOnCancelListener { result.confirm() }
                    .setCancelable(false)
                    .show()
                return true
            }

            override fun onJsConfirm(view: WebView, url: String, message: String, result: JsResult): Boolean {
                AlertDialog.Builder(this@MainActivity)
                    .setMessage(message)
                    .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm() }
                    .setNegativeButton(android.R.string.cancel) { _, _ -> result.cancel() }
                    .setOnCancelListener { result.cancel() }
                    .setCancelable(false)
                    .show()
                return true
            }

            override fun onJsPrompt(
                view: WebView,
                url: String,
                message: String,
                defaultValue: String?,
                result: JsPromptResult
            ): Boolean {
                val input = EditText(this@MainActivity).apply { setText(defaultValue) }
                AlertDialog.Builder(this@MainActivity)
                    .setMessage(message)
                    .setView(input)
                    .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm(input.text.toString()) }
                    .setNegativeButton(android.R.string.cancel) { _, _ -> result.cancel() }
                    .setOnCancelListener { result.cancel() }
                    .setCancelable(false)
                    .show()
                return true
            }
        }

        retryButton.setOnClickListener {
            loadBundledApp()
        }

        loadBundledApp()
        warmPythonBridge()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.visibility == View.VISIBLE && webView.canGoBack()) {
                    webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })
    }

    private fun loadBundledApp() {
        setupForm.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl("https://appassets.androidplatform.net/assets/web/index.html")
    }

    private fun warmPythonBridge() {
        Thread {
            try {
                synchronized(pythonLock) {
                    ensurePythonBridgeLocked()
                }
            } catch (_: Throwable) {
                // The web UI will surface API errors if Python cannot initialize.
            }
        }.start()
    }

    private fun isLocalApiRequest(uri: Uri): Boolean {
        return uri.host == "appassets.androidplatform.net" && (uri.path ?: "").startsWith("/api/")
    }

    private fun pathWithQuery(uri: Uri): String {
        val path = uri.encodedPath ?: "/"
        val query = uri.encodedQuery
        return if (query.isNullOrBlank()) path else "$path?$query"
    }

    private fun ensurePythonBridgeLocked(): PyObject {
        val existing = pythonBridge
        if (existing != null) return existing

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this@MainActivity))
        }
        val bridge = Python.getInstance().getModule("sapphirebox_android")
        pythonBridge = bridge
        return bridge
    }

    private fun bridgeRequest(payload: JSONObject): JSONObject {
        synchronized(pythonLock) {
            val bridge = ensurePythonBridgeLocked()
            val raw = bridge.callAttr(
                "handle",
                filesDir.absolutePath,
                cacheDir.absolutePath,
                payload.toString()
            ).toString()
            return JSONObject(raw)
        }
    }

    private fun handleApiResource(request: WebResourceRequest): WebResourceResponse {
        return try {
            val payload = JSONObject()
                .put("method", request.method ?: "GET")
                .put("url", pathWithQuery(request.url))
                .put("body", JSONObject.NULL)
            responseFromBridge(bridgeRequest(payload))
        } catch (error: Throwable) {
            responseFromBridge(errorResponse(error))
        }
    }

    private fun responseFromBridge(response: JSONObject): WebResourceResponse {
        val responseHeaders = response.optJSONObject("headers")
        val headers = linkedMapOf("Access-Control-Allow-Origin" to "*")
        var contentType = "application/json; charset=utf-8"

        if (responseHeaders != null) {
            val keys = responseHeaders.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val value = responseHeaders.optString(key)
                if (value.isNotBlank()) headers[key] = value
            }
            contentType = responseHeaders.optString("content-type", contentType)
        }

        val mediaType = contentType.substringBefore(";").trim().ifBlank { "application/octet-stream" }
        val encoding = responseEncoding(contentType, mediaType)
        val body = if (response.has("bodyBase64")) {
            Base64.decode(response.getString("bodyBase64"), Base64.DEFAULT)
        } else {
            response.optString("body", "").toByteArray(Charsets.UTF_8)
        }

        val status = response.optInt("status", 200).coerceIn(100, 599)
        val reason = response.optString("statusText", defaultReason(status)).ifBlank {
            defaultReason(status)
        }
        return WebResourceResponse(
            mediaType,
            encoding,
            status,
            reason,
            headers,
            ByteArrayInputStream(body)
        )
    }

    private fun responseEncoding(contentType: String, mediaType: String): String? {
        val charset = contentType
            .split(";")
            .map { it.trim() }
            .firstOrNull { it.startsWith("charset=", ignoreCase = true) }
            ?.substringAfter("=")
            ?.trim()
        if (!charset.isNullOrBlank()) return charset
        if (mediaType == "application/json" || mediaType.startsWith("text/")) return "utf-8"
        return null
    }

    private fun defaultReason(status: Int): String {
        return if (status >= 400) "Error" else "OK"
    }

    private fun errorResponse(error: Throwable): JSONObject {
        val body = JSONObject()
            .put("detail", error.message ?: error.javaClass.simpleName)
        return JSONObject()
            .put("status", 500)
            .put("statusText", "Android bridge error")
            .put("headers", JSONObject().put("content-type", "application/json; charset=utf-8"))
            .put("body", body.toString())
    }

    private fun beginFolderPick() {
        when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.R -> {
                if (Environment.isExternalStorageManager()) {
                    openTreeLauncher.launch(null)
                } else {
                    pendingFolderPickAfterPermission = true
                    val perAppIntent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                        data = Uri.parse("package:$packageName")
                    }
                    try {
                        allFilesAccessLauncher.launch(perAppIntent)
                    } catch (_: ActivityNotFoundException) {
                        // Some OEM ROMs don't ship the per-app screen — fall
                        // back to the general "all files access" settings list.
                        try {
                            allFilesAccessLauncher.launch(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
                        } catch (_: ActivityNotFoundException) {
                            pendingFolderPickAfterPermission = false
                            notifyFolderPickFailed()
                        }
                    }
                }
            }
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q -> {
                // Android 10: MANAGE_EXTERNAL_STORAGE doesn't exist yet and
                // this app's targetSdk makes it a full scoped-storage app on
                // this one OS version, so writes outside the app's own
                // directories may still fail here — resolvePickedFolder's
                // caller handles that the same as any other failure.
                openTreeLauncher.launch(null)
            }
            else -> {
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED) {
                    openTreeLauncher.launch(null)
                } else {
                    pendingFolderPickAfterPermission = true
                    legacyStoragePermissionLauncher.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                }
            }
        }
    }

    /** Resolves a SAF tree Uri to a plain filesystem path. Only works for
     * the primary storage volume — layout for SD cards and other secondary
     * volumes isn't standardized across devices, so those are left
     * unsupported (caller falls back to the manual path field) rather than
     * guessing a path that might not exist. */
    private fun resolvePickedFolder(treeUri: Uri): String? {
        try {
            contentResolver.takePersistableUriPermission(
                treeUri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
        } catch (_: SecurityException) {
            // Not fatal on its own — still try to use the resolved path below.
        }

        val docId = try {
            DocumentsContract.getTreeDocumentId(treeUri)
        } catch (_: Exception) {
            return null
        }
        val split = docId.split(":", limit = 2)
        if (split.size != 2 || !split[0].equals("primary", ignoreCase = true)) return null

        val root = Environment.getExternalStorageDirectory()
        val relativePath = split[1]
        val folder = if (relativePath.isBlank()) root else File(root, relativePath)
        return folder.absolutePath
    }

    private fun notifyFolderPicked(path: String) {
        val escaped = JSONObject.quote(path)
        webView.post {
            webView.evaluateJavascript("window.onSapphireBoxFolderPicked && window.onSapphireBoxFolderPicked($escaped)", null)
        }
    }

    private fun notifyFolderPickFailed() {
        webView.post {
            webView.evaluateJavascript("window.onSapphireBoxFolderPickFailed && window.onSapphireBoxFolderPickFailed()", null)
        }
    }

    private fun beginUpdateDownload(url: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !packageManager.canRequestPackageInstalls()) {
            pendingUpdateUrl = url
            val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                data = Uri.parse("package:$packageName")
            }
            try {
                installSourceLauncher.launch(intent)
            } catch (_: ActivityNotFoundException) {
                pendingUpdateUrl = null
                notifyUpdateError("Não achei a tela de permissão de instalação desse Android.")
            }
            return
        }
        startApkDownload(url)
    }

    private fun startApkDownload(url: String) {
        Thread {
            var connection: HttpURLConnection? = null
            try {
                val apkFile = File(cacheDir, "update.apk")
                connection = (URL(url).openConnection() as HttpURLConnection).apply {
                    instanceFollowRedirects = true
                    connectTimeout = 20_000
                    readTimeout = 20_000
                    connect()
                }
                if (connection.responseCode !in 200..299) {
                    notifyUpdateError("O servidor respondeu ${connection.responseCode} ao baixar o APK.")
                    return@Thread
                }
                val total = connection.contentLengthLong
                var downloaded = 0L
                var lastReportedPct = -1
                connection.inputStream.use { input ->
                    apkFile.outputStream().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val read = input.read(buffer)
                            if (read <= 0) break
                            output.write(buffer, 0, read)
                            downloaded += read
                            if (total > 0) {
                                val pct = ((downloaded * 100) / total).toInt()
                                if (pct != lastReportedPct) {
                                    lastReportedPct = pct
                                    notifyUpdateProgress(pct)
                                }
                            }
                        }
                    }
                }
                installApk(apkFile)
            } catch (error: Exception) {
                notifyUpdateError(error.message ?: error.javaClass.simpleName)
            } finally {
                connection?.disconnect()
            }
        }.start()
    }

    private fun installApk(file: File) {
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        runOnUiThread {
            try {
                startActivity(intent)
            } catch (_: ActivityNotFoundException) {
                notifyUpdateError("Não achei um instalador de pacotes nesse Android.")
            }
        }
    }

    private fun notifyUpdateProgress(pct: Int) {
        webView.post {
            webView.evaluateJavascript("window.onSapphireBoxUpdateProgress && window.onSapphireBoxUpdateProgress($pct)", null)
        }
    }

    private fun notifyUpdateError(message: String) {
        val escaped = JSONObject.quote(message)
        webView.post {
            webView.evaluateJavascript("window.onSapphireBoxUpdateError && window.onSapphireBoxUpdateError($escaped)", null)
        }
    }

    private fun showStartup(message: String, isError: Boolean, allowRetry: Boolean = true) {
        webView.visibility = View.GONE
        serverStatus.text = message
        serverStatus.setTextColor(Color.parseColor(if (isError) "#B42318" else "#6B7280"))
        retryButton.visibility = if (allowRetry) View.VISIBLE else View.GONE
        setupForm.visibility = View.VISIBLE
    }

    inner class AndroidApiBridge {
        @JavascriptInterface
        fun request(payloadJson: String): String {
            return try {
                bridgeRequest(JSONObject(payloadJson)).toString()
            } catch (error: Throwable) {
                errorResponse(error).toString()
            }
        }

        @JavascriptInterface
        fun hasFolderPicker(): Boolean = true

        // @JavascriptInterface methods run on a background WebView thread;
        // the picker launches an Activity/Intent, which must happen on the
        // main thread.
        @JavascriptInterface
        fun pickFolder() {
            runOnUiThread { beginFolderPick() }
        }

        @JavascriptInterface
        fun hasAutoUpdate(): Boolean = true

        @JavascriptInterface
        fun downloadAndInstallUpdate(apkUrl: String) {
            runOnUiThread { beginUpdateDownload(apkUrl) }
        }
    }
}
