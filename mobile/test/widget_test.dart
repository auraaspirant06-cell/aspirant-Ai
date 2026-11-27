import 'package:flutter_test/flutter_test.dart';
import 'package:aspirant_max/main.dart';

void main() {
  testWidgets('MAX companion renders core navigation destinations', (tester) async {
    await tester.pumpWidget(const MaxCompanionApp());
    expect(find.text('MAX Companion'), findsOneWidget);
    expect(find.text('Voice & Chat'), findsOneWidget);
    expect(find.text('Planner'), findsOneWidget);
    expect(find.text('AI Notes'), findsOneWidget);
  });
}
