package io.github.zeanuri.orduenliturgia;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.widget.LinearLayout;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;
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
    /** Android 13+: «Atrás» vuelve en la web mientras haya adónde; si no, lo maneja el sistema. */
    private OnBackInvokedCallback atrasWeb;
    private boolean atrasRegistrado;

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        web = new WebView(this);
        setContentView(montarPantalla(web));
        if (Build.VERSION.SDK_INT >= 33) {
            atrasWeb = () -> web.goBack();
        }
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
            public void doUpdateVisitedHistory(WebView v, String url, boolean recarga) {
                actualizarAtras();
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
            actualizarAtras();
        }
    }

    /**
     * Desde Android 15 la app ocupa también la franja de la barra de estado y la
     * de navegación (no se puede desactivar al apuntar a Android 16). Se deja
     * arriba una franja del color de antes y la web empieza debajo.
     */
    private View montarPantalla(WebView w) {
        LinearLayout raiz = new LinearLayout(this);
        raiz.setOrientation(LinearLayout.VERTICAL);
        raiz.setBackgroundColor(Color.parseColor("#F6F4F1"));
        View franja = new View(this);
        franja.setBackgroundColor(Color.parseColor("#3D4458"));
        raiz.addView(franja, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0));
        raiz.addView(w, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));
        if (Build.VERSION.SDK_INT >= 35) {
            raiz.setOnApplyWindowInsetsListener((v, ins) -> {
                android.graphics.Insets b = ins.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                franja.getLayoutParams().height = b.top;
                franja.requestLayout();
                v.setPadding(b.left, 0, b.right, b.bottom);
                return WindowInsets.CONSUMED;
            });
        }
        return raiz;
    }

    private void actualizarAtras() {
        if (Build.VERSION.SDK_INT < 33) return;
        boolean hace = web.canGoBack();
        if (hace == atrasRegistrado) return;
        OnBackInvokedDispatcher d = getOnBackInvokedDispatcher();
        if (hace) {
            d.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, atrasWeb);
        } else {
            d.unregisterOnBackInvokedCallback(atrasWeb);
        }
        atrasRegistrado = hace;
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

    /** Hasta Android 12; desde el 13, actualizarAtras(). */
    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
