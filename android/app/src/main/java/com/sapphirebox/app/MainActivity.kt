package com.sapphirebox.app

import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.webkit.WebViewAssetLoader
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.ByteArrayInputStream
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var setupForm: LinearLayout
    private lateinit var serverStatus: TextView
    private lateinit var retryButton: Button
    private lateinit var assetLoader: WebViewAssetLoader

    private val pythonLock = Any()
    private var pythonBridge: PyObject? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

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
    }
}
