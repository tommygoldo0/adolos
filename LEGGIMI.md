# ADOLOS — Oltre i Fatti

Un sito di notizie che si aggiorna da solo ogni 10 minuti. Legge i feed ufficiali delle testate di tutto il mondo, raggruppa gli articoli che parlano dello stesso fatto e mostra chi lo racconta, da quale paese e con quale titolo, con il link all'originale (il modello è Ground News). La redazione approva le sintesi su Notion, e il sistema prepara e pubblica i caroselli su Instagram.

**Si parte gratis.** AI e Instagram si accendono aggiungendo una chiave: non serve riscrivere niente.

---

## Le regole legali (sono già nel codice)

| Regola | Come la rispetta Adolos |
|---|---|
| 1. Niente copie | Sul sito vanno solo titolo originale, nome della testata, data e link. Mai il testo degli articoli. |
| 2. Sintesi da più fonti | Solo se il fatto è riportato da almeno 2 testate. L'AI parte da titoli e brevi descrizioni dei feed, estrae i fatti e scrive un testo nuovo. Un controllo automatico scarta i testi con 6 parole di fila uguali a una fonte. |
| 3. Niente scraping | Si leggono solo i feed RSS ufficiali e l'API aperta di GDELT. Google News, Reddit e Telegram via web sono **spenti** (in `engine/fonti.json`, voce `fonti_attive`). |
| 4. Immagini | Nessuna foto delle testate viene salvata o mostrata. I caroselli sono grafiche Adolos disegnate dal sistema, con caratteri a licenza libera. |
| 5. Attribuzione | Ogni notizia ha le testate, i titoli originali e i link. Il footer cita GDELT come chiede la sua licenza. |
| 6. Instagram | Si pubblica solo con l'API ufficiale di Meta, solo caroselli Adolos, e solo dopo che una persona ha approvato. |
| 7. Trasparenza | Ci sono le pagine "Fonti, diritti e rimozioni" e "Privacy e cookie", un avviso privacy e i caratteri ospitati sul sito (niente Google Fonts). Le sintesi fatte con l'AI lo dicono. |

**Revisione umana:** le bozze dell'AI non sono pubbliche. Restano nella cache privata del robot e su Notion, e vanno sul sito solo quando una persona mette Stato = Approvata. È anche quello che chiede l'AI Act europeo dal 2 agosto 2026 per i testi d'informazione scritti con l'AI.

**Controllo obbligatorio:** quando una notizia contiene nomi di persone legati a reati, la scheda Notion lo segnala in rosso. Prima di approvarla, rispettate la presunzione d'innocenza e non scrivete nomi di minori o di vittime.

**Prima di andare online**
- Scrivete il nome del responsabile del sito in `engine/fonti.json`, voce `sito` > `responsabile`. Compare nelle pagine Fonti e Privacy.
- Controllate i termini d'uso dei feed in `rss_diretti`. Per ognuno, `termini` va su `ok` o `no`; con `no` il feed non viene letto.
- Fate leggere le pagine Fonti e Privacy a un legale. Quest'ultima parte non sostituisce un avvocato.

---

## Come funziona

1. **Raccoglie**: i feed RSS ufficiali di 74 testate e l'API di GDELT, 18 paesi diversi a ogni giro.
2. **Traduce i titoli**, solo con servizi ufficiali: l'AI configurata oppure DeepL. Senza chiave i titoli restano in lingua originale.
3. **Raggruppa**: se Le Monde, NHK e BBC parlano dello stesso fatto, diventa una sola notizia con tutte le fonti.
4. **Valuta**: assegna il calore (quanto se ne parla) e l'attendibilità (da rosso a verde, sale con ogni testata indipendente).
5. **Il bot propone**: post, storia, solo sito o da verificare, e scrive perché.
6. **Scrive la bozza**, se l'AI è attiva: titolo, sintesi, i fatti (chi, cosa, dove, quando, perché) e i punti per il carosello.
7. **La redazione decide su Notion**: corregge, approva, spunta "Pubblica su Instagram".
8. **Pubblica**: la sintesi va sul sito con l'etichetta, il carosello viene disegnato e poi pubblicato su Instagram via API.

---

## Parte 1 — Mettere il sito online (15 minuti, gratis)

