import { getApp, getApps, initializeApp } from "firebase/app";
import { type Auth, connectAuthEmulator, getAuth } from "firebase/auth";

let auth: Auth | null = null;

/** Firebase Authentication, configured from NEXT_PUBLIC_FIREBASE_* (the web config: not secrets). Throws a readable error if it is missing. */
export function firebaseAuth(): Auth {
  if (auth) return auth;
  // Next only inlines NEXT_PUBLIC_* when they are written out in full like this.
  const config = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  };
  if (!config.apiKey || !config.projectId) {
    throw new Error("Sign-in isn't set up yet: add the Firebase web config (NEXT_PUBLIC_FIREBASE_*) to .env and restart.");
  }
  auth = getAuth(getApps().length ? getApp() : initializeApp(config));
  const emulator = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST;
  if (emulator) connectAuthEmulator(auth, `http://${emulator}`, { disableWarnings: true });
  return auth;
}
