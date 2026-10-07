import 'package:flutter_test/flutter_test.dart';
import '../../lib/foo_repository.dart';

void main() {
  group('FooRepository', () {
    late FooRepository repo;

    setUp(() {
      repo = FooRepository();
    });

    test('inserts row', () async {
      await repo.insert(Foo());
      expect(repo.count, 1);
    });

    test("returns null on missing", () {
      expect(repo.find('nope'), isNull);
    });
  });

  group('edge cases', () {
    testWidgets('renders a spinner while loading', (tester) async {
      await tester.pumpWidget(const FooView());
    });
  });
}
