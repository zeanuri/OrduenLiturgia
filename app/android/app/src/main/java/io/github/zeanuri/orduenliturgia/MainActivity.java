package io.github.zeanuri.orduenliturgia;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.WebViewAssetLoader;

/**
 * La app es la web publicada en GitHub Pages: cada cambio que se publica llega
 * solo, sin instalar un APK nuevo, y la propia web se guarda para abrirse sin
 * conexión. Si falla la carga (primer arranque sin red), se abre la copia que
 * el APK lleva dentro. Los enlaces a otros sitios se abren en el navegador.
 */
public class MainActivity extends Activity {
    private static final String PUBLICADA = "https://zeanuri.github.io/OrduenLiturgia/app/";
    private static final String HOST_COPIA = "appassets.androidplatform.net";
    private static final String COPIA = "https://" + HOST_COPIA + "/assets/index.html";
    private WebView web;

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        web = new WebView(this);
        setContentView(web);
        final WebViewAssetLoader assets = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                return assets.shouldInterceptRequest(r.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (HOST_COPIA.equals(u.getHost()) || u.toString().startsWith(PUBLICADA)) {
                    return false;
                }
                startActivity(new Intent(Intent.ACTION_VIEW, u));
                return true;
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                abrirCopiaSiFalla(v, r);
            }

            @Override
            public void onReceivedHttpError(WebView v, WebResourceRequest r, WebResourceResponse e) {
                abrirCopiaSiFalla(v, r);
            }
        });
        if (estado == null) {
            web.loadUrl(PUBLICADA);
        } else {
            web.restoreState(estado);
        }
    }

    /** Solo cuando lo que falla es la página misma (no una imagen o un dato). */
    private void abrirCopiaSiFalla(WebView v, WebResourceRequest r) {
        if (r.isForMainFrame() && r.getUrl().toString().startsWith(PUBLICADA)) {
            v.loadUrl(COPIA);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle estado) {
        super.onSaveInstanceState(estado);
        web.saveState(estado);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
