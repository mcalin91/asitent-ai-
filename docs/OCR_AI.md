# OCR si analiza AI

## Flux

1. Backendul valideaza tipul si dimensiunea fisierului.
2. Originalul este salvat cu un nume intern aleator in volumul privat `data/uploads`.
3. Pentru TXT, CSV, DOCX si PDF cu text se incearca mai intai extractia locala.
4. Cu `GEMINI_API_KEY` activ, PDF-ul, imaginea sau textul este trimis prin Gemini Interactions API.
5. Raspunsul este validat intr-o schema stricta inainte de salvarea in SQLite.
6. Valorile, rezumatul, alertele si recomandarile sunt salvate separat.
7. Documentele esuate pot fi reanalizate din interfata fara o noua incarcare.

## Rute

- `GET /ai/status` - furnizorul si modelul curent, fara a expune cheia.
- `POST /documents` - upload si analiza.
- `POST /analyses/upload` - acelasi flux, marcat ca document de analize.
- `POST /documents/{id}/reanalyze` - reia analiza fisierului original.
- `GET /documents/{id}/download` - descarca originalul.
- `POST /chat` - raspuns AI cu un context medical redus la datele relevante.

## Configurare

Variabilele sunt documentate in `.env.example`. Cheia Gemini ramane exclusiv pe
backend. Pentru productie, directorul de upload trebuie inlocuit sau protejat prin
stocare criptata, politici de retentie, autentificare si audit.

## Limite clinice

AI-ul extrage si explica informatii, dar nu pune diagnostic si nu recomanda
modificarea tratamentului. Valorile incerte sunt marcate `necunoscut`, iar
rezultatele trebuie verificate in documentul original si discutate cu un medic.
