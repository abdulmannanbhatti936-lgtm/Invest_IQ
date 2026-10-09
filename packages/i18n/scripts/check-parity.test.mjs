// Run: npm test -w @investiq/i18n — proves the parity check catches each kind of drift.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { checkParity } from './check-parity.mjs';

const en = { a: { greet: 'Hello {{name}}', bye: 'Bye' } };

test('identical structure passes', () => {
  assert.deepEqual(checkParity(en, { a: { greet: 'سلام {{name}}', bye: 'خدا حافظ' } }).errors, []);
});

test('missing, extra, empty, wrong type and placeholder drift all fail', () => {
  const { errors } = checkParity(
    { ...en, n: 'x' },
    { a: { greet: 'سلام {{user}}', bye: '  ' }, extra: 'اضافی', n: { nested: 'x' } },
  );
  const text = errors.join('\n');
  assert.match(text, /placeholders differ for a\.greet/);
  assert.match(text, /ur\.json a\.bye: empty value/);
  assert.match(text, /extra in ur\.json \(not in en\.json\): extra/);
  assert.match(text, /missing in ur\.json: n$/m);
  assert.match(text, /extra in ur\.json \(not in en\.json\): n\.nested/);
});

test('untranslated text is a warning, not an error', () => {
  const result = checkParity({ title: 'Portfolio' }, { title: 'Portfolio' });
  assert.deepEqual(result.errors, []);
  assert.equal(result.warnings.length, 1);
});
