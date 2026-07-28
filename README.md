# Asistent Medical AI

Aplicatie multiplatforma pentru dosar medical personal: web, PWA, Android si iOS, cu Next.js, FastAPI si SQLite.

## Ce este functional

- Dashboard cu statistici, documente recente, analize recente, recomandari si notificari.
- Dosar Medical cu agregarea tuturor datelor si export JSON.
- Analize cu adaugare manuala si incarcare fisier.
- Documente cu upload, OCR multimodal pentru PDF/imagini, analiza AI structurata si stergere cu confirmare.
- Investigatii, Medicatie, Istoric Medical, Monitorizare si Programari cu formulare reale.
- Recomandari AI cu generare automata din valori iesite din interval si marcare finalizata.
- Setari pentru pacient, limba, notificari si mesaj de urgenta.
- Chat AI real cu intrebari rapide si context minimizat din dosar; fallback local cand cheia nu este configurata.
- Medici recomandati dupa specialitatea sugerata de dosar, distanta, rating si recenzii Google.
- Selectarea unui medic precompleteaza formularul de programare din aplicatie.
- Stari de loading, eroare, succes, empty state si confirmari.
- PWA si configurare Capacitor pentru Android/iOS.

## Pornire locala

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Aplicatia web ruleaza la `http://localhost:3000`, iar API-ul la `http://localhost:8000`.

## Activare OCR si AI cu Gemini

Copiaza `.env.example` ca `.env` in radacina proiectului si seteaza cheia doar pe backend:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=cheia-proiectului-tau
GEMINI_MODEL=gemini-3.6-flash
```

Cheia Gemini se genereaza in Google AI Studio. Nu o introduce in variabile
`NEXT_PUBLIC_*` si nu o include in aplicatiile Android/iOS.
Backendul accepta PDF, JPG, PNG, WebP, TXT, CSV si DOCX, maximum 10 MB. Imaginile
si PDF-urile scanate necesita cheia Gemini; fisierele text pot fi procesate si local.
Starea curenta este disponibila la `GET /ai/status`.

## Recomandari de medici

Activeaza Places API (New) intr-un proiect Google Maps Platform si adauga in `.env`:

```env
GOOGLE_PLACES_API_KEY=cheia-ta-server
```

Cheia este folosita exclusiv de backend. Ecranul `Medici recomandati` solicita
permisiunea de localizare, deduce maximum trei specialitati din valorile anormale
si recomandarile dosarului, apoi afiseaza cabinete si clinici din raza aleasa.
Rezultatele si recenziile Google nu sunt stocate in SQLite; se salveaza doar
programarea creata explicit de utilizator.

Documentele medicale sunt trimise Gemini numai cand cheia este activa.
Pentru productie trebuie definite politica de consimtamant, retentia datelor,
criptarea, controlul accesului si un acord adecvat pentru prelucrarea datelor medicale.

OpenAI ramane disponibil ca furnizor optional prin `AI_PROVIDER=openai` si
variabilele `OPENAI_API_KEY` / `OPENAI_MODEL`.

## Docker

```bash
docker compose up --build
```

## Render

Proiectul include `render.yaml`, `Dockerfile.render` si un disc persistent pentru
SQLite/documente. Pasii de publicare sunt in `docs/RENDER.md`. Cheile Gemini si
Google Places sunt solicitate de Render la crearea Blueprint-ului si nu sunt
incluse in proiect.

## Android si iOS

```bash
cd frontend
npm install
cp .env.mobile.example .env.mobile.local
npm run mobile:init:android
npm run android
```

Pentru iOS ruleaza comenzile pe macOS:

```bash
npm run mobile:init:ios
npm run ios
```

Pentru publicare mobila, `NEXT_PUBLIC_API_URL` trebuie sa indice un backend HTTPS accesibil public.

## Observatie medicala

Aplicatia este un MVP pentru testare si organizarea datelor. Nu pune diagnostic si nu inlocuieste consultul medical.
