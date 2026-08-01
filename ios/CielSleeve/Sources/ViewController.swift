import UIKit
import WebKit

/// A full-bleed WKWebView pointed at the live site.
///
/// Loading the remote URL rather than a bundled copy is deliberate: every
/// scanner commit reaches the phone with no rebuild. Bundling would mean a new
/// .ipa and a fresh sideload every quarter, which is precisely the friction
/// that stops a quarterly review from happening.
final class ViewController: UIViewController {

    /// Every GitHub Pages URL the site has lived at, newest first.
    ///
    /// A single hardcoded host would make a repository transfer fatal: Pages
    /// stops serving the old owner's URL the moment the repo moves, the app
    /// shows its offline page forever, and fixing it costs a rebuild and a
    /// second sideload. Sideloading is the expensive part, so the app walks
    /// this list instead and remembers whichever host answered. Adding a row
    /// here is enough to survive the next move.
    private static let candidates: [URL] = [
        URL(string: "https://arthurgayecom.github.io/ciel-site/sleeve.html")!,
        URL(string: "https://lgaye1211.github.io/ciel-site/sleeve.html")!,
    ]
    private static let savedKey = "ciel.siteURL"

    /// The remembered host is tried first; the rest stay behind it as fallbacks,
    /// so a site that moves back still recovers on its own.
    private lazy var order: [URL] = {
        var list = Self.candidates
        if let saved = UserDefaults.standard.url(forKey: Self.savedKey),
           let found = list.firstIndex(of: saved) {
            list.remove(at: found)
            list.insert(saved, at: 0)
        }
        return list
    }()
    private var index = 0
    private var siteURL: URL { order[min(index, order.count - 1)] }

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
        // Start the walk again from the top: a pull-to-refresh after a move
        // should find the new home rather than retry the one that just failed.
        index = 0
        load()
    }

    /// Move to the next candidate, or give up and explain.
    private func advance() {
        index += 1
        if index < order.count {
            load()
        } else {
            index = 0
            showOffline()
        }
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
        handleFailure(error)
    }

    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        handleFailure(error)
    }

    /// A cancellation is always one of ours: cancelling a 404 below makes WebKit
    /// report the abandoned navigation back here as a failure. Advancing on it
    /// would step past the candidate just moved to and blank the app on the
    /// exact case this whole mechanism exists to handle.
    private func handleFailure(_ error: Error) {
        refresher.endRefreshing()
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        advance()
    }

    /// A moved site does not fail the navigation - GitHub Pages answers a dead
    /// URL with its own 404 page, which loads perfectly well and would sit there
    /// looking like the app was broken. So the status code decides, not the
    /// absence of an error.
    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationResponse: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        guard navigationResponse.isForMainFrame,
              let response = navigationResponse.response as? HTTPURLResponse else {
            decisionHandler(.allow); return
        }
        if response.statusCode >= 400 {
            decisionHandler(.cancel)
            advance()
            return
        }
        UserDefaults.standard.set(siteURL, forKey: Self.savedKey)
        decisionHandler(.allow)
    }

    /// Keep the app on its own site; send anything else (EDGAR filing links,
    /// citations) to Safari, where they belong. Every candidate host counts as
    /// "its own site", or a link tapped after a move would bounce out.
    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow); return
        }
        let ours = Set(Self.candidates.compactMap { $0.host })
        if navigationAction.navigationType == .linkActivated,
           url.isFileURL == false,
           url.host.map({ ours.contains($0) }) != true {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }
}
