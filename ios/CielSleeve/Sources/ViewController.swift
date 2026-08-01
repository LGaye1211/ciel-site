import UIKit
import WebKit

/// A full-bleed WKWebView pointed at the live site.
///
/// Loading the remote URL rather than a bundled copy is deliberate: every
/// scanner commit reaches the phone with no rebuild. Bundling would mean a new
/// .ipa and a fresh sideload every quarter, which is precisely the friction
/// that stops a quarterly review from happening.
final class ViewController: UIViewController {

    /// Every GitHub Pages URL the site may live at, current home first.
    ///
    /// A single hardcoded host would make a repository transfer fatal: Pages
    /// stops serving the old owner's URL the moment the repo moves, the app
    /// shows its offline page forever, and fixing it costs a rebuild and a
    /// second sideload. Sideloading is the expensive part, so the app asks each
    /// of these in turn and remembers whichever answered. Adding a row here is
    /// enough to survive the next move.
    ///
    /// Order matters only for launch latency - the resolver tries them in
    /// sequence - so the address serving the site today goes first and the
    /// planned one waits behind it. Once the transfer happens the second entry
    /// starts answering, the app switches to it on the next launch and pins it.
    private static let candidates: [URL] = [
        URL(string: "https://lgaye1211.github.io/ciel-site/sleeve.html")!,
        URL(string: "https://arthurgayecom.github.io/ciel-site/sleeve.html")!,
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
    /// Whichever candidate answered. Nothing loads until one has.
    private var siteURL: URL?

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

    /// Ask each candidate in turn who is home, then load the one that answered.
    ///
    /// The first version of this drove the walk through WKWebView itself:
    /// cancel the navigation on a 4xx and advance. That looked tidy and was
    /// quietly broken. Cancelling a response makes WebKit report the abandoned
    /// navigation as a *failure* - and not as NSURLErrorCancelled, which is what
    /// the guard checked for, but as WebKitErrorDomain 102, "frame load
    /// interrupted". So every recovery advanced twice: once deliberately, once
    /// from the phantom failure. With two candidates that ran off the end of the
    /// list and painted the offline page over a load that was already
    /// succeeding. The app shipped showing "No connection" against a site
    /// returning 200.
    ///
    /// Resolving with URLSession before handing anything to the web view has no
    /// such race. One request decides, then exactly one navigation happens, and
    /// the navigation delegate goes back to meaning what it says: a failure is a
    /// failure.
    private func load() {
        resolve(from: 0)
    }

    private func resolve(from position: Int) {
        guard position < order.count else {
            refresher.endRefreshing()
            showOffline()
            return
        }
        let candidate = order[position]
        var probe = URLRequest(url: candidate, cachePolicy: .reloadIgnoringLocalCacheData,
                               timeoutInterval: 12)
        // GET rather than HEAD: a static host that mishandles HEAD would take
        // the site down for no reason, and the page is a few tens of kilobytes.
        probe.httpMethod = "GET"

        URLSession.shared.dataTask(with: probe) { [weak self] _, response, _ in
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard (200..<400).contains(code) else {
                    self.resolve(from: position + 1)
                    return
                }
                self.siteURL = candidate
                UserDefaults.standard.set(candidate, forKey: Self.savedKey)
                self.webView.load(URLRequest(url: candidate,
                                             cachePolicy: .reloadRevalidatingCacheData))
            }
        }.resume()
    }

    @objc private func reload() {
        // Start the walk again from the top: a pull-to-refresh after a move
        // should find the new home rather than retry the one that just failed.
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

    /// By the time anything loads, a candidate has already answered, so a
    /// failure here is a genuine one - a dropped connection mid-load - and the
    /// offline page is the honest response to it. No advancing, no cancelling,
    /// nothing to race with the resolver.
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
