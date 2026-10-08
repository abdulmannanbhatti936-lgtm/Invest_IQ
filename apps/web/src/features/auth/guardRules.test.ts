// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  adminRedirect,
  guestRedirect,
  onboardingRedirect,
  protectedRouteRedirect,
  safeReturnPath,
} from './guardRules.ts';

const loggedOut = null;
const noProfile = { has_risk_profile: false, role: 'user' as const };
const withProfile = { has_risk_profile: true, role: 'user' as const };
const admin = { has_risk_profile: true, role: 'admin' as const };

test('protected routes: logged out -> /login, no profile -> /onboarding, profile -> allowed', () => {
  assert.equal(protectedRouteRedirect(loggedOut), '/login');
  assert.equal(protectedRouteRedirect(noProfile), '/onboarding');
  assert.equal(protectedRouteRedirect({ ...admin, has_risk_profile: false }), '/onboarding');
  assert.equal(protectedRouteRedirect(withProfile), null);
});

test('onboarding: open without a profile; with a profile only as a retake or to show the result', () => {
  const plain = { retake: false, showingResult: false };
  assert.equal(onboardingRedirect(loggedOut, plain), '/login');
  assert.equal(onboardingRedirect(noProfile, plain), null);
  assert.equal(onboardingRedirect(withProfile, plain), '/dashboard');
  assert.equal(onboardingRedirect(withProfile, { retake: true, showingResult: false }), null);
  // Just finished: the profile now exists but the result screen must stay visible
  assert.equal(onboardingRedirect(withProfile, { retake: false, showingResult: true }), null);
});

test('admin: only the admin role gets through', () => {
  assert.equal(adminRedirect(loggedOut), '/dashboard');
  assert.equal(adminRedirect(withProfile), '/dashboard');
  assert.equal(adminRedirect(admin), null);
});

test('login/register while logged in: back to the requested page if the profile is complete', () => {
  assert.equal(guestRedirect(loggedOut, '/stocks/SYS'), null);
  assert.equal(guestRedirect(withProfile, '/stocks/SYS?period=1y'), '/stocks/SYS?period=1y');
  assert.equal(guestRedirect(withProfile, undefined), '/dashboard');
  assert.equal(guestRedirect(noProfile, '/stocks/SYS'), '/onboarding');
});

test('return paths are limited to this app', () => {
  assert.equal(safeReturnPath('/portfolio'), '/portfolio');
  assert.equal(safeReturnPath('//evil.example.com'), null);
  assert.equal(safeReturnPath('https://evil.example.com'), null);
  assert.equal(safeReturnPath('/login'), null);
  assert.equal(safeReturnPath('/register?x=1'), null);
  assert.equal(safeReturnPath('/onboarding'), null);
  assert.equal(safeReturnPath('/loginhelp'), '/loginhelp');
  assert.equal(safeReturnPath(null), null);
});
