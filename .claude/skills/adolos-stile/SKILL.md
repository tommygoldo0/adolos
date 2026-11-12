---
name: adolos-stile
description: Usala per qualsiasi testo o grafica di Adolos: voce del brand, frasi vietate (anti AI slop), formato dei numeri e delle fonti, colori e font.
---

# Stile Adolos

## Voce
- Italiano semplice e diretto, frasi brevi, tono neutro. Come un amico informato, non un giornale urlato.
- Prima il fatto, poi il contesto. Niente opinioni.
- Numeri in cifre ("61 testate", "3 morti"), date precise ("lunedì 20 ottobre"), unità chiare.
- Fonti sempre in fondo: "Fonti: Reuters, ANSA, Le Monde".

## Anti AI slop: frasi vietate
"Sono entusiasta di annunciare", "Ecco il punto", "Questo cambia tutto", "Il futuro è qui",
"In un mondo in continua evoluzione", "Non è solo X, è Y", "Facciamo chiarezza", "Ma c'è di più",
"Senza precedenti" (se non è vero), "Un vero e proprio", "Andiamo a vedere", "Scopriamolo insieme",
elenchi di tre aggettivi, frasi con trattini a effetto, domande retoriche in apertura.

## Grafica: stile A "Prima pagina" (scelto da Tommaso il 13 novembre 2026)
Il codice è in `engine/social.py` (funzione `carosello`). Il vecchio stile tutto rosso non si usa più.
- **Fondo carta** `#f7f2eb`, **testo nero** `#111111`. Il rosso `#d3202b` resta per la α e per i numeri grandi
  (`#b3151f` per le etichette piccole, che si leggono meglio). **Giallo** `#ffd400` solo come evidenziatore.
- **Riga in alto, uguale su ogni slide**: etichetta in maiuscolo spaziato a sinistra, **α rossa** a destra, filetto nero spesso.
- **Copertina**: titolo MAIUSCOLO, Archivo 900 stretto, molto grande, allineato a sinistra. **Una sola parola
  evidenziata in giallo**: l'ultima che contiene un numero, altrimenti l'ultima parola lunga. Sotto, una frase in
  Newsreader. Se il Titolo Adolos ha i due punti ("Spagna, primo sciopero dal 2012: la protesta è per la casa"),
  la parte prima diventa l'etichetta e la parte dopo il titolo grande: scrivi i titoli così.
- **Barra "Chi ne parla" in fondo alla copertina**: un quadratino nero per testata + "7 testate · 6 paesi".
  È il segno fisso di Adolos: non toglierla e non cambiarle posto.
- **Slide dei fatti**: una frase grande per slide. Se la frase ha un dato con unità (1.170 euro, 48%, 3 miliardi)
  il numero va enorme e rosso, la frase sotto in Newsreader. Quindi: un numero forte per punto, non due.
- **"Chi ne parla"**: fondo nero, testo carta, etichette gialle, elenco testate e paesi, barra dei continenti.
- **Ultima slide**: "Tutti i link agli articoli su adolos.it" con adolos.it in giallo, elenco delle testate,
  nota sull'AI e credito della foto.
- **Foto in copertina**: in un riquadro sotto la riga in alto, a colori, senza filtri né veli, con il credito sotto.
  SOLO licenza libera (Wikimedia, con autore e licenza) o foto vostre. Una foto senza licenza scritta NON è libera,
  anche se ritrae una persona pubblica: i diritti sono del fotografo. Senza foto adatta: solo titolo.
- **Punto cieco**: etichetta gialla "IL MONDO NE PARLA, L'ITALIA NO" sopra il titolo.
- **Font**: Archivo (titoli) e Newsreader (testo), gli stessi del sito. **Formati**: carosello 1080×1350 (4:5),
  video 1080×1920 (9:16).
- **Titoli che funzionano**: massimo 8-10 parole dopo i due punti, il fatto o il dato per primo, la parola più
  forte in fondo (è quella che finisce in giallo). Il gancio non dice mai più della sintesi (skill `adolos-viralita`).

## Il tratto che ci distingue: "Chi ne parla" e "Punto cieco"
- Su ogni notizia mostriamo quante testate italiane ed estere la raccontano e da quali continenti.
- "Punto cieco italiano" = molte testate straniere, nessuna italiana tra quelle che leggiamo.
  "Solo in Italia" = solo testate italiane. Sono numeri, non opinioni: niente etichette destra/sinistra.
- **Paese e proprietà, non orientamento politico** (deciso da Tommaso il 12 novembre 2026): di ogni testata
  diciamo il paese e chi la possiede (pubblica, privata, no profit, gruppo editoriale), mai "di destra" o
  "di sinistra". I dati stanno in `engine/proprieta.json`. Finché una riga non ha `verificata: true` (controllata
  da una persona) si usa solo in redazione (Telegram, Notion) e non va sul sito né nei post.
  Più testate dello stesso gruppo editoriale non sono voci indipendenti: dillo ("3 testate, 2 dello stesso gruppo").
- Formato social dedicato: copertina "IL MONDO NE PARLA, L'ITALIA NO" + la notizia + slide "Chi ne parla"
  (barra dei continenti) + fonti.
