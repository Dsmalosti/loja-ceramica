// Carrossel do herói e animação de entrada da landing. Sem dependências.
(function () {
  "use strict";
  document.documentElement.classList.add("tem-js");

  var reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Aparecer ao rolar ---------- */
  var itens = [].slice.call(document.querySelectorAll(".revela"));
  if ("IntersectionObserver" in window && !reduzir) {
    var obs = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("visivel"); obs.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    itens.forEach(function (el) { obs.observe(el); });
  } else {
    itens.forEach(function (el) { el.classList.add("visivel"); });
  }

  /* ---------- Carrossel ---------- */
  var raiz = document.querySelector("[data-carrossel]");
  if (!raiz) return;
  var slides = [].slice.call(raiz.querySelectorAll(".slide"));
  if (slides.length < 2) return;

  var INTERVALO = 6500;
  var atual = 0, timer = null, pausadoPeloUsuario = reduzir, pausadoTemporario = false;
  var contador = raiz.querySelector("[data-atual]");
  var barra = raiz.querySelector("[data-progresso]");
  var barraBox = barra && barra.parentNode;
  var botaoPausa = raiz.querySelector("[data-pausa]");
  raiz.style.setProperty("--intervalo", INTERVALO + "ms");

  function dois(n) { return (n < 10 ? "0" : "") + n; }

  function reiniciarBarra() {
    if (!barra) return;
    barra.classList.remove("corre");
    void barra.offsetWidth; // força o navegador a reiniciar a animação
    if (!pausadoPeloUsuario) barra.classList.add("corre");
  }

  function ir(n) {
    slides[atual].classList.remove("is-active");
    slides[atual].setAttribute("aria-hidden", "true");
    atual = (n + slides.length) % slides.length;
    slides[atual].classList.add("is-active");
    slides[atual].removeAttribute("aria-hidden");
    if (contador) contador.textContent = dois(atual + 1);
    reiniciarBarra();
  }

  function agendar() {
    clearTimeout(timer);
    if (pausadoPeloUsuario || pausadoTemporario) return;
    timer = setTimeout(function () { ir(atual + 1); agendar(); }, INTERVALO);
  }

  function atualizarEstado() {
    var parado = pausadoPeloUsuario || pausadoTemporario;
    // quem usa leitor de tela é avisado das trocas só quando o automático está desligado
    raiz.querySelector(".capa__slides").setAttribute("aria-live", parado ? "polite" : "off");
    if (barraBox) barraBox.classList.toggle("pausado", parado);
    if (botaoPausa) {
      botaoPausa.textContent = pausadoPeloUsuario ? "Continuar" : "Pausar";
      botaoPausa.setAttribute("aria-pressed", pausadoPeloUsuario ? "true" : "false");
    }
    agendar();
  }

  raiz.querySelector("[data-anterior]").addEventListener("click", function () { ir(atual - 1); agendar(); });
  raiz.querySelector("[data-proximo]").addEventListener("click", function () { ir(atual + 1); agendar(); });
  if (botaoPausa) botaoPausa.addEventListener("click", function () {
    pausadoPeloUsuario = !pausadoPeloUsuario;
    reiniciarBarra();
    atualizarEstado();
  });

  // pausa enquanto o mouse ou o teclado estão sobre o carrossel
  raiz.addEventListener("mouseenter", function () { pausadoTemporario = true; atualizarEstado(); });
  raiz.addEventListener("mouseleave", function () { pausadoTemporario = false; atualizarEstado(); });
  raiz.addEventListener("focusin", function () { pausadoTemporario = true; atualizarEstado(); });
  raiz.addEventListener("focusout", function () { pausadoTemporario = false; atualizarEstado(); });

  raiz.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { ir(atual - 1); agendar(); }
    else if (e.key === "ArrowRight") { ir(atual + 1); agendar(); }
  });

  // arrastar com o dedo no celular
  var x0 = null;
  raiz.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; }, { passive: true });
  raiz.addEventListener("touchend", function (e) {
    if (x0 === null) return;
    var dx = e.changedTouches[0].clientX - x0;
    x0 = null;
    if (Math.abs(dx) > 45) { ir(dx < 0 ? atual + 1 : atual - 1); agendar(); }
  }, { passive: true });

  // aba escondida: não gasta bateria trocando foto
  document.addEventListener("visibilitychange", function () {
    pausadoTemporario = document.hidden;
    atualizarEstado();
  });

  reiniciarBarra();
  atualizarEstado();
})();
