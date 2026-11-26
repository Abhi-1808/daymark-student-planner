import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

const _endpointKey = 'server_url';
const _configuredEndpoint = String.fromEnvironment('DAYMARK_URL');

Uri? parseEndpoint(String input) {
  final uri = Uri.tryParse(input.trim());
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment ||
      (uri.path.isNotEmpty && uri.path != '/')) {
    return null;
  }
  return Uri.parse(uri.origin).replace(path: '/');
}

bool isWorkspaceNavigation(Uri workspace, String url) {
  final target = Uri.tryParse(url);
  return target != null &&
      target.scheme == 'https' &&
      target.host.isNotEmpty &&
      target.userInfo.isEmpty &&
      target.origin == workspace.origin;
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final preferences = SharedPreferencesAsync();
  final saved = await preferences.getString(_endpointKey);
  runApp(
    DaymarkApp(
      endpoint:
          parseEndpoint(saved ?? '') ?? parseEndpoint(_configuredEndpoint),
      save: (value) => preferences.setString(_endpointKey, value.toString()),
    ),
  );
}

class DaymarkApp extends StatefulWidget {
  const DaymarkApp({super.key, required this.endpoint, required this.save});

  final Uri? endpoint;
  final Future<void> Function(Uri) save;

  @override
  State<DaymarkApp> createState() => _DaymarkAppState();
}

class _DaymarkAppState extends State<DaymarkApp> {
  late Uri? _endpoint = widget.endpoint;
  bool _editing = false;

  Future<void> _connect(Uri uri) async {
    await widget.save(uri);
    if (!mounted) return;
    setState(() {
      _endpoint = uri;
      _editing = false;
    });
  }

  ThemeData _theme(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: const Color(0xff234fce),
      brightness: brightness,
      surface: brightness == Brightness.dark
          ? const Color(0xff12161f)
          : const Color(0xffe9effa),
    );
    return ThemeData(
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final endpoint = _endpoint;
    return MaterialApp(
      title: 'Daymark',
      debugShowCheckedModeBanner: false,
      theme: _theme(Brightness.light),
      darkTheme: _theme(Brightness.dark),
      home: endpoint == null || _editing
          ? ConnectionScreen(
              initial: endpoint,
              onConnect: _connect,
              onCancel: endpoint == null
                  ? null
                  : () => setState(() => _editing = false),
            )
          : WorkspaceScreen(
              key: ValueKey(endpoint),
              endpoint: endpoint,
              changeServer: () => setState(() => _editing = true),
            ),
    );
  }
}

class ConnectionScreen extends StatefulWidget {
  const ConnectionScreen({
    super.key,
    this.initial,
    required this.onConnect,
    this.onCancel,
  });

  final Uri? initial;
  final Future<void> Function(Uri) onConnect;
  final VoidCallback? onCancel;

  @override
  State<ConnectionScreen> createState() => _ConnectionScreenState();
}