1. Vai su **github.com** → **+** → **New repository**. Nome `adolos`, **Public**. **Create repository**.
2. Clicca **uploading an existing file** e trascina **tutto il contenuto** della cartella `adolos`, compresa la cartella nascosta `.github` (su Mac la vedi nel Finder con **Cmd + Maiusc + .**). **Commit changes**.
3. **Settings** → **Pages** → *Source*: **GitHub Actions**.
4. **Settings** → **Actions** → **General** → *Workflow permissions*: **Read and write permissions** → **Save**.
5. Se il tuo nome utente GitHub non è `tommygoldo0`, apri `site/assets/config.js` e scrivi `tuonome/adolos`.
6. **Actions** → **Aggiorna notizie** → **Run workflow**. Dopo 4-5 minuti il sito è su `https://TUONOME.github.io/adolos/`. Al primo giro il robot scarica anche i caratteri del sito.
7. **Settings** → **Secrets and variables** → **Actions** → **Variables** → **New repository variable**: nome `SITO_URL`, valore l'indirizzo del punto 6.

I dati di lavoro (archivio, traduzioni, bozze, spesa AI) restano nella cache privata di GitHub Actions e non finiscono nel repository pubblico.

---

## Parte 2 — L'area staff su Notion (10 minuti, gratis)

Su Notion ci sono già due database:
- **Redazione Adolos**: una scheda per ogni notizia proposta dal bot.
- **Fonti Adolos**: qui si aggiungono le testate, una riga per feed RSS.

Per collegarli:
1. **notion.so/my-integrations** → **New integration** → nome `Adolos bot` → **Save**. Copia l'**Internal Integration Secret**.
2. Apri **Redazione Adolos** → **•••** → **Connections** → aggiungi **Adolos bot**. Fai lo stesso con **Fonti Adolos**.
3. Su GitHub, nei **Secrets**, aggiungi:

| Nome | Valore |
|---|---|
| `NOTION_TOKEN` | il codice copiato al punto 1 |
| `NOTION_DB_REDAZIONE` | `9c9a2cafbee14f1796df2978958984b8` |
| `NOTION_DB_FONTI` | `4da73fc1b90b43df911203ebda7ba837` |

Le chiavi segrete vanno solo nei Secrets di GitHub, mai nei file o in chat.

**Come si lavora su una scheda** (anche dal telefono):
1. Arriva con Stato = **Da valutare**. Se c'è il riquadro ⚠️ o la casella **Controllo obbligatorio**, va controllata con più attenzione.
2. Apri le fonti in fondo alla scheda e controlla i fatti della bozza.
3. Correggi **Titolo Adolos**, **Sintesi** e **Punti carosello** (una frase per riga). Se l'AI è spenta, scrivili tu: bastano 4-5 righe con parole tue.
4. Stato = **Approvata**: al giro dopo la sintesi è sul sito e il carosello è pronto (il link compare in **Carosello**).
5. Guarda il carosello, poi spunta **Pubblica su Instagram**: al giro dopo parte. La scheda passa a **Pubblicata** con il link al post.
6. Stato = **Scartata**: la notizia sparisce dal sito.

---

## Parte 3 — Avvisi su Telegram (5 minuti, gratis, facoltativo)

