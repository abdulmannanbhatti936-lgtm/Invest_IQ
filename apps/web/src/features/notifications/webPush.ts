import { notificationsApi } from '@investiq/api-client';

// Firebase web config (public values, from the Firebase console; see apps/web/.env.example).
// The service account key never comes near the browser: only the API holds it.
const env = import.meta.env;
const FIREBASE = {
  apiKey: env.VITE_FIREBASE_API_KEY as string | undefined,
  projectId: env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID as string | undefined,
  appId: env.VITE_FIREBASE_APP_ID as string | undefined,
};
const VAPID_KEY = env.VITE_FIREBASE_VAPID_KEY as string | undefined;
const WORKER_URL = '/push-sw.js';
const DEVICE_KEY = 'investiq.push_device_id';

export type PushProblem = 'not_configured' | 'unsupported' | 'blocked' | 'failed';

export class WebPushError extends Error {
  readonly problem: PushProblem;

  constructor(problem: PushProblem) {
    super(problem);
    this.problem = problem;
  }
}

export const webPushConfigured = (): boolean =>
  Boolean(FIREBASE.apiKey && FIREBASE.projectId && FIREBASE.messagingSenderId && FIREBASE.appId) &&
  Boolean(VAPID_KEY);

const storedDevice = (): string | null => {
  try {
    return localStorage.getItem(DEVICE_KEY);
  } catch {
    return null;
  }
};

const storeDevice = (id: string | null) => {
  try {
    if (id) localStorage.setItem(DEVICE_KEY, id);
    else localStorage.removeItem(DEVICE_KEY);
  } catch {
    // Private windows can refuse storage; the server still holds the device
  }
};

/** Whether this browser is the one registered for push (the setting itself is per account). */
export const thisBrowserRegistered = (): boolean => storedDevice() !== null;

const messaging = async () => {
  const [{ getApps, initializeApp }, firebaseMessaging] = await Promise.all([
    import('firebase/app'),
    import('firebase/messaging'),
  ]);
  if (!(await firebaseMessaging.isSupported())) throw new WebPushError('unsupported');
  const app = getApps()[0] ?? initializeApp(FIREBASE);
  return { firebaseMessaging, instance: firebaseMessaging.getMessaging(app) };
};

/** Asks for permission, registers the service worker and this browser's FCM token. */
export const enableWebPush = async (): Promise<void> => {
  if (!webPushConfigured()) throw new WebPushError('not_configured');
  if (!('Notification' in window) || !('serviceWorker' in navigator)) {
    throw new WebPushError('unsupported');
  }
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new WebPushError('blocked');
  try {
    const { firebaseMessaging, instance } = await messaging();
    const registration = await navigator.serviceWorker.register(WORKER_URL);
    await navigator.serviceWorker.ready;
    const token = await firebaseMessaging.getToken(instance, {
      vapidKey: VAPID_KEY,
      serviceWorkerRegistration: registration,
    });
    const device = await notificationsApi.registerDevice(token);
    storeDevice(device.id);
  } catch (error) {
    if (error instanceof WebPushError) throw error;
    throw new WebPushError('failed');
  }
};

/** Forgets this browser's token here and on the server; the in-app list is unaffected. */
export const disableWebPush = async (): Promise<void> => {
  const deviceId = storedDevice();
  storeDevice(null);
  if (webPushConfigured()) {
    try {
      const { firebaseMessaging, instance } = await messaging();
      await firebaseMessaging.deleteToken(instance);
    } catch {
      // The token may already be gone; the server copy is removed below either way
    }
  }
  if (deviceId) {
    try {
      await notificationsApi.removeDevice(deviceId);
    } catch {
      // Already removed (404) or moved to another account: nothing left to do here
    }
  }
};
