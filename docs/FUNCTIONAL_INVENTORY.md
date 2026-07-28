# Inventar functional

## Ecrane

| Ecran | Ruta UI | API folosit | Functionalitate |
| --- | --- | --- | --- |
| Dashboard | `/` | `GET /dashboard` | Statistici, analize recente, documente recente, recomandari, notificari si actiuni rapide. |
| Dosar Medical | `/` | `GET /medical-record`, `GET /medical-record/export` | Agregare dosar si export JSON. |
| Analize | `/` | `GET /analyses`, `POST /analyses`, `POST /analyses/upload` | Listare, adaugare manuala si upload analize. |
| Documente | `/` | `GET /documents`, `POST /documents`, `DELETE /documents/{id}` | Upload documente, analiza demo, listare si stergere. |
| Investigatii | `/` | `GET /investigations`, `POST /investigations` | Adaugare si listare investigatii. |
| Medicatie | `/` | `GET /medications`, `POST /medications`, `PATCH /medications/{id}/toggle`, `DELETE /medications/{id}` | Adaugare medicatie, activare/oprire si stergere. |
| Istoric Medical | `/` | `GET /history`, `POST /history` | Adaugare si listare evenimente medicale. |
| Monitorizare | `/` | `GET /monitoring`, `POST /monitoring` | Adaugare si listare masuratori. |
| Recomandari AI | `/` | `GET /recommendations`, `POST /recommendations`, `PATCH /recommendations/{id}/complete` | Listare recomandari si marcare finalizata. |
| Programari | `/` | `GET /appointments`, `POST /appointments`, `DELETE /appointments/{id}` | Programare consultatie, listare si anulare. |
| Setari | `/` | `GET /settings`, `PUT /settings` | Profil pacient, limba, notificari si mesaj de urgenta. |
| Notificari | `/` | `GET /notifications`, `PATCH /notifications/{id}/read` | Listare si marcare notificari ca citite. |

## Butoane si comenzi

| Comanda | Unde apare | Actiune |
| --- | --- | --- |
| Incarca documente | Dashboard, Documente | Deschide selectorul de fisier si trimite catre `POST /documents`. |
| Incarca analize | Dashboard, Analize | Deschide selectorul de fisier si trimite catre `POST /analyses/upload`. |
| Adauga medicatie | Dashboard, Medicatie | Navigheaza la ecranul Medicatie si salveaza prin `POST /medications`. |
| Programeaza consultatie | Dashboard, Programari | Navigheaza la Programari si salveaza prin `POST /appointments`. |
| Exporta dosar medical | Topbar, Dosar Medical | Descarca JSON din `GET /medical-record/export`. |
| Vezi toate analizele | Dashboard | Navigheaza la ecranul Analize. |
| Vezi toate recomandarile | Dashboard, Recomandari AI | Navigheaza sau reincarca recomandarile. |
| Documente recente | Dashboard | Navigheaza la ecranul Documente. |
| Notificari | Topbar, ecran dedicat | Afiseaza notificarile si le marcheaza citite. |
| Chat AI | Panou lateral/inferior | Trimite intrebari la `POST /chat`. |
| Intrebari rapide | Panou Chat AI | Completeaza si trimite intrebari predefinite din `GET /quick-questions`. |
| Stergere document | Documente | Cere confirmare si apeleaza `DELETE /documents/{id}`. |
| Oprire/activare medicatie | Medicatie | Apeleaza `PATCH /medications/{id}/toggle`. |
| Finalizare recomandare | Recomandari AI | Apeleaza `PATCH /recommendations/{id}/complete`. |
| Anulare programare | Programari | Cere confirmare si apeleaza `DELETE /appointments/{id}`. |

## Stari UI

- Loading global pentru incarcari si actiuni.
- Mesaje de succes dupa salvare, upload, export, stergere sau actualizare.
- Mesaje de eroare preluate din API.
- Empty states pentru fiecare lista.
- Confirmari pentru stergere document, stergere medicatie si anulare programare.
- Layout responsive cu navigatie inferioara pe mobil si suport pentru zonele sigure ale ecranului.

## Servicii externe ramase

- Autentificare reala si roluri pacient/medic.
- Stocare fisiere medicale in cloud criptat.
- OCR pentru PDF scanat si imagini.
- Integrarea Gemini este disponibila; pentru productie mai sunt necesare auditul si consimtamantul explicit.
- Push notifications native pentru Android/iOS.
- Calendar extern pentru programari.
- Backend HTTPS public pentru aplicatiile mobile publicate.