È il vostro bot che vi scrive, con l'API ufficiale di Telegram.
1. Su Telegram cerca **@BotFather** → `/newbot` → nome `Adolos Redazione`. Copia il **token**.
2. Crea un gruppo, aggiungi il bot e scrivi un messaggio.
3. Apri `https://api.telegram.org/botTOKEN/getUpdates` e copia il numero dopo `"chat":{"id":`.
4. Nei **Secrets** di GitHub aggiungi `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.

---

## Parte 4 — Aggiungere testate

Su Notion, database **Fonti Adolos**: una riga per testata, con tipo **Sito (feed RSS)** o **Agenzia (feed RSS)**. Nell'indirizzo va quello del feed. Spunta **Attiva**, e **Termini verificati** dopo aver letto le condizioni del feed.

- Per trovare il feed, prova ad aggiungere `/feed` o `/rss` all'indirizzo del sito, o cerca "RSS" in fondo alla pagina. È giusto se vedi una pagina di testo con tanti `<item>`.
- Le righe di tipo **Telegram** e **Google News** vengono ignorate finché quelle fonti restano spente. Si possono riaccendere solo con un permesso scritto o un contratto.
- **Pagine Instagram di altri:** non si leggono in automatico. Se una pagina ha anche un sito con feed RSS, si aggiunge quello.

---

## Parte 5 — L'AI per titoli, sintesi, indice e voce (a pagamento, pochi euro)

Una sola chiave fa tutto: **Gemini API** di Google (testi con `gemini-3.1-flash-lite`, voce con Gemini TTS).

1. Vai su **aistudio.google.com**, entra con l'account Google della redazione e crea una **API key**.
2. Attiva la **fatturazione** sul progetto (Google Cloud): nell'Unione Europea la quota gratuita non si può usare per app e siti. Imposta subito un **avviso di budget** basso (per esempio 10 €).
3. Su GitHub: Settings → Secrets and variables → Actions → **New repository secret**, nome `AI_KEY`, valore la chiave. Non incollarla mai in chat, in un file o su Notion.
4. Per la voce, sul computer dove usi Claude Code: imposta la variabile `GEMINI_API_KEY` con la stessa chiave (o lascia solo `AI_KEY`).

Costi indicativi: testi 2-5 € al mese, voce 1-3 € al mese. Il motore ha i suoi tetti (`fonti.json` → `ai` → `budget_mensile_usd`, e `voce` → `budget_mensile_usd`).
Se preferite Claude per i testi: chiave dalla Console Anthropic, secret `AI_KEY`, e la variabile `AI_PROVIDER` = `anthropic`, `AI_MODEL` = `claude-haiku-5-5`.
ChatGPT Go, Gemini Pro della scuola e Claude Max sono abbonamenti alle app: non danno una chiave API.

---

## Parte 6 — Pubblicare su Instagram con l'API ufficiale (gratis, facoltativo)

1. L'account Instagram `adolos.it` deve essere **professionale** (business o creator) e collegato a una **Pagina Facebook**.
2. Su **developers.facebook.com** crea un'app, aggiungi il prodotto **Instagram** e genera un token con i permessi di pubblicazione: `instagram_basic`, `instagram_content_publish` e `pages_read_engagement` con il login Facebook, oppure `instagram_business_basic` e `instagram_business_content_publish` con il login Instagram. Se l'account è vostro e siete amministratori dell'app di solito basta l'accesso standard, ma Meta può chiedere verifiche.
3. Nei **Secrets** di GitHub aggiungi `IG_USER_ID` (l'ID dell'account Instagram) e `IG_TOKEN`. Se usi il login Instagram, aggiungi anche la variabile `IG_GRAPH_HOST` = `graph.instagram.com`.
4. I token hanno una scadenza: segnatevi quando rinnovarli.

Le regole di Meta: massimo 10 immagini per carosello, solo JPEG, e le immagini devono stare a un indirizzo pubblico (il sito). Il motore pubblica al massimo 6 post al giorno (`engine/fonti.json`, voce `instagram`).

## Parte 7 — La redazione AI in Claude Code (indice di viralità, agenti, Canva, video)

**Il flusso, in breve**
1. Il motore (ogni 10 minuti) crea le schede su Notion con **Indice virale** (0-100), **Zona** (verde/rossa) e **Perché virale**.
2. Su Notion il tuo amico apre la vista **"Da approvare (per indice)"**: le migliori sono in alto. Su quelle che gli piacciono mette Stato = **In revisione**.
3. Qualcuno apre Claude Code nella cartella del progetto e scrive: *usa la skill adolos-redazione*. Gli agenti preparano per ogni notizia: angoli, ganci, carosello, didascalia, copione TikTok, testo Facebook, grafica Canva e controllo legale. Alla fine spuntano **Pacchetto pronto**.
4. Il tuo amico controlla, mette Stato = **Approvata** e spunta **Pubblica su Instagram**. Il motore pubblica al giro dopo. Se il **Controllo legale** è "Da sistemare", la pubblicazione è bloccata.
5. Dopo 48 ore il motore legge i risultati veri da Instagram e una volta a settimana aggiusta l'indice.

**"Chi ne parla" e "Punto cieco" (l'idea di Ground News, fatta per l'Italia)**: su ogni notizia il sito mostra quante testate italiane ed estere la raccontano e da quali continenti. La pagina **Punto cieco** raccoglie le notizie che il mondo racconta e le testate italiane che leggiamo no, e quelle che si raccontano solo in Italia. Le soglie sono in `engine/fonti.json` → `punto_cieco`. Niente etichette destra/sinistra: solo numeri controllabili.

**Gli agenti** (cartella `.claude/agents/`): RADAR (notizie), PRIME (capo redattore), INDICE (viralità), LEGALE (controllo), VISION (immagini), PULSE (Instagram e TikTok), SOCIAL (Facebook), AUTHORITY (LinkedIn, più avanti), CANVA (impaginazione), VOICE (voce AI), DIRECTOR (video Hyperframes).

**Titoli**: sul sito non compaiono i titoli delle testate né le loro traduzioni. Ogni notizia ha un titolo scritto da Adolos (dall'AI con controllo anti-copia, o dalla redazione su Notion). Senza titolo Adolos la notizia resta solo su Notion. Le testate italiane sono in modalità "solo conteggio e link".

**Voce AI**: `python3 engine/voce.py video/<id>/copione.txt` crea `voce.wav` con Gemini TTS. Serve la variabile `GEMINI_API_KEY` (servizio a pagamento: nell'UE la quota gratuita non si può usare per app e siti; un video di 30 secondi costa meno di un centesimo, tetto 3 $ al mese). Sempre l'etichetta "Voce generata con AI".
**Le skill** (cartella `.claude/skills/`): adolos-redazione, adolos-viralita, adolos-controllo-legale, adolos-stile, adolos-regia.

**Cosa collegare in Claude Code** (una volta sola)
- **Notion** e **Canva**: come connettori di Claude (Impostazioni → Connettori). Per Canva serve un modello del brand chiamato "Adolos carosello" con i campi dati `cover_title`, `point_1`…`point_4`, `sources`, `section`, `image`, `image_credit`, `ai_label`.
- **Hyperframes** (video): serve Node.js 22+ e FFmpeg, poi `claude plugin marketplace add heygen-com/hyperframes` e `claude plugin install hyperframes@hyperframes`.
- Le immagini AI sono **spente** (`engine/fonti.json` → `immagini` → `ai: false`). Si usano template e foto Wikimedia con licenza libera.

---

## Quanto costa

| Cosa | Costo |
|---|---|
| Sito, robot ogni 10 minuti, Notion, Telegram, API di Instagram | gratis |
| AI per titoli e sintesi (Claude Haiku 5.5: 0,10 $ per milione di token in entrata, 0,50 $ in uscita) | 2-5 € al mese circa, con tetto a 5 $ |
| Voce AI per i video (Gemini TTS, circa 0,002 $ ogni 10 secondi fino a fine 2026) | 1-3 € al mese, con tetto a 3 $ |
| Dominio `adolos.it` | circa 10 € all'anno |
| Una consulenza legale prima del lancio | una tantum, chiedete un preventivo |
| Assicurazione di responsabilità civile per l'attività editoriale, ed eventualmente una società (SRL) | da valutare con un commercialista quando il progetto cresce |

Canva è facoltativo (va bene il vostro Canva Pro): senza Canva i caroselli li disegna il sistema. Claude Code usa il vostro abbonamento Claude, senza costi in più.

---

## Cosa c'è nella cartella

| File | A cosa serve |
|---|---|
| `engine/adolos.py` | Il motore: raccoglie, raggruppa, valuta, decide (bot) |
| `engine/traduci.py` | Traduzione dei titoli, solo servizi ufficiali |
| `engine/ai.py` | Collegamento all'AI, con tetto di spesa |
| `engine/sintesi.py` | Bozze di sintesi multi-fonte con controllo anti-copia |
| `engine/indice.py` | Indice di viralità, zona di rischio, risultati veri e calibrazione |
| `engine/copertura.py` | Chi ne parla (Italia contro estero, continenti) e punto cieco |
| `engine/titoli.py` | Titoli scritti da Adolos e dati pubblici senza titoli delle testate |
| `engine/voce.py` | Voce AI (Gemini TTS) con etichetta e tetto di spesa |
| `engine/social.py` | Caroselli Adolos e pubblicazione su Instagram via API |
| `engine/redazione.py` | Notion e Telegram |
| `engine/sito.py` | Le pagine del sito |
| `engine/fonti.json` | Fonti, interruttori legali, AI, Instagram, regole del bot, responsabile |
| `engine/fonts/` | Caratteri a licenza libera per i caroselli (licenze incluse) |
| `site/` | Il sito pronto. `site/social/` contiene i caroselli |
| `CLAUDE.md` | Le regole del progetto che Claude Code legge sempre |
| `.claude/agents/`, `.claude/skills/` | La redazione AI |
| `video/` | I video: `brief.md`, `frame.md` e il risultato |

Per provarlo sul computer, senza internet: `python engine/adolos.py --campione`, poi apri `site/index.html`. I dati di prova sono titoli veri del 17 ottobre 2026, con una sintesi d'esempio sulla prima notizia.
