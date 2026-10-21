/* ADOLOS — globo 3D "Il mondo, adesso"
   Nessuna libreria esterna: canvas 2D con proiezione ortografica.
   Uso: Globo(canvas, { paesi: {IT: 4, US: 7}, nomi: {IT: "Italia"}, tip: elemento, suClick: fn(codice) }) */
(function () {
  "use strict";

  // Contorni dei continenti, volutamente semplificati (lat, lng)
  var TERRE = [
    [[70,-165],[71,-156],[70,-140],[69,-130],[70,-115],[73,-95],[69,-85],[62,-75],[60,-64],[53,-56],[47,-53],[45,-62],[43,-70],[41,-71],[35,-76],[30,-81],[25,-80],[27,-82],[30,-84],[30,-89],[29,-95],[26,-97],[21,-97],[18,-95],[19,-91],[21,-87],[18,-88],[15,-84],[11,-83],[9,-79],[8,-77],[7,-80],[9,-85],[13,-88],[15,-93],[17,-100],[20,-105],[23,-110],[27,-111],[31,-113],[32,-117],[35,-121],[40,-124],[46,-124],[49,-125],[55,-131],[58,-137],[60,-146],[59,-153],[56,-158],[55,-163],[59,-158],[61,-165],[65,-168]],
    [[83,-35],[82,-20],[76,-18],[70,-22],[65,-38],[60,-43],[64,-52],[70,-54],[76,-68],[79,-72],[82,-62]],
    [[12,-72],[10,-62],[7,-58],[5,-52],[0,-50],[-2,-44],[-5,-35],[-8,-35],[-13,-38],[-23,-41],[-25,-48],[-29,-49],[-34,-53],[-36,-57],[-39,-62],[-42,-64],[-47,-66],[-51,-69],[-55,-67],[-54,-72],[-47,-75],[-40,-73],[-30,-71],[-18,-70],[-14,-76],[-6,-81],[-1,-80],[2,-79],[7,-77],[9,-76],[11,-74]],
    [[37,-9],[43,-9],[43,-2],[46,-1],[48,-5],[49,0],[51,2],[53,5],[54,9],[57,8],[58,6],[62,5],[65,12],[70,19],[71,26],[69,33],[67,41],[68,44],[69,55],[73,70],[73,80],[76,95],[77,105],[74,113],[73,130],[72,140],[70,160],[67,180],[62,179],[60,170],[59,163],[52,157],[55,155],[59,151],[54,140],[48,140],[43,133],[39,128],[35,129],[34,126],[38,125],[40,122],[37,122],[35,120],[31,122],[27,120],[23,117],[22,113],[21,108],[18,106],[16,108],[11,109],[9,105],[10,104],[13,100],[10,99],[7,100],[4,103],[1,104],[3,101],[7,98],[10,98],[16,97],[17,94],[22,92],[22,89],[20,86],[16,82],[13,80],[9,79],[8,77],[12,75],[18,73],[22,70],[24,67],[25,62],[26,57],[24,57],[22,59],[18,56],[17,52],[13,45],[17,43],[21,39],[28,34],[31,35],[36,36],[37,28],[40,26],[41,23],[38,24],[36,22],[39,20],[42,19],[45,13],[44,12],[42,15],[40,18],[38,16],[40,15],[42,12],[44,9],[43,5],[43,3],[41,2],[38,0],[36,-5]],
    [[35,-6],[36,-1],[37,10],[33,11],[31,16],[32,20],[31,25],[31,32],[28,34],[22,37],[15,39],[12,43],[11,51],[4,48],[-2,41],[-10,40],[-16,40],[-21,35],[-26,33],[-34,26],[-35,20],[-29,16],[-22,14],[-17,12],[-11,14],[-6,12],[-1,9],[4,9],[4,6],[6,1],[5,-4],[4,-8],[7,-12],[10,-15],[15,-17],[21,-17],[27,-13],[31,-10]],
    [[-11,142],[-17,141],[-12,136],[-12,131],[-15,129],[-14,126],[-20,119],[-22,114],[-26,113],[-32,115],[-35,117],[-34,123],[-32,127],[-32,133],[-35,136],[-38,140],[-39,146],[-37,150],[-33,152],[-28,153],[-24,152],[-19,147],[-15,145]],
    [[-12,49],[-16,50],[-25,47],[-25,44],[-17,44]],
    [[58,-5],[58,-3],[55,-1],[53,0],[51,1],[50,-5],[52,-5],[54,-3],[55,-6]],
    [[45,142],[43,145],[40,142],[35,140],[34,135],[33,130],[35,133],[38,139],[41,140]],
    [[5,95],[1,104],[-6,106],[-3,101]],
    [[7,117],[1,119],[-4,116],[-3,110],[2,109]],
    [[-35,173],[-41,176],[-46,170],[-44,168],[-40,172]],
    [[66,-23],[66,-14],[64,-14],[63,-20]],
    [[19,121],[13,124],[7,126],[9,123],[14,120]],
    [[10,80],[8,82],[6,81],[7,80]],
    [[-2,131],[-6,141],[-9,147],[-10,150],[-6,147],[-3,139]]
  ];

  // Centro approssimativo di ogni paese (lat, lng)
  var CENTRI = {US:[39,-98],CA:[57,-101],MX:[23,-102],CU:[22,-79],HT:[19,-72],DO:[19,-70],GT:[15,-90],HN:[15,-87],PA:[9,-80],CR:[10,-84],JM:[18,-77],
    BR:[-10,-52],AR:[-35,-65],CO:[4,-73],CL:[-33,-71],PE:[-10,-75],VE:[7,-66],EC:[-1,-78],UY:[-33,-56],PY:[-23,-58],BO:[-17,-64],
    GB:[54,-2],IE:[53,-8],FR:[46.5,2.5],DE:[51,10],ES:[40,-4],PT:[39.5,-8],IT:[42.5,12.5],NL:[52.2,5.5],BE:[50.6,4.6],CH:[46.8,8.2],AT:[47.5,14.5],
    SE:[62,15],NO:[62,9],DK:[56,10],FI:[63,26],IS:[65,-18],PL:[52,19],CZ:[49.8,15.5],SK:[48.7,19.7],HU:[47.2,19.5],RO:[45.9,25],BG:[42.7,25.5],GR:[39,22],
    RS:[44,21],HR:[45.1,15.2],SI:[46.1,14.8],BA:[44,17.8],ME:[42.7,19.3],MK:[41.6,21.7],AL:[41,20],XK:[42.6,20.9],EE:[58.6,25],LV:[56.9,24.6],LT:[55.2,23.9],
    UA:[49,32],BY:[53.7,28],MD:[47.4,28.4],RU:[56,38],CY:[35,33],MT:[35.9,14.4],LU:[49.8,6.1],VA:[41.9,12.45],
    TR:[39,35],IL:[31.5,34.9],PS:[31.9,35.2],LB:[33.9,35.9],SY:[35,38],JO:[31,36],IQ:[33,44],IR:[32,53],SA:[24,45],AE:[24,54],QA:[25.3,51.2],KW:[29.3,47.6],YE:[15.5,47.5],
    GE:[42,43.5],AM:[40.1,45],AZ:[40.3,47.7],KZ:[48,67],AF:[33.9,67.7],PK:[30,70],IN:[22,79],BD:[23.7,90.3],LK:[7.9,80.8],NP:[28.4,84.1],
    CN:[35,104],TW:[23.7,121],HK:[22.3,114.2],JP:[36.5,138.5],KR:[36.5,127.8],MN:[46.9,103.8],MM:[21,96],TH:[15.5,101],VN:[16,107.5],KH:[12.6,105],LA:[19.9,102.5],
    MY:[4,102],SG:[1.35,103.8],ID:[-2.5,118],PH:[12.9,122],AU:[-25,134],NZ:[-41,174],
    EG:[26.8,30.8],MA:[31.8,-7.1],DZ:[28,2.6],TN:[34,9.5],LY:[27,17],SD:[15.5,30],ET:[9,40],KE:[0.2,37.9],UG:[1.4,32.3],TZ:[-6.4,34.9],NG:[9.1,8.7],GH:[7.9,-1],
    SN:[14.5,-14.5],CI:[7.5,-5.5],CM:[7.4,12.4],ZA:[-30.6,22.9],NA:[-22.9,18.5],BW:[-22.3,24.7],ZW:[-19,29.2],ZM:[-13.1,27.8],AO:[-11.2,17.9],MZ:[-18.7,35.5],
    RW:[-1.9,29.9],CD:[-2.9,23.7],CG:[-0.7,15.8]};
  var REDAZIONE = [41.9, 12.5]; // le notizie "arrivano" qui

  var R = Math.PI / 180;
  function dentro(lat, lng, poly) {
    var c = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      var yi = poly[i][0], xi = poly[i][1], yj = poly[j][0], xj = poly[j][1];
      if ((yi > lat) !== (yj > lat) && lng < (xj - xi) * (lat - yi) / (yj - yi) + xi) c = !c;
    }
    return c;
  }
  var PUNTI_TERRA = null;
  function puntiTerra() {
    if (PUNTI_TERRA) return PUNTI_TERRA;
    PUNTI_TERRA = [];
    for (var lat = -56; lat <= 82; lat += 2.4) {
      var passo = 2.4 / Math.max(0.2, Math.cos(lat * R));
      for (var lng = -180; lng < 180; lng += passo) {
        for (var k = 0; k < TERRE.length; k++) if (dentro(lat, lng, TERRE[k])) { PUNTI_TERRA.push(xyz(lat, lng)); break; }
      }
    }
    return PUNTI_TERRA;
  }
  function xyz(lat, lng) {
    var a = lat * R, b = lng * R;
    return [Math.cos(a) * Math.sin(b), Math.sin(a), Math.cos(a) * Math.cos(b)];
  }

  window.Globo = function (canvas, opz) {
    var ctx = canvas.getContext("2d");
    var ridotto = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var rotY = 14 * R, rotX = 28 * R, vel = ridotto ? 0 : 0.0016;
    var trascina = null, ultimoTocco = 0, W = 0, H = 0, raggio = 0, dpr = 1;
    var dati = { paesi: {}, nomi: {} }, marcatori = [], archi = [], hover = null, t0 = performance.now();
    var terra = puntiTerra();

    function imposta(nuovi) {
      dati = nuovi || dati;
      var max = 1;
      Object.keys(dati.paesi).forEach(function (c) { if (dati.paesi[c] > max) max = dati.paesi[c]; });
      marcatori = Object.keys(dati.paesi).filter(function (c) { return CENTRI[c]; }).map(function (c) {
        return { cod: c, n: dati.paesi[c], p: xyz(CENTRI[c][0], CENTRI[c][1]), r: 2.5 + 7 * Math.sqrt(dati.paesi[c] / max) };
      });
      archi = marcatori.filter(function (m) { return m.cod !== "IT"; })
        .sort(function (a, b) { return b.n - a.n; }).slice(0, 14)
        .map(function (m, i) { return { da: m.p, a: xyz(REDAZIONE[0], REDAZIONE[1]), fase: i * 0.13 }; });
    }
    function dimensiona() {
      var box = canvas.getBoundingClientRect();
      dpr = Math.min(2, window.devicePixelRatio || 1);
      W = box.width; H = box.width;
      canvas.width = W * dpr; canvas.height = H * dpr;
      raggio = W * 0.44;
    }
    function ruota(p) {
      var cy = Math.cos(rotY), sy = Math.sin(rotY), cx = Math.cos(rotX), sx = Math.sin(rotX);
      var x = p[0] * cy - p[2] * sy, z = p[0] * sy + p[2] * cy;
      var y = p[1] * cx - z * sx; z = p[1] * sx + z * cx;
      return [x, y, z];
    }
    function proietta(q) { return [W / 2 + q[0] * raggio, H / 2 - q[1] * raggio, q[2]]; }
    function slerp(a, b, t) {
      var d = Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))), s = Math.sin(d) || 1;
      var k1 = Math.sin((1 - t) * d) / s, k2 = Math.sin(t * d) / s, h = 1 + 0.22 * Math.sin(Math.PI * t) * Math.min(1, d);
      return [(a[0] * k1 + b[0] * k2) * h, (a[1] * k1 + b[1] * k2) * h, (a[2] * k1 + b[2] * k2) * h];
    }

    function disegna(ora) {
      if (!trascina && ora - ultimoTocco > 2500) rotY += vel * 16;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      // alone e sfera
      var g = ctx.createRadialGradient(W / 2 - raggio * .35, H / 2 - raggio * .4, raggio * .1, W / 2, H / 2, raggio * 1.05);
      g.addColorStop(0, "#5e1a1f"); g.addColorStop(.7, "#2c0809"); g.addColorStop(1, "#160304");
      ctx.beginPath(); ctx.arc(W / 2, H / 2, raggio, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
      ctx.lineWidth = 1; ctx.strokeStyle = "rgba(255,255,255,.12)"; ctx.stroke();
      // terre a puntini
      for (var i = 0; i < terra.length; i++) {
        var q = ruota(terra[i]); if (q[2] <= 0) continue;
        var p = proietta(q);
        ctx.fillStyle = "rgba(255,226,228," + (0.18 + q[2] * 0.55).toFixed(3) + ")";
        ctx.fillRect(p[0] - .9, p[1] - .9, 1.8, 1.8);
      }
      // archi verso la redazione
      var tt = (ora - t0) / 2600;
      archi.forEach(function (a) {
        var fase = ((tt + a.fase) % 1 + 1) % 1, prev = null;
        for (var s = 0; s <= 40; s++) {
          var t = s / 40, q = ruota(slerp(a.da, a.a, t)); var p = proietta(q);
          if (prev && q[2] > -0.05 && prev[2] > -0.05) {
            var vicino = Math.abs(t - fase) < 0.12 ? 1 - Math.abs(t - fase) / 0.12 : 0;
            ctx.strokeStyle = vicino ? "rgba(255,212,0," + (0.35 + 0.65 * vicino).toFixed(2) + ")" : "rgba(255,212,0,.16)";
            ctx.lineWidth = vicino ? 2 : 1;
            ctx.beginPath(); ctx.moveTo(prev[0], prev[1]); ctx.lineTo(p[0], p[1]); ctx.stroke();
          }
          prev = [p[0], p[1], q[2]];
        }
      });
      // marcatori dei paesi
      var pul = 0.5 + 0.5 * Math.sin(ora / 380);
      marcatori.forEach(function (m) {
        var q = ruota(m.p); m.vis = q[2] > 0.05; if (!m.vis) return;
        var p = proietta(q); m.sx = p[0]; m.sy = p[1];
        var r = m.r * (0.75 + 0.25 * q[2]);
        ctx.beginPath(); ctx.arc(p[0], p[1], r + 4 + pul * 3, 0, Math.PI * 2); ctx.fillStyle = "rgba(211,32,43,.22)"; ctx.fill();
        ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, Math.PI * 2); ctx.fillStyle = hover === m ? "#ffd400" : "#ff3b47"; ctx.fill();
        ctx.lineWidth = 1.5; ctx.strokeStyle = "#fff"; ctx.stroke();
      });
      // la redazione
      var qr = ruota(xyz(REDAZIONE[0], REDAZIONE[1]));
      if (qr[2] > 0) { var pr = proietta(qr); ctx.beginPath(); ctx.arc(pr[0], pr[1], 4, 0, Math.PI * 2); ctx.fillStyle = "#ffd400"; ctx.fill(); }
      requestAnimationFrame(disegna);
    }

    function trova(ev) {
      var b = canvas.getBoundingClientRect(), x = ev.clientX - b.left, y = ev.clientY - b.top, best = null, dmin = 16;
      marcatori.forEach(function (m) { if (!m.vis) return; var d = Math.hypot(m.sx - x, m.sy - y) - m.r; if (d < dmin) { dmin = d; best = m; } });
      return { m: best, x: x, y: y };
    }
    canvas.addEventListener("pointerdown", function (e) { trascina = { x: e.clientX, y: e.clientY, ry: rotY, rx: rotX, mosso: false }; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", function (e) {
      if (trascina) {
        var dx = e.clientX - trascina.x, dy = e.clientY - trascina.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) trascina.mosso = true;
        rotY = trascina.ry - dx * 0.008; rotX = Math.max(-1.2, Math.min(1.2, trascina.rx + dy * 0.006)); ultimoTocco = performance.now();
        return;
      }
      var f = trova(e); hover = f.m; canvas.style.cursor = f.m ? "pointer" : "grab";
      if (opz.tip) {
        if (f.m) { opz.tip.textContent = (dati.nomi[f.m.cod] || f.m.cod) + ": " + f.m.n + (f.m.n === 1 ? " storia" : " storie"); opz.tip.style.left = f.x + "px"; opz.tip.style.top = f.y + "px"; opz.tip.classList.add("on"); }
        else opz.tip.classList.remove("on");
      }
    });
    canvas.addEventListener("pointerup", function (e) {
      var era = trascina; trascina = null; ultimoTocco = performance.now();
      if (era && !era.mosso) { var f = trova(e); if (f.m && opz.suClick) opz.suClick(f.m.cod); }
    });
    canvas.addEventListener("pointerleave", function () { hover = null; if (opz.tip) opz.tip.classList.remove("on"); });
    canvas.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") rotY += .15; if (e.key === "ArrowRight") rotY -= .15;
      if (e.key === "ArrowUp") rotX = Math.max(-1.2, rotX - .1); if (e.key === "ArrowDown") rotX = Math.min(1.2, rotX + .1);
      ultimoTocco = performance.now();
    });
    window.addEventListener("resize", dimensiona);
    dimensiona(); imposta(opz); requestAnimationFrame(disegna);
    return { aggiorna: imposta, giraVerso: function (cod) { var c = CENTRI[cod]; if (c) { rotY = c[1] * R; rotX = Math.max(-1.2, Math.min(1.2, c[0] * R)); ultimoTocco = performance.now(); } } };
  };
})();