class _ConnectionScreenState extends State<ConnectionScreen> {
  final _form = GlobalKey<FormState>();
  late final _input = TextEditingController(text: widget.initial?.origin);
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.onConnect(parseEndpoint(_input.text)!);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not save the server address.');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Card.outlined(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Form(
                    key: _form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.calendar_today_outlined,
                          color: theme.colorScheme.primary,
                          size: 28,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'Connect to Daymark',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 22),
                        TextFormField(
                          controller: _input,
                          keyboardType: TextInputType.url,
                          textInputAction: TextInputAction.go,
                          autocorrect: false,
                          decoration: const InputDecoration(
                            labelText: 'Server address',
                            hintText: 'https://daymark.example.com',
                          ),
                          validator: (value) =>
                              parseEndpoint(value ?? '') == null
                              ? 'Enter an HTTPS server address.'
                              : null,
                          onFieldSubmitted: (_) => _submit(),
                        ),
                        if (_error != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 12),
                            child: Text(
                              _error!,
                              style: TextStyle(color: theme.colorScheme.error),
                            ),
                          ),
                        const SizedBox(height: 16),
                        FilledButton(
                          onPressed: _saving ? null : _submit,
                          child: Text(_saving ? 'Connecting…' : 'Connect'),
                        ),
                        if (widget.onCancel != null)
                          TextButton(
                            onPressed: _saving ? null : widget.onCancel,
                            child: const Text('Cancel'),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

enum _WorkspaceAction { reload, browser, server }

class WorkspaceScreen extends StatefulWidget {
  const WorkspaceScreen({
    super.key,
    required this.endpoint,
    required this.changeServer,
  });

  final Uri endpoint;
  final VoidCallback changeServer;

  @override
  State<WorkspaceScreen> createState() => _WorkspaceScreenState();
}

class _WorkspaceScreenState extends State<WorkspaceScreen> {
  late final WebViewController _controller;
  bool _loading = true;
  bool _failed = false;
  bool _hasHistory = false;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController();
    _start();
  }

  Future<void> _start() async {
    try {
      await _controller.setJavaScriptMode(JavaScriptMode.unrestricted);
      await _controller.setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (_) {
            if (!mounted) return;
            setState(() {
              _loading = true;
              _failed = false;
            });
          },
          onPageFinished: (_) async {
            await _updateHistory();
            if (mounted) setState(() => _loading = false);
          },
          onUrlChange: (_) => _updateHistory(),
          onWebResourceError: (error) {
            if (error.isForMainFrame != true || !mounted) return;
            _showFailure();
          },
          onNavigationRequest: (request) {
            if (!request.isMainFrame ||
                isWorkspaceNavigation(widget.endpoint, request.url)) {
              return NavigationDecision.navigate;
            }
            if (mounted) {
              setState(() => _loading = false);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: const Text(
                    'Use your browser to connect external accounts.',
                  ),
                  action: SnackBarAction(
                    label: 'Open Daymark',
                    onPressed: _openBrowser,
                  ),
                ),
              );
            }
            return NavigationDecision.prevent;
          },
        ),
      );
      await _controller.loadRequest(widget.endpoint);
    } catch (_) {
      if (mounted) _showFailure();
    }
  }

  void _showFailure() {
    setState(() {
      _loading = false;
      _failed = true;
    });
  }

  Future<void> _updateHistory() async {
    final history = await _controller.canGoBack();
    if (mounted && history != _hasHistory) {
      setState(() => _hasHistory = history);
    }
  }

  Future<void> _reload() async {
    setState(() {
      _failed = false;
      _loading = true;
    });
    try {
      final url = await _controller.currentUrl();
      if (url != null && isWorkspaceNavigation(widget.endpoint, url)) {
        await _controller.reload();
      } else {
        await _controller.loadRequest(widget.endpoint);
      }
    } catch (_) {
      if (mounted) _showFailure();
    }
  }

  Future<void> _openBrowser() async {
    try {
      if (await launchUrl(
        widget.endpoint,
        mode: LaunchMode.externalApplication,
      )) {
        return;
      }
    } catch (_) {
      // The platform can reject a launch when no compatible browser is installed.
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open a browser.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope<Object?>(
      canPop: !_hasHistory,
      onPopInvokedWithResult: (popped, _) async {
        if (!popped && _hasHistory) await _controller.goBack();
      },
      child: Scaffold(
        appBar: AppBar(
          toolbarHeight: 44,
          title: Text(
            widget.endpoint.host,
            style: Theme.of(context).textTheme.labelLarge,
            overflow: TextOverflow.ellipsis,
          ),
          actions: [
            PopupMenuButton<_WorkspaceAction>(
              tooltip: 'Workspace options',
              onSelected: (action) {
                switch (action) {
                  case _WorkspaceAction.reload:
                    _reload();
                  case _WorkspaceAction.browser:
                    _openBrowser();
                  case _WorkspaceAction.server:
                    widget.changeServer();
                }
              },
              itemBuilder: (_) => const [
                PopupMenuItem(
                  value: _WorkspaceAction.reload,
                  child: Text('Reload'),
                ),
                PopupMenuItem(
                  value: _WorkspaceAction.browser,
                  child: Text('Open in browser'),
                ),
                PopupMenuItem(
                  value: _WorkspaceAction.server,
                  child: Text('Change server'),
                ),
              ],
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: Stack(
            fit: StackFit.expand,
            children: [
              WebViewWidget(controller: _controller),
              if (_failed)
                ColoredBox(
                  color: Theme.of(context).scaffoldBackgroundColor,
                  child: Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text('Could not reach your Daymark server.'),
                          const SizedBox(height: 12),
                          FilledButton(
                            onPressed: _reload,
                            child: const Text('Retry'),
                          ),
                          TextButton(
                            onPressed: widget.changeServer,
                            child: const Text('Change server'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              if (_loading)
                const Align(
                  alignment: Alignment.topCenter,
                  child: LinearProgressIndicator(minHeight: 2),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
