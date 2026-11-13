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

## Grafica: stile "Onde" (scelto da Tommaso il 13 novembre 2026)
Il codice è in `engine/social.py` (funzione `carosello`). Nasce dallo stile A "Prima pagina" e ci aggiunge le onde.
- **Le onde**: in fondo a ogni slide ci sono onde rosse sovrapposte con un filo giallo sopra. **Sono un dato, non un
  decoro: un'onda per ogni continente che parla della notizia** (da 2 a 5). La forma dipende dalla notizia, quindi
  ogni post ha le sue, e a ogni slide si spostano un po': sfogliando sembrano muoversi.
- **Fondo carta** `#f7f2eb` con una grana leggera, **testo nero** `#111111`, rosso `#d3202b`, giallo `#ffd400`.
- **Riga in alto, uguale su ogni slide**: etichetta in maiuscolo spaziato a sinistra, **α rossa** a destra, filetto spesso.
- **Copertina**: titolo MAIUSCOLO enorme (Archivo 900 stretto), **una sola parola evidenziata in giallo** con un
  tratto un po' storto, come fatto a mano: l'ultima che contiene un numero, altrimenti l'ultima parola lunga.
  Sotto, una frase in Newsreader. In basso le onde grandi con la barra "Chi ne parla" (un quadratino per testata).
- **Come scrivere il Titolo Adolos perché la copertina venga forte**: "ETICHETTA: frase corta". La parte prima dei
  due punti diventa l'etichetta piccola, la parte dopo il titolo enorme. Esempio: "Spagna, primo sciopero generale
  dal 2012: la protesta è per la casa" → in copertina "LA PROTESTA È PER LA **CASA**". Dopo i due punti massimo
  6-8 parole, con la parola più forte in fondo. Senza i due punti il titolo intero finisce in copertina, più piccolo.
- **Slide dei fatti**: una frase grande per slide. Se la frase ha un dato con unità (1.170 euro, 48%, 3 miliardi,
  4.585 voti, 22 punti) la slide diventa **tutta rossa con il numero enorme in giallo**: rompe il ritmo e ferma chi
  scorre. Quindi: un solo numero forte per punto, e mettilo in un punto dove conta davvero.
- **"Chi ne parla"**: fondo nero, testate e paesi, barra "Da dove arriva: un'onda per continente".
- **Ultima slide**: "Tutti i link agli articoli su adolos.it", elenco delle testate, nota sull'AI, credito della foto.
- **Foto in copertina**: in un riquadro sotto la riga in alto, a colori, senza filtri né veli, con il credito sotto.
  SOLO licenza libera (Wikimedia, con autore e licenza) o foto vostre. Una foto senza licenza scritta NON è libera,
  anche se ritrae una persona pubblica: i diritti sono del fotografo. Senza foto adatta: solo titolo.
- **Punto cieco**: etichetta gialla "IL MONDO NE PARLA, L'ITALIA NO" sopra il titolo.
- **Font**: Archivo (titoli) e Newsreader (testo), gli stessi del sito. **Formati**: carosello 1080×1350 (4:5),
  video 1080×1920 (9:16).

### Perché questo stile (da tenere a mente quando si scrive)
- La copertina deve fermare il pollice in meno di un secondo: poche parole enormi, un colore che salta, un'idea sola.
- La seconda slide deve reggersi da sola: Instagram a volte ripropone il carosello partendo da lì.
- Il post si salva e si manda se dà qualcosa da usare: un numero preciso, due versioni a confronto, "cosa cambia".
- Niente esche: il titolo non dice mai più della sintesi (skill `adolos-viralita`).

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
