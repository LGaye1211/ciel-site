import UIKit
import WebKit

/// A full-bleed WKWebView pointed at the live site.
///
/// Loading the remote URL rather than a bundled copy is deliberate: every
/// scanner commit reaches the phone with no rebuild. Bundling would mean a new
/// .ipa and a fresh sideload every quarter, which is precisely the friction
/// that stops a quarterly review from happening.
final class ViewController: UIViewController {

    /// Point this at your GitHub Pages URL.
    private let siteURL = URL(string: "https://lgaye1211.github.io/ciel-site/sleeve.html")!

    private var webView: WKWebView!
    private let refresher = UIRefreshControl()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = Self.pageColour(for: traitCollection)

        let config = WKWebViewConfiguration()
        // The default persistent store keeps localStorage across launches, which
        // is where accepted positions and the theme choice live.
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = true

        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.isOpaque = false
        webView.backgroundColor = view.backgroundColor
        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)

        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
        ])

        refresher.addTarget(self, action: #selector(reload), for: .valueChanged)
        webView.scrollView.refreshControl = refresher

        load()
    }

    /// The page themes itself light or dark from the system setting, so a fixed
    /// light status bar would be invisible against the light theme.
    override var preferredStatusBarStyle: UIStatusBarStyle {
        traitCollection.userInterfaceStyle == .light ? .darkContent : .lightContent
    }

    override func traitCollectionDidChange(_ previous: UITraitCollection?) {
        super.traitCollectionDidChange(previous)
        if previous?.userInterfaceStyle != traitCollection.userInterfaceStyle {
            view.backgroundColor = Self.pageColour(for: traitCollection)
            webView.backgroundColor = view.backgroundColor
            setNeedsStatusBarAppearanceUpdate()
        }
    }

    private static func pageColour(for traits: UITraitCollection) -> UIColor {
        traits.userInterfaceStyle == .light
            ? UIColor(red: 0.918, green: 0.933, blue: 0.957, alpha: 1)   // --page light
            : UIColor(red: 0.027, green: 0.051, blue: 0.094, alpha: 1)   // --page dark
    }

    private func load() {
        webView.load(URLRequest(url: siteURL, cachePolicy: .reloadRevalidatingCacheData))
    }

    @objc private func reload() {
        load()
    }

    /// Shown when the site cannot be reached, so a dead connection explains
    /// itself instead of rendering Safari's error page inside a chromeless app.
    private func showOffline() {
        guard let path = Bundle.main.url(forResource: "Offline", withExtension: "html") else { return }
        webView.loadFileURL(path, allowingReadAccessTo: path.deletingLastPathComponent())
    }
}

extension ViewController: WKNavigationDelegate {
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        refresher.endRefreshing()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        refresher.endRefreshing()
        showOffline()
    }

    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        refresher.endRefreshing()
        showOffline()
    }

    /// Keep the app on its own site; send anything else (EDGAR filing links,
    /// citations) to Safari, where they belong.
    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow); return
        }
        if navigationAction.navigationType == .linkActivated,
           url.host != siteURL.host, url.isFileURL == false {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }
}
