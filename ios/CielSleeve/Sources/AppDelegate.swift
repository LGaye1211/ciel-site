import UIKit

/// Scene-based lifecycle (iOS 13+). The window is created in SceneDelegate.
///
/// Do not add a `window` property here and expect it to be used: when a
/// UIApplicationSceneManifest is present, UIKit drives the UI through scenes
/// and silently ignores AppDelegate.window, which shows up as a black screen
/// on launch rather than as a build error.
@main
final class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions:
                     [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        return true
    }

    func application(_ application: UIApplication,
                     configurationForConnecting connectingSceneSession: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let config = UISceneConfiguration(name: "Default Configuration",
                                          sessionRole: connectingSceneSession.role)
        config.delegateClass = SceneDelegate.self
        return config
    }
}
