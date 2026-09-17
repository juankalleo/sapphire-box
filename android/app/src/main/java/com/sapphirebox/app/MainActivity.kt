package com.sapphirebox.app

import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var setupForm: LinearLayout
    private lateinit var serverStatus: TextView
    private lateinit var retryButton: Button

    @Volatile
    private var starting = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        setupForm = findViewById(R.id.setup_form)
        serverStatus = findViewById(R.id.server_status)
        retryButton = findViewById(R.id.connect_button)

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = object : WebViewClient() {
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
            startLocalServer()
        }

        startLocalServer()

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

    private fun startLocalServer() {
        if (starting) return
        starting = true
        showStartup(getString(R.string.server_help), isError = false, allowRetry = false)

        Thread {
            try {
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this@MainActivity))
                }

                val py = Python.getInstance()
                val bridge = py.getModule("sapphirebox_android")
                val url = bridge.callAttr(
                    "start",
                    filesDir.absolutePath,
                    cacheDir.absolutePath
                ).toString()

                runOnUiThread {
                    starting = false
                    loadLocalApp(url)
                }
            } catch (error: Throwable) {
                runOnUiThread {
                    starting = false
                    showStartup(
                        getString(R.string.server_error, error.message ?: error.javaClass.simpleName),
                        isError = true
                    )
                }
            }
        }.start()
    }

    private fun loadLocalApp(url: String) {
        setupForm.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl(url)
    }

    private fun showStartup(message: String, isError: Boolean, allowRetry: Boolean = true) {
        webView.visibility = View.GONE
        serverStatus.text = message
        serverStatus.setTextColor(Color.parseColor(if (isError) "#B42318" else "#6B7280"))
        retryButton.visibility = if (allowRetry) View.VISIBLE else View.GONE
        setupForm.visibility = View.VISIBLE
    }
}
