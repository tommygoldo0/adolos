---
name: adolos-regia
description: Usala per preparare un video Adolos con Hyperframes: intervista di regia in 5 blocchi a scelta multipla, poi brief.md e frame.md in video/<id>/ e il comando /hyperframes.
---

# Regia video Adolos (Hyperframes)

Mai scrivere subito il codice del video. Prima l'intervista, un blocco alla volta, con conferma.
Ogni domanda ha 3-4 opzioni; la prima è quella predefinita di Adolos.

## Blocco 1 – Messaggio
- Messaggio chiave in una frase (proponi quello del brief).
- Domanda a cui risponde il video.
- Gancio dei primi 3 secondi: (a) il dato · (b) il contrasto · (c) la conseguenza · (d) la domanda.

## Blocco 2 – Pubblico e formato
- Pubblico: (a) 18-35 italiani che si informano sui social · (b) professionisti · (c) appassionati del tema.
- Piattaforma: (a) Reel + TikTok 9:16 · (b) solo TikTok · (c) post feed 4:5.
- Durata: (a) 25-35 s · (b) 15-20 s · (c) 45-60 s. Voce fuori campo: (a) no, solo testo · (b) sì.

## Blocco 3 – Storyline
Scena per scena: testo a schermo, durata, cosa si vede. Ultima scena sempre: fonti + logo Adolos.
Proponi una storyline completa dal copione di PULSE e chiedi solo cosa cambiare.

## Blocco 4 – Look
- (a) **Sobrio**: sfondo chiaro, testo nero, accento colore della sezione.
- (b) **Adolos**: bordeaux scuro e rosso Adolos (#3a0b0e, #d3202b), titoli bianchi maiuscoli, α rosso in alto a destra. (predefinito)
- (c) **Rilassato**: colori caldi, angoli arrotondati.
Palette e font come nella skill `adolos-stile` (sans spesso e stretto per i titoli), cornice fissa con logo e barra di avanzamento.

## Blocco 5 – Movimento e audio
- Voce: (a) voce AI di ADOLOS-VOICE (voce Charon, stile notiziario calmo) con etichetta "Voce generata con AI"
  · (b) nessuna voce, solo testo a schermo · (c) voce di un membro della redazione registrata a mano.
- Ritmo: (a) un cambio ogni 2-3 s · (b) più lento, 4-5 s. Transizioni: (a) taglio netto · (b) scorrimento.
- Movimenti di camera: (a) zoom lenti sulle cifre · (b) nessuno.
- Musica: (a) nessuna, si aggiunge a mano dalla libreria della piattaforma · (b) traccia con licenza libera.
- Effetti sonori sincronizzati ai cambi: (a) leggeri · (b) nessuno.

## Dopo la conferma
1. Scrivi `video/<id>/brief.md`: pubblico, messaggio, copione, storyboard con tempi, audio ed effetti.
2. Scrivi `video/<id>/frame.md`: design system completo del video (colori in esadecimale, font e dimensioni,
   griglia, margini di sicurezza 9:16, cornice, animazioni, tempi).
3. Dai il comando:
   `/hyperframes genera il video leggendo le direttive da brief.md e il design system da frame.md`

Requisiti Hyperframes: Node.js 22+ e FFmpeg. Installazione del plugin in Claude Code:
`claude plugin marketplace add heygen-com/hyperframes` e `claude plugin install hyperframes@hyperframes`.
Se Tommaso dice "valori Adolos", usa tutte le opzioni (a) senza fare domande e mostra solo il riepilogo.
