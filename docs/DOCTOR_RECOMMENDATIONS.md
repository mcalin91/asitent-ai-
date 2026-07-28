# Medici recomandati

## Logica functionala

- Aplicatia analizeaza numai valorile marcate si recomandarile deja salvate.
- Regulile aleg maximum trei specialitati, fara a formula un diagnostic.
- Locatia este citita numai dupa acordul explicit al utilizatorului.
- Backendul cauta prin Google Places Text Search (New), fara a expune cheia.
- Rezultatele sunt ordonate dupa rating, numarul recenziilor si distanta calculata.
- Selectarea unui medic precompleteaza formularul existent de programare.

## API

- `GET /doctors/status`
- `GET /doctors/recommendations?latitude=...&longitude=...&radius_km=10`

Raza acceptata este intre 1 si 50 km. Se poate transmite optional parametrul
`specialty` pentru o cautare aleasa manual.

## Confidentialitate si conformitate

Coordonatele sunt utilizate pentru cererea curenta si nu sunt salvate. Continutul
Google Places nu este memorat in baza de date. Interfata pastreaza linkul catre
Google Maps si explica ordonarea rezultatelor si natura recenziilor.

In productie sunt necesare Termeni de utilizare si Politica de confidentialitate
care includ cerintele Google Maps Platform, plus restrictii ale cheii API pentru
serviciul Places si backendul public.
