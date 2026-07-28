# Web, PWA, Android si iOS

Frontend-ul este configurat cu export static Next.js si Capacitor.

## Web si PWA

- `public/manifest.json` defineste numele, tema si iconita aplicatiei.
- `public/sw.js` cache-uieste fisierele de baza pentru PWA.
- `app/layout.tsx` seteaza metadata si theme color.

## Android

1. Configureaza `frontend/.env.mobile.local` cu backend HTTPS.
2. Ruleaza `npm run mobile:init:android`.
3. Deschide proiectul generat cu `npm run android`.

## iOS

1. Ruleaza pe macOS cu Xcode instalat.
2. Configureaza `frontend/.env.mobile.local` cu backend HTTPS.
3. Ruleaza `npm run mobile:init:ios`.
4. Deschide proiectul cu `npm run ios`.

## Backend mobil

Aplicatiile mobile au nevoie de un API public prin HTTPS. Pentru productie sunt necesare autentificare, criptare, politici GDPR si jurnal de audit.
