---
name: adolos-redazione
description: Usala per preparare i pacchetti pronti da pubblicare di Adolos partendo dalle notizie scelte su Notion (o da un ID storia): fa lavorare in ordine PRIME, VISION, PULSE, SOCIAL, INDICE, CANVA, LEGALE e scrive tutto sulla scheda Notion.
---

# Redazione Adolos: dalla notizia scelta al pacchetto pronto

Il tuo amico sceglie le notizie su Notion. Questa skill prepara tutto il resto e si ferma prima della
pubblicazione: l'ultimo clic è sempre di una persona.

## 0. Quali notizie
- Se ti danno un ID storia, lavora solo su quello.
- Altrimenti, nella vista Notion "Da approvare (per indice)" prendi le schede con Stato = "In revisione"
  (= "mi piace, preparala") e "Pacchetto pronto" non spuntato. Massimo 10 per volta.
- Data source Notion: `collection://57ca1ff1-e682-4f7e-af95-747a0658bb5e`.

## 1. Per ogni notizia, in quest'ordine
1. **adolos-prime**: fatti, fonti, 3 angoli, brief. Se dice "Notizia non pronta", scrivi il motivo nel
   campo "Motivo del bot", lascia la scheda com'è e passa alla prossima.
2. **adolos-vision**: immagine (A template, D Wikimedia; B AI solo se attivata).
3. **adolos-pulse**: 5 ganci, carosello, didascalia, copione TikTok.
4. **adolos-social**: testo Facebook. **adolos-authority** solo per Economia e Tecnologia.
5. **adolos-indice**: voto ai ganci, sceglie il migliore come copertina.
6. **adolos-canva**: impagina (Canva Autofill, oppure carosello del motore).
   Se la notizia merita un video: **adolos-voice** (voce AI etichettata) e poi **adolos-director** (Hyperframes).
7. **adolos-legale**: controllo. Se "Da sistemare", rimanda al writer giusto UNA volta, poi ricontrolla.
   Se è ancora "Da sistemare", lascia l'esito e i problemi sulla scheda.

## 2. Cosa scrivere sulla scheda Notion
Angoli proposti, Titolo Adolos (gancio scelto), Sintesi, Punti carosello (uno per riga), Ganci alternativi,
Didascalia Instagram, Copione TikTok, Testo Facebook, Immagine (provenienza e crediti), Link Canva,
Controllo legale, e infine **Pacchetto pronto = sì**.

## 3. Cosa NON fare mai
- Non mettere Stato = Approvata, non spuntare "Pubblica su Instagram", non pubblicare da nessuna parte.
- Non toccare il campo "ID storia".
- Non cancellare il testo scritto da una persona sulla scheda: se c'è già un testo umano, proponi il tuo
  nei commenti della pagina invece di sovrascrivere.

## 4. Alla fine
Una riga per notizia: titolo, indice, zona, esito legale, cosa resta da fare alla persona.
Poi la persona controlla, mette Stato = Approvata e spunta "Pubblica su Instagram": il motore pubblica al giro dopo.
