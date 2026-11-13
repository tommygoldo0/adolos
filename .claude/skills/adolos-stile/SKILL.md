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

## Grafica: stile "Foto" (scelto da Tommaso il 13 novembre 2026, sul modello dei post di Sky News)
Il codice è in `engine/social.py` (funzione `carosello`). Gli stili "Prima pagina" e "Onde" non si usano più.
- **Copertina**: una **foto a tutto schermo**, scurita in basso. In alto a sinistra il marchio (cerchio rosso con
  la α + scritta ADOLOS). In basso, uno sopra l'altro: **etichetta rossa** piena, **titolo bianco MAIUSCOLO**
  enorme con **una sola parola in giallo**, una frase in Newsreader, il credito della foto piccolo, e la barra
  "Chi ne parla" (un quadratino bianco per testata). Per il punto cieco l'etichetta è gialla:
  "IL MONDO NE PARLA, L'ITALIA NO".
- **Slide interne**: la stessa foto, sfocata e molto scurita, così il carosello resta unito. Testo bianco grande,
  una frase per slide. Se la frase ha un dato con unità (1.170 euro, 48%, 4.585 voti) il numero va enorme e giallo.
- **"Chi ne parla"** e **ultima slide** ("Ne parlano nel MONDO" + elenco delle testate + nota sull'AI + credito
  della foto) sullo stesso fondo. Il sito non si nomina finché non è pronto.
- **Colori**: rosso `#d3202b`, giallo `#ffd400`, bianco, nero caldo `#100809`. **Font**: Archivo (titoli, stretto e
  spesso) e Newsreader (testo). **Formati**: carosello 1080×1350 (4:5), video 1080×1920 (9:16).

### La foto: come la sceglie il motore (`engine/immagini.py`) e cosa NON si fa
- SOLO Wikimedia Commons con licenza libera (CC0, pubblico dominio, CC BY, CC BY-SA), con autore e licenza
  scritti sulla copertina, sull'ultima slide e nella didascalia. Una foto senza licenza scritta NON è libera, anche
  se ritrae una persona pubblica: i diritti sono del fotografo. Mai foto dei giornali, dei social o di Google.
- Una **persona** si cerca solo con nome e cognome: un cognome da solo può essere un'altra persona o un luogo.
  Per questo nella Sintesi e nei Punti scrivi sempre nome e cognome almeno una volta ("Scott Colom", non "Colom").
- Un **luogo** è la parola prima della virgola a inizio titolo ("Spagna, ...", "Gaza, ..."). Per un paese o una
  regione il motore usa una foto della capitale: è una foto di repertorio, non dell'evento. Non scrivere mai nel
  testo che la foto mostra il fatto.
- Niente foto di persone private. In cronaca meglio il luogo che la persona.
- Se non c'è una foto adatta la copertina usa il fondo scuro Adolos con la grande α: è grafica nostra, non una
  foto finta. Le immagini create con AI restano spente finché non c'è la chiave, e comunque mai volti di persone vere.
- **Prima di approvare guarda sempre la foto**: il motore può sbagliare soggetto. Se è sbagliata, scarta o
  correggi il titolo.

### Come scrivere il Titolo Adolos perché la copertina venga forte
- Forma "ETICHETTA: frase corta". La parte prima dei due punti va nell'etichetta rossa, la parte dopo è il titolo
  enorme. Esempio: "Spagna, primo sciopero generale dal 2012: la protesta è per la casa" → etichetta
  "SPAGNA, PRIMO SCIOPERO GENERALE DAL 2012", titolo "LA PROTESTA È PER LA **CASA**".
- Dopo i due punti massimo 6-8 parole, con la parola più forte in fondo: è quella che finisce in giallo
  (l'ultima con un numero, altrimenti l'ultima parola lunga).
- Senza i due punti il titolo intero finisce in copertina, più piccolo, e l'etichetta è la sezione.
- Un solo numero forte per punto. Niente esche: il titolo non dice mai più della sintesi (skill `adolos-viralita`).

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
