import 'package:daymark_mobile/main.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('only root HTTPS endpoints are accepted', () {
    expect(
      parseEndpoint(' https://example.net:8443 '),
      Uri.parse('https://example.net:8443/'),
    );
    for (final address in [
      'http://example.net',
      'https://user@example.net',
      'https://example.net/settings',
      'https://example.net/?token=value',
      'https://example.net/#today',
      '',
    ]) {
      expect(parseEndpoint(address), isNull, reason: address);
    }
  });

  test('embedded top-level navigation stays within the configured origin', () {
    final endpoint = Uri.parse('https://planner.example.net/');
    expect(
      isWorkspaceNavigation(endpoint, 'https://planner.example.net/#study'),
      isTrue,
    );
    expect(
      isWorkspaceNavigation(endpoint, 'https://planner.example.net.evil.test/'),
      isFalse,
    );
    expect(
      isWorkspaceNavigation(endpoint, 'https://planner.example.net:444/'),
      isFalse,
    );
    expect(
      isWorkspaceNavigation(endpoint, 'http://planner.example.net/'),
      isFalse,
    );
  });

  testWidgets('setup rejects invalid addresses and passes the verified one', (
    tester,
  ) async {
    Uri? connected;
    await tester.pumpWidget(
      MaterialApp(
        home: ConnectionScreen(onConnect: (uri) async => connected = uri),
      ),
    );
    final input = find.byType(TextFormField);
    await tester.enterText(input, 'http://planner.example.net');
    await tester.tap(find.text('Connect'));
    await tester.pump();
    expect(find.text('Enter an HTTPS server address.'), findsOneWidget);
    expect(connected, isNull);
    await tester.enterText(input, 'https://planner.example.net');
    await tester.tap(find.text('Connect'));
    await tester.pump();
    expect(connected.toString(), 'https://planner.example.net/');
  });
}
