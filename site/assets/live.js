/* ADOLOS — parti vive del sito */
(function () {
  "use strict";
  var base = document.body.dataset.base || "";
  var L = window.ADOLOS_LIVE || { storie: [], nomi: {}, aggiornato: null, paesi: {} };
  var ridotto = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var esc = function (t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var ora = function (iso) { return new Date(iso).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }); };

  /* ---------- "aggiornato X minuti fa" */
  function relativo() {
    var el = $("[data-aggiornato]"); if (!el || !L.aggiornato) return;
    var m = Math.max(0, Math.round((Date.now() - new Date(L.aggiornato)) / 60000));
    el.textContent = m < 1 ? "aggiornato adesso" : m < 60 ? "aggiornato " + m + (m === 1 ? " minuto fa" : " minuti fa") : "aggiornato alle " + ora(L.aggiornato);
  }
  relativo(); setInterval(relativo, 30000);

  /* ---------- termometro e voce della lista */
  function termo(c) {
    var on = Math.max(1, Math.round(c / 10)), h = "";
    for (var i = 1; i <= 10; i++) h += "<i class='" + (i <= on ? "on c" + Math.min(4, Math.ceil(i / 2.5)) : "") + "'></i>";
    return "<span class='termo' aria-label='Calore " + c + " su 100'>" + h + "</span>";
  }
  function provenienza(s) {
    var n = s.n_fonti || s.fonti.length, p = s.paesi.length, nomi = s.fonti.slice(0, 2).join(", ") + (n > 2 ? " e altre " + (n - 2) : "");
    return "<span class='prov'>Ripresa da <b>" + n + (n === 1 ? " testata" : " testate") + "</b>" + (p > 1 ? " in <b>" + p + " paesi</b>" : "") + ": " + esc(nomi) + "</span>";
  }
  function voce(s, nuova) {
    return "<a class='voce" + (nuova ? " nuova" : "") + "' href='" + base + "storie/" + s.id + ".html'><span class='riga-calore'><span class='ora'>" + ora(s.aggiornata) + "</span>" + termo(s.calore) +
      "<span class='chip-cat'>" + esc(s.sezione || "") + "</span></span><h4 class='t'>" + esc(s.titolo) + "</h4>" + provenienza(s) + "</a>";
  }

  /* ---------- diretta: righe con attendibilità e diffusione */
  function fa(iso) {
    var m = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
    if (m < 1) return "adesso"; if (m < 60) return m + " min fa";
    var h = Math.round(m / 60); return h < 24 ? h + (h === 1 ? " ora fa" : " ore fa") : Math.round(h / 24) + " g fa";
  }
  function tempiRelativi() { document.querySelectorAll(".fa[data-t]").forEach(function (el) { el.textContent = fa(el.dataset.t); }); }
  tempiRelativi(); setInterval(tempiRelativi, 30000);
  function durata(m) { if (m < 60) return m + " min"; var h = Math.floor(m / 60), r = m % 60; return h + " h" + (r ? " " + r + " min" : ""); }
  function curvaSvg(c, w, h) {
    w = w || 120; h = h || 34; if (!c || !c.length) return "";
    var mx = Math.max.apply(null, c); if (mx === Math.min.apply(null, c)) return "";
    var passo = w / Math.max(1, c.length - 1), p = c.map(function (v, k) { return (k * passo).toFixed(1) + "," + (h - 3 - v / mx * (h - 6)).toFixed(1); }).join(" ");
    return "<svg class='curva' viewBox='0 0 " + w + " " + h + "' width='" + w + "' height='" + h + "' aria-hidden='true'><polygon class='area' points='0," + h + " " + p + " " + w + "," + h + "'/><polyline class='linea' points='" + p + "'/></svg>";
  }
  function statoFonte(s) {
    if (s.conferma) return s.conferma.dopo_min < 5 ? "Ripresa subito da <b>" + esc(s.conferma.fonte) + "</b>" : "Confermata da <b>" + esc(s.conferma.fonte) + "</b> dopo " + durata(s.conferma.dopo_min);
    if (s.stato === "voce") return "Nessun giornale l'ha ancora ripresa";
    if (s.stato === "una_fonte") return "Per ora la dà solo questa testata";
    return "Ripresa insieme da " + (s.n_fonti || 1) + " testate";
  }
  function rigaDiretta(s, extra) {
    var a = s.att || 50, p = s.prima || {};
    return "<a class='rd" + (s.stato === "voce" ? " voce" : "") + (extra || "") + "' href='" + base + "storie/" + s.id + ".html' data-id='" + s.id + "' style='--a:" + a + "'>" +
      "<div class='rd-tempo'><span class='ora'>" + ora(p.data) + "</span><span class='fa' data-t='" + p.data + "'>" + fa(p.data) + "</span></div>" +
      "<div class='rd-corpo'><div class='rd-top'><span class='liv'>" + esc(s.livello) + "</span><span class='chip-cat'>" + esc(s.sezione || "") + "</span>" +
      (s.crescita >= 2 ? "<span class='sale'>+" + s.crescita + " nell'ultima ora</span>" : "") + "</div>" +
      "<h4>" + esc(s.titolo) + "</h4><p class='rd-orig'>Uscita da <b>" + esc(p.fonte) + "</b>" + (p.veloce ? " · canale veloce" : "") + " · " + statoFonte(s) + "</p>" +
      "<div class='rd-barra' role='img' aria-label='Attendibilità " + a + " su 100'><i style='width:" + a + "%'></i></div></div>" +
      "<div class='rd-curva'>" + curvaSvg(s.curva) + "<span>" + (s.n_fonti || 1) + " testate · " + s.paesi.length + " paesi</span></div></a>";
  }
  var ordine = "nuove";
  function ordina(lista) {
    var k = { nuove: function (s) { return new Date(s.prima.data).getTime(); }, crescita: function (s) { return s.crescita * 1000 + s.att; }, att: function (s) { return s.att * 1000 + s.n_fonti; } }[ordine];
    return lista.slice().sort(function (a, b) { return k(b) - k(a); });
  }
  function disegnaDiretta(nuove, salite) {
    nuove = nuove || {}; salite = salite || {};
    var lista = $("#diretta-lista");
    if (lista) {
      var soloVoci = $("#solo-voci") && $("#solo-voci").checked, sez = $("#dir-sezione") ? $("#dir-sezione").value : "";
      var dati = ordina(L.storie.filter(function (s) { return s.prima && (!soloVoci || s.stato === "voce") && (!sez || s.sezione === sez); })).slice(0, 200);
      lista.innerHTML = dati.map(function (s) { return rigaDiretta(s, nuove[s.id] ? " nuova" : salite[s.id] ? " salita" : ""); }).join("") || "<p class='meta' style='padding:20px 0'>Nessuna notizia con questi filtri.</p>";
    }
    var mini = $("#diretta-mini");
    if (mini) {
      var n = +mini.dataset.quante || 8;
      mini.innerHTML = L.storie.filter(function (s) { return s.prima; }).sort(function (a, b) { return new Date(b.prima.data) - new Date(a.prima.data); })
        .slice(0, n).map(function (s) { return rigaDiretta(s, nuove[s.id] ? " nuova" : ""); }).join("");
    }
  }
  var schede = $(".schede");
  if (schede) {
    schede.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return; ordine = b.dataset.ordina;
      schede.querySelectorAll("button").forEach(function (x) { x.classList.toggle("on", x === b); x.setAttribute("aria-selected", x === b); });
      disegnaDiretta();
    });
    ["#solo-voci", "#dir-sezione"].forEach(function (q) { var el = $(q); if (el) el.addEventListener("change", function () { disegnaDiretta(); }); });
  }

  /* ---------- globo */
  var globo = null, canvas = $("#globo");
  if (canvas && window.Globo) {
    globo = window.Globo(canvas, {
      paesi: L.paesi, nomi: L.nomi, tip: $("#globo-tip"),
      suClick: function (cod) {
        if (document.body.dataset.pagina === "mondo") filtraPaese(cod);
        else location.href = base + "mondo.html?paese=" + cod;
      }
    });
  }

  /* ---------- inclinazione 3D della storia d'apertura */
  var foto = $(".lead .foto");
  if (foto && !ridotto && matchMedia("(hover: hover)").matches) {
    foto.addEventListener("mousemove", function (e) {
      var b = foto.getBoundingClientRect(), x = (e.clientX - b.left) / b.width - .5, y = (e.clientY - b.top) / b.height - .5;
      foto.style.transform = "rotateY(" + (x * 10).toFixed(2) + "deg) rotateX(" + (-y * 10).toFixed(2) + "deg) translateZ(10px)";
    });
    foto.addEventListener("mouseleave", function () { foto.style.transform = ""; });
  }

  /* ---------- numeri che contano */
  var numeri = document.querySelectorAll("[data-n]");
  if (numeri.length && "IntersectionObserver" in window && !ridotto) {
    var io = new IntersectionObserver(function (voci) {
      voci.forEach(function (v) {
        if (!v.isIntersecting) return; io.unobserve(v.target);
        var el = v.target, fine = +el.dataset.n, t0 = performance.now();
        (function passo(t) { var k = Math.min(1, (t - t0) / 900); el.textContent = Math.round(fine * (1 - Math.pow(1 - k, 3))).toLocaleString("it-IT"); if (k < 1) requestAnimationFrame(passo); })(t0);
      });
    }, { threshold: .4 });
    numeri.forEach(function (n) { io.observe(n); });
  }

  /* ---------- pagina "Dal mondo": filtri */
  var filtroCont = "tutti", filtroPaese = null;
  function applica() {
    document.querySelectorAll(".storia").forEach(function (s) {
      var ok = (filtroCont === "tutti" || s.dataset.c === filtroCont) && (!filtroPaese || (" " + s.dataset.p + " ").indexOf(" " + filtroPaese + " ") >= 0);
      s.hidden = !ok;
    });
    var info = $("#filtro-paese");
    if (info) info.innerHTML = filtroPaese ? "Stai vedendo le notizie da <b>" + esc(L.nomi[filtroPaese] || filtroPaese) + "</b>. <button type='button' id='togli-paese'>Mostra tutte</button>" : "";
    var b = $("#togli-paese"); if (b) b.onclick = function () { filtroPaese = null; applica(); };
  }
  function filtraPaese(cod) { filtroPaese = cod; applica(); if (globo) globo.giraVerso(cod); var l = $("#storie"); if (l) l.scrollIntoView({ behavior: ridotto ? "auto" : "smooth", block: "start" }); }
  var filtri = $("#filtri");
  if (filtri) {
    filtri.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      filtroCont = b.dataset.c;
      filtri.querySelectorAll("button").forEach(function (x) { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
      applica();
    });
    var q = new URLSearchParams(location.search).get("paese");
    if (q) setTimeout(function () { filtraPaese(q); }, 300);
    if (location.hash) { var d = document.getElementById(location.hash.slice(1)); if (d) { var det = d.querySelector("details"); if (det) det.open = true; } }
  }

  /* ---------- aggiornamento automatico (solo quando il sito è online) */
  if (location.protocol.indexOf("http") !== 0) return;
  var avviso = document.createElement("div");
  avviso.className = "avviso-nuove";
  avviso.innerHTML = "<button type='button' class='btn3d giallo'><span class='punto'></span><span class='testo'></span></button>";
  document.body.appendChild(avviso);
  avviso.querySelector("button").onclick = function () { location.reload(); };

  function controlla() {
    fetch(base + "data/live.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (nuovo) {
      if (!nuovo || !nuovo.aggiornato || nuovo.aggiornato === L.aggiornato) return;
      var visti = {}; L.storie.forEach(function (s) { visti[s.id] = s.att || 0; });
      var nuove = nuovo.storie.filter(function (s) { return !(s.id in visti); });
      var idNuove = {}, salite = {};
      nuove.forEach(function (s) { idNuove[s.id] = 1; });
      nuovo.storie.forEach(function (s) { if (s.id in visti && (s.att || 0) > visti[s.id]) salite[s.id] = 1; });
      L = nuovo; relativo();
      disegnaDiretta(idNuove, salite);
      var st = $("#dir-stato");
      if (st) st.textContent = "Aggiornata alle " + ora(L.aggiornato) + ": " + nuove.length + " nuove, " + Object.keys(salite).length + " con attendibilità in salita.";
      var hs = document.querySelector("[data-hero=storie]"), hp = document.querySelector("[data-hero=paesi]");
      if (hs) hs.textContent = L.totale || L.storie.length; if (hp) hp.textContent = Object.keys(L.paesi).length;
      if (globo) globo.aggiorna({ paesi: L.paesi, nomi: L.nomi });
      var did = document.querySelectorAll(".didascalia b");
      if (did.length === 2) { did[0].textContent = L.storie.length + " storie"; did[1].textContent = Object.keys(L.paesi).length + " paesi"; }
      var lista = $("#flusso-live");
      if (lista) {
        var n = +lista.dataset.quante || 8, ids = {}; nuove.forEach(function (s) { ids[s.id] = 1; });
        var sez = lista.dataset.sezione;
        lista.innerHTML = L.storie.filter(function (s) { return s.pubblicata !== false && (!sez || s.sezione === sez); }).slice(0, n).map(function (s) { return voce(s, ids[s.id]); }).join("");
      }
      var nastro = $(".ultimora .nastro");
      if (nastro) { var h = L.storie.filter(function (s) { return s.pubblicata !== false; }).slice(0, 10).map(function (s) { return "<a href='" + base + "storie/" + s.id + ".html'>" + esc(s.titolo) + "</a>"; }).join(""); nastro.innerHTML = h + h; }
      if (nuove.length && document.body.dataset.pagina === "mondo") {
        avviso.querySelector(".testo").textContent = nuove.length === 1 ? "1 notizia nuova: mostra" : nuove.length + " notizie nuove: mostra";
        avviso.classList.add("on");
      }
    }).catch(function () {});
  }
  setInterval(controlla, 60000);
})();
