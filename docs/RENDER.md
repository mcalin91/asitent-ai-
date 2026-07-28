# Publicare pe Render

## Fisiere folosite

- `render.yaml` defineste serviciul web, secretele si discul persistent.
- `Dockerfile.render` construieste interfața Next.js si porneste FastAPI.
- `render.env.example` este lista variabilelor necesare, fara chei reale.

## Publicare

1. Incarca directorul proiectului intr-un repository privat GitHub sau GitLab.
2. In Render, alege `New` -> `Blueprint`.
3. Conecteaza repository-ul care contine `render.yaml`.
4. Completeaza valorile solicitate pentru `GEMINI_API_KEY` si
   `GOOGLE_PLACES_API_KEY`.
5. Confirma Blueprint-ul si asteapta ca verificarea `/health` sa devina verde.

Aplicatia va fi disponibila la adresa HTTPS generata de Render. Interfata si API-ul
folosesc acelasi domeniu.

## Observatii importante

- Discul persistent necesita un serviciu Render platit. Fara disc, baza SQLite si
  documentele incarcate se pierd la redeploy.
- Daca Render schimba numele serviciului, actualizeaza `CORS_ORIGINS` cu URL-ul
  final `https://...onrender.com`.
- Cheile API se introduc numai in sectiunea Environment din Render. Nu incarca
  un fisier `.env` cu valori reale in repository.
- Pentru Android si iOS seteaza `NEXT_PUBLIC_API_URL` la URL-ul HTTPS Render
  inainte de buildul Capacitor.
- Pentru utilizare medicala reala mai sunt necesare autentificare, consimtamant,
  criptare, audit si politici de retentie.
