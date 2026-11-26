# Daymark for Android

The Flutter client opens your Daymark workspace in an embedded Android WebView. It shares the Tailwind web interface and your server's calendar, tasks, and study data. The browser interface provides System, Light, and Dark modes. Use the moon or sun button to switch modes.

## Run on Android

Install Flutter 3.50.1 or a compatible newer release and the Android toolchain. Start a Daymark backend with a reachable HTTPS address and a workspace password. See [private phone access](../docs/setup.md#private-phone-access) for an example.

From this directory, run:

```bash
flutter pub get
flutter analyze
flutter test
flutter run
```

Enter the base HTTPS address on the connection screen. The server address is saved on the device. You can also set an initial address in the build:

```bash
flutter run --dart-define=DAYMARK_URL=https://planner.example.net
```

Use **Workspace options → Open in browser** for external account consent, file imports and downloads, or browser notifications. This opens the same workspace and may require a fresh sign-in in the browser.

For a local test APK, use `flutter build apk --debug`. A store release requires your own release signing configuration.
