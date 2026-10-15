// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { otherTheme, parseTheme } from './themeRules.ts';

test('dark is the default when nothing or something unknown is stored', () => {
  assert.equal(parseTheme(null), 'dark');
  assert.equal(parseTheme(undefined), 'dark');
  assert.equal(parseTheme(''), 'dark');
  assert.equal(parseTheme('sepia'), 'dark');
  assert.equal(parseTheme('dark'), 'dark');
});

test('a saved light choice is remembered', () => {
  assert.equal(parseTheme('light'), 'light');
});

test('the toggle switches to the other theme', () => {
  assert.equal(otherTheme('dark'), 'light');
  assert.equal(otherTheme('light'), 'dark');
});
